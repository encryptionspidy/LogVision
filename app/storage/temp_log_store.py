"""
Temporary log storage for session-scoped log files.

Provides file-based storage with automatic cleanup, compression for large files,
and TTL-based expiration to manage storage growth while enabling context reuse.
"""

import os
import gzip
import shutil
import hashlib
import threading
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from app.config.settings import DEFAULT_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class TempLogEntry:
    """Metadata for a temporary log file."""
    session_id: str
    file_path: str
    original_size: int
    compressed_size: int = 0
    is_compressed: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class TempLogStore:
    """
    Session-scoped temporary storage for log files.
    
    Features:
    - Automatic compression for files > 10MB
    - TTL-based expiration (default 24 hours)
    - Thread-safe operations
    - Automatic cleanup of expired entries
    """
    
    def __init__(self, base_dir: Optional[str] = None, ttl_hours: int = 24):
        """
        Initialize the temporary log store.
        
        Args:
            base_dir: Base directory for storage (defaults to data/temp_logs)
            ttl_hours: Time-to-live for stored logs in hours
        """
        self.base_dir = Path(base_dir or os.path.join(os.getcwd(), "data", "temp_logs"))
        self.ttl_hours = ttl_hours
        self.compression_threshold = 10 * 1024 * 1024  # 10MB
        self._lock = threading.Lock()
        self._entries: Dict[str, TempLogEntry] = {}
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Start cleanup thread
        self._start_cleanup_thread()
        
        logger.info(f"TempLogStore initialized with base_dir={self.base_dir}, ttl={ttl_hours}h")
    
    def _get_session_dir(self, session_id: str) -> Path:
        """Get the directory for a specific session."""
        # Use hash of session_id to avoid filesystem issues with long IDs
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()[:16]
        return self.base_dir / session_hash
    
    def _compress_file(self, file_path: Path) -> tuple[Path, int]:
        """
        Compress a file using gzip.
        
        Args:
            file_path: Path to file to compress
            
        Returns:
            Tuple of (compressed_file_path, compressed_size)
        """
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            compressed_size = compressed_path.stat().st_size
            # Remove original file after successful compression
            file_path.unlink()
            
            logger.info(f"Compressed {file_path} -> {compressed_path} "
                       f"({file_path.stat().st_size} -> {compressed_size} bytes)")
            
            return compressed_path, compressed_size
        except Exception as e:
            logger.error(f"Compression failed for {file_path}: {e}")
            # If compression fails, keep original
            if compressed_path.exists():
                compressed_path.unlink()
            return file_path, file_path.stat().st_size
    
    def _decompress_file(self, compressed_path: Path) -> tuple[Path, int]:
        """
        Decompress a gzip file.
        
        Args:
            compressed_path: Path to compressed file
            
        Returns:
            Tuple of (decompressed_file_path, decompressed_size)
        """
        decompressed_path = compressed_path.with_suffix('')  # Remove .gz
        
        try:
            with gzip.open(compressed_path, 'rb') as f_in:
                with open(decompressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            decompressed_size = decompressed_path.stat().st_size
            return decompressed_path, decompressed_size
        except Exception as e:
            logger.error(f"Decompression failed for {compressed_path}: {e}")
            raise
    
    def store(
        self,
        session_id: str,
        log_content: str,
        filename: str = "logs.txt"
    ) -> TempLogEntry:
        """
        Store log content for a session.
        
        Args:
            session_id: Session identifier
            log_content: Raw log content as string
            filename: Optional filename for the stored file
            
        Returns:
            TempLogEntry with metadata
        """
        with self._lock:
            session_dir = self._get_session_dir(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = session_dir / filename
            original_size = len(log_content.encode('utf-8'))
            
            # Write content to file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
            except Exception as e:
                logger.error(f"Failed to write log file {file_path}: {e}")
                raise
            
            # Compress if large enough
            is_compressed = False
            compressed_size = original_size
            
            if original_size > self.compression_threshold:
                file_path, compressed_size = self._compress_file(file_path)
                is_compressed = True
            
            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(hours=self.ttl_hours)
            
            # Create entry
            entry = TempLogEntry(
                session_id=session_id,
                file_path=str(file_path),
                original_size=original_size,
                compressed_size=compressed_size,
                is_compressed=is_compressed,
                expires_at=expires_at
            )
            
            self._entries[session_id] = entry
            
            logger.info(f"Stored log for session {session_id}: "
                       f"size={original_size}, compressed={is_compressed}, "
                       f"expires={expires_at.isoformat()}")
            
            return entry
    
    def retrieve(self, session_id: str) -> Optional[str]:
        """
        Retrieve log content for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Log content as string, or None if not found
        """
        with self._lock:
            entry = self._entries.get(session_id)
            
            if not entry:
                logger.warning(f"No log entry found for session {session_id}")
                return None
            
            # Check if expired
            if entry.expires_at and datetime.utcnow() > entry.expires_at:
                logger.info(f"Log entry for session {session_id} has expired")
                self.delete(session_id)
                return None
            
            file_path = Path(entry.file_path)
            
            if not file_path.exists():
                logger.error(f"Log file {file_path} does not exist")
                del self._entries[session_id]
                return None
            
            # Decompress if needed
            if entry.is_compressed:
                decompressed_path, _ = self._decompress_file(file_path)
                file_path = decompressed_path
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Clean up decompressed file if it was temporary
                if entry.is_compressed and decompressed_path.exists():
                    decompressed_path.unlink()
                
                logger.info(f"Retrieved log for session {session_id}: size={len(content)}")
                return content
            except Exception as e:
                logger.error(f"Failed to read log file {file_path}: {e}")
                return None
    
    def delete(self, session_id: str) -> bool:
        """
        Delete log entry for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            entry = self._entries.pop(session_id, None)
            
            if not entry:
                return False
            
            session_dir = self._get_session_dir(session_id)
            
            try:
                if session_dir.exists():
                    shutil.rmtree(session_dir)
                logger.info(f"Deleted log storage for session {session_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete storage for session {session_id}: {e}")
                return False
    
    def get_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a session's log entry.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with metadata, or None if not found
        """
        with self._lock:
            entry = self._entries.get(session_id)
            
            if not entry:
                return None
            
            return {
                "session_id": entry.session_id,
                "original_size": entry.original_size,
                "compressed_size": entry.compressed_size,
                "is_compressed": entry.is_compressed,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "compression_ratio": round(entry.compressed_size / entry.original_size, 3) if entry.original_size > 0 else 0
            }
    
    def _cleanup_expired(self):
        """Clean up expired entries."""
        with self._lock:
            now = datetime.utcnow()
            expired_sessions = [
                session_id for session_id, entry in self._entries.items()
                if entry.expires_at and now > entry.expires_at
            ]
            
            for session_id in expired_sessions:
                logger.info(f"Cleaning up expired session {session_id}")
                self.delete(session_id)
    
    def _start_cleanup_thread(self):
        """Start background thread for periodic cleanup."""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(3600)  # Run every hour
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logger.info("Started cleanup thread")
    
    def cleanup_all(self):
        """Clean up all entries (for testing or shutdown)."""
        with self._lock:
            session_ids = list(self._entries.keys())
            for session_id in session_ids:
                self.delete(session_id)
            logger.info("Cleaned up all temporary log entries")


# Global instance
_temp_log_store: Optional[TempLogStore] = None


def get_temp_log_store() -> TempLogStore:
    """Get the global TempLogStore instance."""
    global _temp_log_store
    if _temp_log_store is None:
        _temp_log_store = TempLogStore()
    return _temp_log_store
