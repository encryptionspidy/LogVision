"""Tests for app.monitoring (Streamer & Watcher)."""

import pytest
import time
import os
from threading import Thread
from sqlalchemy import text
from app.monitoring.stream import LogStreamer, StreamProcessor
from app.monitoring.watcher import LogMonitor, MonitoringHandler
from app.storage.database import get_db, Database

@pytest.fixture
def monitored_file(tmp_path):
    f = tmp_path / "stream.log"
    f.touch()
    return f

def test_streamer_reads_new_content(monitored_file):
    """Verify streamer reads lines appended after init."""
    # Write initial content
    monitored_file.write_text("line1\n")
    
    # Init streamer (starts at EOF by default for existing file)
    streamer = LogStreamer(str(monitored_file))
    assert streamer.last_position == len("line1\n")
    
    # Append
    with open(monitored_file, "a") as f:
        f.write("line2\nline3\n")
        
    lines = list(streamer.read_new_content())
    assert lines == ["line2", "line3"]

def test_streamer_handles_rotation(monitored_file):
    """Verify streamer resets position on rotation (inode change/truncation)."""
    monitored_file.write_text("line1\n")
    streamer = LogStreamer(str(monitored_file))
    
    # Simulate rotation: rename old, create new
    rotated = monitored_file.with_name("stream.log.1")
    monitored_file.rename(rotated)
    monitored_file.write_text("newline1\n")
    
    # streamer should detect inode change (if OS supports it) OR size change
    lines = list(streamer.read_new_content())
    assert "newline1" in lines

def test_stream_processor_integration(monitored_file, tmp_path):
    """Verify processor runs pipeline and inserts to DB."""
    # Setup isolated test DB
    db_path = tmp_path / "monitor_test.db"
    # Patch get_db to return our test db
    test_db = Database(db_path)
    
    # Monkey patch get_db in stream module
    import app.monitoring.stream
    original_get_db = app.monitoring.stream.get_db
    app.monitoring.stream.get_db = lambda: test_db
    
    try:
        processor = StreamProcessor(str(monitored_file), batch_size=1)
        
        # Append log line
        with open(monitored_file, "a") as f:
            f.write("Jan 15 10:30:45 host app: ERROR: Database connection failed\n")
            
        processor.process_new_lines()
        
        # Check DB
        with test_db.get_connection() as conn:
            row = conn.execute(text("SELECT * FROM logs")).fetchone()
            assert row is not None
            assert "Database connection failed" in row.message
            
    finally:
        app.monitoring.stream.get_db = original_get_db
        test_db.close()
