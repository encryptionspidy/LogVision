"""
File watcher using watchdog.

Triggers `StreamProcessor` on file modification events.
"""
import logging
import os
import time
from threading import Thread
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.monitoring.stream import StreamProcessor

logger = logging.getLogger(__name__)

class MonitoringHandler(FileSystemEventHandler):
    """
    Watchdog handler that triggers processing on file modification.
    """
    def __init__(self, target_file: str):
        self.target_file = os.path.abspath(target_file)
        self.processor = StreamProcessor(target_file)

    def on_modified(self, event):
        if event.src_path == self.target_file:
            self.processor.process_new_lines()

    def on_created(self, event):
        if event.src_path == self.target_file:
            # Handle rotation create
            self.processor.process_new_lines()

class LogMonitor:
    """
    Manages the background watcher thread via watchdog observer.
    """
    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.observer: Optional[Observer] = None
        self.handler: Optional[MonitoringHandler] = None

    def start(self):
        """Start the file watcher in background."""
        if self.observer:
            return

        directory = os.path.dirname(self.file_path)
        if not directory: 
            directory = "."
            
        self.handler = MonitoringHandler(self.file_path)
        self.observer = Observer()
        self.observer.schedule(self.handler, directory, recursive=False)
        self.observer.start()
        logger.info("Started monitoring %s", self.file_path)

    def stop(self):
        """Stop the watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        logger.info("Stopped monitoring %s", self.file_path)
