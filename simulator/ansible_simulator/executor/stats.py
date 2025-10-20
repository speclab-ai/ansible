"""
AggregateStats - Per-host activity statistics.

Mirrors lib/ansible/executor/stats.py for proper statistics tracking.
"""

from typing import Dict, Any, Optional
from collections.abc import MutableMapping


class AggregateStats:
    """
    Holds stats about per-host activity during playbook runs.

    This class mirrors Ansible's AggregateStats exactly, tracking:
    - processed: Hosts that have been processed
    - ok: Successful tasks
    - failures: Failed tasks
    - dark: Unreachable hosts
    - changed: Tasks that changed something
    - skipped: Skipped tasks
    - rescued: Tasks rescued from failure (rescue blocks)
    - ignored: Failed tasks with ignore_errors
    - custom: User-defined statistics
    """

    def __init__(self):
        self.processed: Dict[str, int] = {}
        self.failures: Dict[str, int] = {}
        self.ok: Dict[str, int] = {}
        self.dark: Dict[str, int] = {}  # Unreachable
        self.changed: Dict[str, int] = {}
        self.skipped: Dict[str, int] = {}
        self.rescued: Dict[str, int] = {}
        self.ignored: Dict[str, int] = {}

        # User defined stats, which can be per host or global
        self.custom: Dict[str, Dict[str, Any]] = {}

    def increment(self, what: str, host: str) -> None:
        """
        Helper function to bump a statistic.

        Args:
            what: Name of the stat to increment (ok, failures, changed, etc.)
            host: Host name
        """
        self.processed[host] = 1
        stat_dict = getattr(self, what)
        prev = stat_dict.get(host, 0)
        stat_dict[host] = prev + 1

    def decrement(self, what: str, host: str) -> None:
        """
        Decrement a statistic.

        Args:
            what: Name of the stat to decrement
            host: Host name
        """
        stat_dict = getattr(self, what)
        try:
            if stat_dict[host] - 1 < 0:
                # This should never happen, but let's be safe
                raise KeyError("Don't be so negative")
            stat_dict[host] -= 1
        except KeyError:
            stat_dict[host] = 0

    def summarize(self, host: str) -> Dict[str, int]:
        """
        Return information about a particular host.

        Args:
            host: Host name

        Returns:
            Dictionary with all stats for the host
        """
        return dict(
            ok=self.ok.get(host, 0),
            failures=self.failures.get(host, 0),
            unreachable=self.dark.get(host, 0),
            changed=self.changed.get(host, 0),
            skipped=self.skipped.get(host, 0),
            rescued=self.rescued.get(host, 0),
            ignored=self.ignored.get(host, 0),
        )

    def set_custom_stats(self, which: str, what: Any, host: Optional[str] = None) -> None:
        """
        Allow setting of a custom stat.

        Args:
            which: Stat name
            what: Stat value
            host: Host name (None for global stats)
        """
        if host is None:
            host = '_run'
        if host not in self.custom:
            self.custom[host] = {which: what}
        else:
            self.custom[host][which] = what

    def update_custom_stats(self, which: str, what: Any, host: Optional[str] = None) -> None:
        """
        Allow aggregation of a custom stat.

        Args:
            which: Stat name
            what: Value to aggregate
            host: Host name (None for global stats)
        """
        if host is None:
            host = '_run'
        if host not in self.custom or which not in self.custom[host]:
            return self.set_custom_stats(which, what, host)

        # Mismatching types
        if not isinstance(what, type(self.custom[host][which])):
            return None

        if isinstance(what, MutableMapping):
            # Merge dictionaries (simplified - Ansible uses merge_hash utility)
            self.custom[host][which].update(what)
        else:
            # Let overloaded + take care of other types
            self.custom[host][which] += what
