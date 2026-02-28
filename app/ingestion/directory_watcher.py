"""
Directory watcher — monitors a directory for new log files.

Uses watchdog to detect new files and submits them for analysis
via the background job queue.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Allowed extensions for auto-ingestion
WATCH_EXTENSIONS = {".log", ".txt", ".json"}


class DirectoryWatcher:
    """
    Watches a directory for new log files and triggers analysis.

    Usage:
        watcher = DirectoryWatcher("/var/log/app", on_new_file=my_callback)
        watcher.start()
        # ...
        watcher.stop()
    """

    def __init__(
        self,
        watch_path: str,
        on_new_file: Optional[Callable[[str], None]] = None,
        extensions: Optional[set[str]] = None,
    ):
        self.watch_path = Path(watch_path)
        self.on_new_file = on_new_file
        self.extensions = extensions or WATCH_EXTENSIONS
        self._observer: Optional[object] = None
        self._running = False

        if not self.watch_path.is_dir():
            raise ValueError(f"Watch path is not a directory: {watch_path}")

    def start(self) -> None:
        """Start watching the directory for new files."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileCreatedEvent

            watcher_self = self

            class _Handler(FileSystemEventHandler):
                def on_created(self, event: FileCreatedEvent) -> None:
                    if event.is_directory:
                        return
                    file_path = event.src_path
                    ext = Path(file_path).suffix.lower()
                    if ext in watcher_self.extensions:
                        logger.info("New file detected: %s", file_path)
                        if watcher_self.on_new_file:
                            try:
                                watcher_self.on_new_file(file_path)
                            except Exception as e:
                                logger.error(
                                    "Error processing new file %s: %s",
                                    file_path, e,
                                )

            observer = Observer()
            observer.schedule(_Handler(), str(self.watch_path), recursive=False)
            observer.daemon = True
            observer.start()
            self._observer = observer
            self._running = True

            logger.info(
                "Directory watcher started: %s (extensions: %s)",
                self.watch_path, self.extensions,
            )

        except ImportError:
            logger.warning(
                "watchdog not installed — directory watching unavailable"
            )

    def stop(self) -> None:
        """Stop watching."""
        if self._observer and self._running:
            self._observer.stop()  # type: ignore[attr-defined]
            self._observer.join()  # type: ignore[attr-defined]
            self._running = False
            logger.info("Directory watcher stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def scan_existing(self) -> list[str]:
        """
        Scan for existing files in the watch directory.

        Returns list of file paths matching the watched extensions.
        Useful for initial processing on startup.
        """
        files = []
        for f in self.watch_path.iterdir():
            if f.is_file() and f.suffix.lower() in self.extensions:
                files.append(str(f))
        return sorted(files)
