"""
Incremental log stream processor.

Handles reading new content from a file, detecting rotation,
and processing chunks through the analysis pipeline.
"""

import logging
import os
import time
from pathlib import Path
from typing import Generator, List, Callable

from app.ingestion.reader import detect_encoding
from app.ingestion.normalizer import normalize_entries
from app.parsing.parser import parse_log_entries
from app.anomaly.evaluator import evaluate_anomalies
from app.severity.scorer import score_entries
from app.explanation.generator import generate_explanations
from app.explanation.deep_explainer import upgrade_explanations
from app.storage.database import get_db
from models.schemas import AnalysisReport, AnomalyResult, SeverityResult, Explanation

logger = logging.getLogger(__name__)

class LogStreamer:
    """
    Tracks file state and yields new lines as they appear.
    Handles file rotation by detecting inode changes or size reduction.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path).resolve()
        self.last_position = 0
        self.last_inode = self._get_inode()
        self.buffer = ""
        
        # Initialize position to end of file for new watchers (don't re-ingest old logs)
        # OR start from 0 if we want full history. For real-time monitoring, 
        # usually start from end unless specified otherwise.
        # Decision: Start from EOF to avoid flooding alerts on startup.
        if self.file_path.exists():
            self.last_position = self.file_path.stat().st_size

    def _get_inode(self) -> int:
        if self.file_path.exists():
            return self.file_path.stat().st_ino
        return 0

    def read_new_content(self) -> Generator[str, None, None]:
        """
        Read continuously from the file, yielding new lines.
        Detects rotation and truncation.
        """
        if not self.file_path.exists():
            return

        current_inode = self._get_inode()
        current_size = self.file_path.stat().st_size

        # Detect rotation (different inode) or truncation (same inode, smaller size)
        if current_inode != self.last_inode:
            logger.info("File rotation detected (inode changed). resetting position.")
            self.last_position = 0
            self.last_inode = current_inode
        elif current_size < self.last_position:
            logger.info("File truncation detected. resetting position.")
            self.last_position = 0

        # Read new data
        try:
            encoding = detect_encoding(self.file_path)
            with open(self.file_path, "r", encoding=encoding, errors="replace") as f:
                f.seek(self.last_position)
                content = f.read()
                if content:
                    self.last_position = f.tell()
                    
                    # Handle partial lines buffer
                    raw_data = self.buffer + content
                    lines = raw_data.split('\n')
                    
                    # If the last character was a newline, the last split is empty string -> good
                    # If not, the last split is a partial line -> keep in buffer
                    if raw_data.endswith('\n'):
                        self.buffer = ""
                    else:
                        self.buffer = lines.pop() # Remove incomplete line
                        
                    for line in lines:
                        if line: # Skip empty
                            yield line
        except OSError as e:
            logger.error("Error reading log stream: %s", e)

class StreamProcessor:
    """
    Orchestrates the pipeline for streaming data.
    """
    def __init__(self, file_path: str, batch_size: int = 50):
        self.streamer = LogStreamer(file_path)
        self.batch_size = batch_size
        self.batch_buffer: List[str] = []
        self.db = get_db()
        self.line_counter = 1 # We might need persistent line counter if we want strict line numbers
        
        # Note: line numbers in streaming are relative to the *session* or need persistence.
        # For simplicity, we just count up from start of monitoring.

    def process_new_lines(self):
        """
        Pull lines from streamer, accumulate batch, run pipeline.
        """
        for line in self.streamer.read_new_content():
            self.batch_buffer.append(line)
            
            if len(self.batch_buffer) >= self.batch_size:
                self._flush_batch()
        
        # Flush remaining if any (optional time-based flush could be added)
        if self.batch_buffer:
            self._flush_batch()

    def _flush_batch(self):
        if not self.batch_buffer:
            return

        try:
            # 1. Pipeline: Raw lines -> Tuple(line_num, line)
            # We assign line numbers roughly. 
            indexed_lines = [
                (self.line_counter + i, line) 
                for i, line in enumerate(self.batch_buffer)
            ]
            self.line_counter += len(self.batch_buffer)
            
            # 2. Normalize
            # normalize_entries requires a generator of (int, str)
            normalized = list(normalize_entries(iter(indexed_lines)))
            
            # 3. Parse
            entries = parse_log_entries(lines=normalized)
            if not entries:
                self.batch_buffer = []
                return

            # 4. Anomaly
            anomalies = evaluate_anomalies(entries)

            # 5. Severity
            severities = score_entries(entries, anomalies)

            # 6. Explanation
            explanations = generate_explanations(entries, anomalies, severities)

            # 7. Persist
            reports = []
            for entry in entries:
                # TODO: Check alert rules here (Phase 14)
                
                reports.append(AnalysisReport(
                    log_entry=entry,
                    anomaly=anomalies.get(entry.line_number, AnomalyResult()),
                    severity=severities.get(entry.line_number, SeverityResult()),
                    explanation=explanations.get(entry.line_number, Explanation()),
                ))

            # Phase 5: Upgrade explanations with batch context.
            # Never fail the stream batch because of explanation upgrades.
            try:
                upgraded = upgrade_explanations(reports)
                for r in reports:
                    if r.log_entry.line_number in upgraded:
                        r.explanation = upgraded[r.log_entry.line_number]
            except Exception:
                logger.exception("Deep explanation upgrade failed; using template explanations")

            self.db.insert_reports(reports)
            logger.info("Processed batch of %d lines", len(self.batch_buffer))

        except Exception as e:
            logger.exception("Error processing stream batch: %s", e)
        finally:
            self.batch_buffer = [] 
