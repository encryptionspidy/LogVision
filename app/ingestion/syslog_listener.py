"""
Syslog UDP listener — future-ready stub for receiving syslog messages.

Binds to a configurable UDP port and receives syslog datagrams.
This is intentionally minimal — not wired into the main pipeline yet.

Usage:
    listener = SyslogListener(port=514)
    listener.start()
    # ... later
    messages = listener.drain()
    listener.stop()
"""

from __future__ import annotations

import logging
import socket
import threading
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_PORT = 5140  # Use non-privileged port by default
DEFAULT_HOST = "0.0.0.0"
MAX_BUFFER_SIZE = 10_000
RECV_BUFFER = 8192


class SyslogListener:
    """
    UDP syslog listener with internal message buffer.

    Thread-safe. Messages accumulate in a bounded deque and can be
    drained for batch processing.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        max_buffer: int = MAX_BUFFER_SIZE,
    ):
        self.host = host
        self.port = port
        self._buffer: deque[str] = deque(maxlen=max_buffer)
        self._lock = threading.Lock()
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start listening for syslog UDP datagrams."""
        if self._running:
            return

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.settimeout(1.0)

            self._running = True
            self._thread = threading.Thread(
                target=self._receive_loop,
                daemon=True,
                name="syslog-listener",
            )
            self._thread.start()

            logger.info(
                "Syslog listener started on %s:%d", self.host, self.port
            )
        except OSError as e:
            logger.error("Failed to start syslog listener: %s", e)
            self._running = False

    def _receive_loop(self) -> None:
        """Background thread: receive UDP datagrams."""
        while self._running and self._sock:
            try:
                data, addr = self._sock.recvfrom(RECV_BUFFER)
                message = data.decode("utf-8", errors="replace").strip()
                if message:
                    with self._lock:
                        self._buffer.append(message)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.warning("Socket error in syslog listener")
                break

    def stop(self) -> None:
        """Stop the listener and close the socket."""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("Syslog listener stopped")

    def drain(self) -> list[str]:
        """
        Drain all buffered messages.

        Returns a list of raw syslog strings and clears the buffer.
        Thread-safe.
        """
        with self._lock:
            messages = list(self._buffer)
            self._buffer.clear()
        return messages

    @property
    def buffer_size(self) -> int:
        """Current number of buffered messages."""
        with self._lock:
            return len(self._buffer)

    @property
    def is_running(self) -> bool:
        return self._running
