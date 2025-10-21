"""
Display Utility for Ansible Simulator.

PROBLEM REPRODUCTION (5e369604):
- Display.display() called from worker processes writes directly to stdout/stderr
- During shutdown, this can cause deadlock when pipes are full
- Workers inherit parent's file descriptors without proper isolation

PROBLEM REPRODUCTION (a7d2a4e0):
- Display calls from workers are not deduplicated globally
- Same warning appears multiple times (once per worker)
- No global deduplication cache across processes
"""

import sys
import threading
from typing import Optional


class Display:
    """
    Display utility for outputting messages.

    PROBLEM REPRODUCTION (5e369604):
    - Workers call display() directly
    - Writes to stdout/stderr without buffering
    - Can deadlock during shutdown if pipe is full
    - No message queue or proxy mechanism
    """

    def __init__(self):
        self.lock = threading.Lock()
        self._color_codes = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'reset': '\033[0m',
        }

        # PROBLEM (a7d2a4e0): Per-instance deduplication only
        # Each worker has its own Display instance, so no global dedup!
        self._message_cache = set()

    def display(self, msg: str, color: Optional[str] = None, stderr: bool = False):
        """
        Display a message.

        PROBLEM REPRODUCTION (5e369604):
        - Called from worker processes
        - Writes directly to stdout/stderr
        - No queue, no proxy, no buffering
        - Deadlock risk during shutdown
        """
        with self.lock:
            # PROBLEM: Direct write to stdout/stderr from worker!
            output = sys.stderr if stderr else sys.stdout

            if color and color in self._color_codes:
                formatted_msg = f"{self._color_codes[color]}{msg}{self._color_codes['reset']}"
            else:
                formatted_msg = msg

            # PROBLEM: This write can block/deadlock!
            output.write(formatted_msg + '\n')
            output.flush()

    def warning(self, msg: str):
        """
        Display a warning.

        PROBLEM REPRODUCTION (a7d2a4e0):
        - Should deduplicate globally across all workers
        - Currently only deduplicates per-instance
        - Workers have separate Display instances
        - Same warning appears multiple times!
        """
        # PROBLEM: Per-instance cache, not global!
        msg_hash = hash(msg)

        if msg_hash in self._message_cache:
            # Already displayed in THIS instance
            return

        self._message_cache.add(msg_hash)

        # PROBLEM: Direct write to stderr from worker
        self.display(f"[WARNING]: {msg}", color='yellow', stderr=True)

    def deprecated(self, msg: str, version: str):
        """
        Display a deprecation warning.

        PROBLEM REPRODUCTION (a7d2a4e0):
        - Same issue as warning()
        - No global deduplication
        - Each worker shows the same deprecation
        """
        # PROBLEM: Per-instance cache
        full_msg = f"{msg} [deprecated in {version}]"
        msg_hash = hash(full_msg)

        if msg_hash in self._message_cache:
            return

        self._message_cache.add(msg_hash)

        # PROBLEM: Direct write from worker
        self.display(f"[DEPRECATED]: {full_msg}", color='red', stderr=True)

    def error(self, msg: str):
        """Display an error."""
        self.display(f"[ERROR]: {msg}", color='red', stderr=True)

    def vvv(self, msg: str):
        """Display verbose message (simulated)."""
        # Simplified - in real Ansible, checks verbosity level
        pass
