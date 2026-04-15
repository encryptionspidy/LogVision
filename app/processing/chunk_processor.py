"""
Intelligent log chunking for progressive summarization.

Implements multiple chunking strategies to handle large logs efficiently:
- Error-density chunking: Group by error concentration
- Severity-based chunking: Separate ERROR/WARN from INFO
- Temporal chunking: Time-based segments for timeline analysis
- Component-based chunking: Group by service/component
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LogChunk:
    """A chunk of log lines with metadata."""
    lines: List[str]
    start_index: int
    end_index: int
    chunk_type: str  # 'error_dense', 'severity_high', 'temporal', 'component', 'normal'
    priority: int  # Higher priority = more important for analysis
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChunkProcessor:
    """
    Intelligently chunk logs for progressive processing.
    
    Prioritizes chunks containing:
    - ERROR, WARN, FATAL, EXCEPTION
    - timeout, connection failure, permission errors
    """
    
    # Priority keywords that indicate important log lines
    PRIORITY_KEYWORDS = [
        'ERROR', 'FATAL', 'CRITICAL', 'EXCEPTION',
        'timeout', 'timed out', 'connection refused', 'connection failed',
        'permission denied', 'access denied', 'unauthorized',
        'out of memory', 'oom', 'segmentation fault', 'kernel panic',
        'deadlock', 'corruption', 'stack overflow'
    ]
    
    def __init__(self, max_chunk_size: int = 5000):
        """
        Initialize the chunk processor.
        
        Args:
            max_chunk_size: Maximum number of lines per chunk
        """
        self.max_chunk_size = max_chunk_size
    
    def chunk_logs(self, log_lines: List[str]) -> List[LogChunk]:
        """
        Chunk logs using intelligent strategies.
        
        Args:
            log_lines: List of log lines
            
        Returns:
            List of LogChunk objects sorted by priority
        """
        if not log_lines:
            return []
        
        # Apply chunking strategies
        chunks = []
        
        # Strategy 1: Error-density chunking (highest priority)
        error_chunks = self._chunk_by_error_density(log_lines)
        chunks.extend(error_chunks)
        
        # Strategy 2: Severity-based chunking
        severity_chunks = self._chunk_by_severity(log_lines)
        # Merge with existing chunks to avoid duplicates
        chunks = self._merge_chunks(chunks, severity_chunks)
        
        # Strategy 3: Component-based chunking
        component_chunks = self._chunk_by_component(log_lines)
        chunks = self._merge_chunks(chunks, component_chunks)
        
        # Strategy 4: Temporal chunking (for timeline analysis)
        temporal_chunks = self._chunk_by_temporal(log_lines)
        chunks = self._merge_chunks(chunks, temporal_chunks)
        
        # Strategy 5: Normal chunks for remaining lines (lowest priority)
        normal_chunks = self._chunk_normal(log_lines, chunks)
        chunks.extend(normal_chunks)
        
        # Sort by priority (higher first)
        chunks.sort(key=lambda c: c.priority, reverse=True)
        
        logger.info(f"Chunked {len(log_lines)} lines into {len(chunks)} chunks")
        
        return chunks
    
    def _chunk_by_error_density(self, log_lines: List[str]) -> List[LogChunk]:
        """
        Chunk logs based on error density.
        
        Identifies clusters of errors and groups them together.
        """
        chunks = []
        current_chunk = []
        chunk_start = 0
        error_count = 0
        
        for i, line in enumerate(log_lines):
            line_upper = line.upper()
            is_error = any(kw in line_upper for kw in self.PRIORITY_KEYWORDS)
            
            if is_error:
                error_count += 1
            
            current_chunk.append(line)
            
            # End chunk if we have enough lines and error density is significant
            if len(current_chunk) >= self.max_chunk_size:
                if error_count > 0:
                    chunk = LogChunk(
                        lines=current_chunk,
                        start_index=chunk_start,
                        end_index=i,
                        chunk_type='error_dense',
                        priority=5,  # High priority
                        metadata={
                            'error_count': error_count,
                            'error_density': error_count / len(current_chunk)
                        }
                    )
                    chunks.append(chunk)
                
                current_chunk = []
                chunk_start = i + 1
                error_count = 0
        
        # Handle remaining lines
        if current_chunk and error_count > 0:
            chunk = LogChunk(
                lines=current_chunk,
                start_index=chunk_start,
                end_index=len(log_lines) - 1,
                chunk_type='error_dense',
                priority=5,
                metadata={
                    'error_count': error_count,
                    'error_density': error_count / len(current_chunk)
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_by_severity(self, log_lines: List[str]) -> List[LogChunk]:
        """
        Chunk logs based on severity levels.
        
        Separates ERROR/WARN/FATAL from INFO/DEBUG.
        """
        chunks = []
        high_severity_lines = []
        low_severity_lines = []
        
        for i, line in enumerate(log_lines):
            line_upper = line.upper()
            if any(kw in line_upper for kw in ['ERROR', 'WARN', 'FATAL', 'CRITICAL']):
                high_severity_lines.append((i, line))
            else:
                low_severity_lines.append((i, line))
        
        # Create chunk for high-severity lines
        if high_severity_lines:
            chunk = LogChunk(
                lines=[line for _, line in high_severity_lines],
                start_index=high_severity_lines[0][0],
                end_index=high_severity_lines[-1][0],
                chunk_type='severity_high',
                priority=4,
                metadata={
                    'severity_level': 'high',
                    'line_count': len(high_severity_lines)
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_by_component(self, log_lines: List[str]) -> List[LogChunk]:
        """
        Chunk logs based on components/services.
        
        Groups logs by service names extracted from log patterns like [ServiceName].
        """
        chunks = []
        component_groups: Dict[str, List[Tuple[int, str]]] = {}
        
        # Extract component names from log lines
        component_pattern = r'\[(\w+)\]'
        
        for i, line in enumerate(log_lines):
            matches = re.findall(component_pattern, line)
            if matches:
                # Use the first match as the component
                component = matches[0]
                if component not in component_groups:
                    component_groups[component] = []
                component_groups[component].append((i, line))
        
        # Create chunks for components with error lines
        for component, lines in component_groups.items():
            # Check if this component has errors
            has_errors = any(
                any(kw in line.upper() for kw in self.PRIORITY_KEYWORDS)
                for _, line in lines
            )
            
            if has_errors and len(lines) >= 5:  # Only chunk if meaningful
                chunk = LogChunk(
                    lines=[line for _, line in lines],
                    start_index=lines[0][0],
                    end_index=lines[-1][0],
                    chunk_type='component',
                    priority=3,
                    metadata={
                        'component': component,
                        'line_count': len(lines),
                        'has_errors': has_errors
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _chunk_by_temporal(self, log_lines: List[str]) -> List[LogChunk]:
        """
        Chunk logs based on temporal segments.
        
        Groups logs by time windows for timeline analysis.
        """
        chunks = []
        
        # Try to extract timestamps from log lines
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})'
        
        time_groups: Dict[str, List[Tuple[int, str]]] = {}
        current_date = None
        
        for i, line in enumerate(log_lines):
            match = re.search(timestamp_pattern, line)
            if match:
                date_str = match.group(1)
                if date_str != current_date:
                    current_date = date_str
                    time_groups[date_str] = []
                time_groups[date_str].append((i, line))
            elif current_date:
                # Add to current time group
                time_groups[current_date].append((i, line))
        
        # Create chunks for time groups with errors
        for date_str, lines in time_groups.items():
            if len(lines) >= 10:  # Only chunk if meaningful
                has_errors = any(
                    any(kw in line.upper() for kw in self.PRIORITY_KEYWORDS)
                    for _, line in lines
                )
                
                if has_errors:
                    chunk = LogChunk(
                        lines=[line for _, line in lines],
                        start_index=lines[0][0],
                        end_index=lines[-1][0],
                        chunk_type='temporal',
                        priority=2,
                        metadata={
                            'time_window': date_str,
                            'line_count': len(lines),
                            'has_errors': has_errors
                        }
                    )
                    chunks.append(chunk)
        
        return chunks
    
    def _chunk_normal(self, log_lines: List[str], existing_chunks: List[LogChunk]) -> List[LogChunk]:
        """
        Chunk remaining normal lines that weren't covered by other strategies.
        
        Args:
            log_lines: All log lines
            existing_chunks: Chunks already created by other strategies
            
        Returns:
            List of normal chunks
        """
        # Find indices not covered by existing chunks
        covered_indices = set()
        for chunk in existing_chunks:
            covered_indices.update(range(chunk.start_index, chunk.end_index + 1))
        
        # Get uncovered lines
        uncovered_lines = [
            (i, line) for i, line in enumerate(log_lines)
            if i not in covered_indices
        ]
        
        if not uncovered_lines:
            return []
        
        # Chunk uncovered lines
        chunks = []
        current_chunk = []
        chunk_start = 0
        
        for i, (line_idx, line) in enumerate(uncovered_lines):
            current_chunk.append((line_idx, line))
            
            if len(current_chunk) >= self.max_chunk_size:
                chunk = LogChunk(
                    lines=[line for _, line in current_chunk],
                    start_index=current_chunk[0][0],
                    end_index=current_chunk[-1][0],
                    chunk_type='normal',
                    priority=1,  # Lowest priority
                    metadata={
                        'line_count': len(current_chunk)
                    }
                )
                chunks.append(chunk)
                current_chunk = []
                chunk_start = i + 1
        
        # Handle remaining lines
        if current_chunk:
            chunk = LogChunk(
                lines=[line for _, line in current_chunk],
                start_index=current_chunk[0][0],
                end_index=current_chunk[-1][0],
                chunk_type='normal',
                priority=1,
                metadata={
                    'line_count': len(current_chunk)
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _merge_chunks(self, existing_chunks: List[LogChunk], new_chunks: List[LogChunk]) -> List[LogChunk]:
        """
        Merge new chunks with existing chunks, avoiding duplicates.
        
        Args:
            existing_chunks: Existing chunks
            new_chunks: New chunks to merge
            
        Returns:
            Merged list of chunks
        """
        # For simplicity, just add new chunks if they don't overlap significantly
        # A more sophisticated implementation would merge overlapping chunks
        merged = existing_chunks.copy()
        
        for new_chunk in new_chunks:
            # Check if this chunk significantly overlaps with existing chunks
            has_overlap = False
            for existing in existing_chunks:
                overlap_start = max(new_chunk.start_index, existing.start_index)
                overlap_end = min(new_chunk.end_index, existing.end_index)
                overlap_size = max(0, overlap_end - overlap_start + 1)
                
                # If overlap is more than 50% of either chunk, consider it a duplicate
                if overlap_size > len(new_chunk.lines) * 0.5 or overlap_size > len(existing.lines) * 0.5:
                    has_overlap = True
                    break
            
            if not has_overlap:
                merged.append(new_chunk)
        
        return merged
