"""
Reproduction of Problem a7d2a4e0: Display Deduplication in Forks

This example demonstrates how warnings/deprecations from worker processes
are not deduplicated globally, appearing multiple times in output.

PROBLEM:
- Each worker process has its own Display instance
- Display.warning() and Display.deprecated() deduplicate per-instance
- Workers share no global deduplication cache
- Same warning appears once per worker that triggers it
- With 100 workers, same warning appears 100 times!

IMPACT:
- Output cluttered with duplicate warnings
- Hard to see real issues among duplicates
- Performance overhead (repeated formatting/writing)
- User experience degradation

SCENARIO:
```
Worker 1:
  - Display instance with local cache
  - Calls display.warning("Module X deprecated")
  - Not in cache → show warning, add to cache

Worker 2:
  - Different Display instance, empty cache!
  - Calls display.warning("Module X deprecated")
  - Not in cache → show warning again!

Worker 3:
  - Different Display instance, empty cache!
  - Same warning shown AGAIN!

Result: Same warning shown 3 times (once per worker)
```
"""

import logging
from typing import List

from ansible_simulator.utils.display import Display

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class WorkerProcess:
    """
    Simulates a worker process with its own Display instance.

    PROBLEM REPRODUCTION (a7d2a4e0):
    - Each worker has separate Display instance
    - No shared deduplication cache
    - Same warnings appear multiple times
    """

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        # PROBLEM: Each worker gets its own Display instance
        # with its own (empty) deduplication cache
        self.display = Display()

    def run_task(self):
        """
        Run a task that triggers warnings.

        PROBLEM: All workers trigger same warnings independently.
        """
        # PROBLEM: Same warning from every worker
        self.display.warning("ansible.builtin.yum module is deprecated, use dnf instead")

        # PROBLEM: Same deprecation from every worker
        if self.worker_id % 2 == 0:
            self.display.deprecated(
                "with_items is deprecated",
                version="2.10"
            )


def demonstrate_problem():
    """Demonstrate Display deduplication issues."""

    logger.info("=" * 80)
    logger.info("PROBLEM a7d2a4e0: Display Deduplication in Forks")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: How Display deduplication works")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Display class has deduplication for warnings/deprecations:")
    logger.info("  • Maintains a cache of seen messages (hashes)")
    logger.info("  • Before showing warning, checks cache")
    logger.info("  • If already shown, skip it")
    logger.info("  • Otherwise, show and add to cache")
    logger.info("")
    logger.info("PROBLEM: Cache is per-instance, not global!")
    logger.info("")

    logger.info("PROBLEM 1: Each worker has separate Display instance")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Creating 5 workers, each will show the same warning:")
    logger.info("")

    workers: List[WorkerProcess] = []
    for i in range(5):
        workers.append(WorkerProcess(worker_id=i))

    logger.info("Workers created. Each has:")
    logger.info("  - Its own Display instance")
    logger.info("  - Empty deduplication cache")
    logger.info("")

    logger.info("Now executing tasks (watch for duplicate warnings):")
    logger.info("")

    # PROBLEM: Each worker will show the same warning
    for worker in workers:
        worker.run_task()

    logger.info("")
    logger.info("❌ PROBLEM: Same warning appeared 5 times!")
    logger.info("❌ One for each worker")
    logger.info("❌ No global deduplication")
    logger.info("")

    logger.info("Expected behavior:")
    logger.info("  ✅ First worker shows warning")
    logger.info("  ✅ Subsequent workers skip it (already shown)")
    logger.info("  ✅ Warning appears exactly ONCE")
    logger.info("")

    logger.info("=" * 80)
    logger.info("ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Current implementation:")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  class Display:")
    logger.info("      def __init__(self):")
    logger.info("          self._message_cache = set()  # Per-instance!")
    logger.info("")
    logger.info("      def warning(self, msg):")
    logger.info("          msg_hash = hash(msg)")
    logger.info("          if msg_hash in self._message_cache:")
    logger.info("              return  # Already shown")
    logger.info("          self._message_cache.add(msg_hash)")
    logger.info("          # Show warning")
    logger.info("")
    logger.info("Problem: Each worker creates new Display instance with empty cache")
    logger.info("")

    logger.info("What happens:")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  Worker 1:")
    logger.info("    display = Display()  # cache = {}")
    logger.info("    display.warning('X')  # Not in cache → SHOW")
    logger.info("    # cache = {hash('X')}")
    logger.info("")
    logger.info("  Worker 2:")
    logger.info("    display = Display()  # cache = {} (different instance!)")
    logger.info("    display.warning('X')  # Not in cache → SHOW AGAIN")
    logger.info("    # cache = {hash('X')}")
    logger.info("")
    logger.info("  Worker 3:")
    logger.info("    display = Display()  # cache = {} (different instance!)")
    logger.info("    display.warning('X')  # Not in cache → SHOW AGAIN")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Scenario 1: Large inventory with deprecated module")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  Inventory: 1000 hosts")
    logger.info("  Forks: 50")
    logger.info("  Module: Uses deprecated parameter")
    logger.info("")
    logger.info("  Result:")
    logger.info("    • Same deprecation warning shown 50 times")
    logger.info("    • Once per worker process")
    logger.info("    • User sees:")
    logger.info("      [DEPRECATED]: with_items is deprecated [deprecated in 2.10]")
    logger.info("      [DEPRECATED]: with_items is deprecated [deprecated in 2.10]")
    logger.info("      ... (48 more times)")
    logger.info("")

    logger.info("Scenario 2: Module with warning in action plugin")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  Action plugin warns about parameter combination")
    logger.info("  100 hosts use this combination")
    logger.info("  Forks: 10")
    logger.info("")
    logger.info("  Result:")
    logger.info("    • Warning shown 10 times")
    logger.info("    • Output cluttered")
    logger.info("    • Real issues hidden among duplicates")
    logger.info("")

    logger.info("Scenario 3: Mixed with other warnings")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  Multiple different warnings/deprecations")
    logger.info("  Each appears N times (N = number of workers)")
    logger.info("")
    logger.info("  Example output:")
    logger.info("    [WARNING]: Module A issue")
    logger.info("    [DEPRECATED]: Feature B [deprecated in 2.10]")
    logger.info("    [WARNING]: Module A issue")
    logger.info("    [DEPRECATED]: Feature B [deprecated in 2.10]")
    logger.info("    [WARNING]: Module C issue")
    logger.info("    [WARNING]: Module A issue")
    logger.info("    [DEPRECATED]: Feature B [deprecated in 2.10]")
    logger.info("    ...")
    logger.info("")
    logger.info("  ❌ Impossible to tell how many unique issues")
    logger.info("  ❌ Can't distinguish between recurring and duplicate")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Option 1: Global deduplication cache (shared memory)")
    logger.info("  ✅ Use multiprocessing.Manager() for shared set")
    logger.info("  ✅ All workers check/update same cache")
    logger.info("  ✅ True global deduplication")
    logger.info("")
    logger.info("  Implementation:")
    logger.info("    from multiprocessing import Manager")
    logger.info("    manager = Manager()")
    logger.info("    global_message_cache = manager.dict()")
    logger.info("")
    logger.info("    class Display:")
    logger.info("        def warning(self, msg):")
    logger.info("            msg_hash = hash(msg)")
    logger.info("            if msg_hash in global_message_cache:")
    logger.info("                return")
    logger.info("            global_message_cache[msg_hash] = True")
    logger.info("            # Show warning")
    logger.info("")

    logger.info("Option 2: Proxy warnings through parent process")
    logger.info("  ✅ Workers send warnings to queue")
    logger.info("  ✅ Parent process deduplicates and displays")
    logger.info("  ✅ Single point of deduplication")
    logger.info("  ✅ Bonus: solves stdout/stderr isolation too!")
    logger.info("")
    logger.info("  Implementation:")
    logger.info("    # Workers send to queue")
    logger.info("    message_queue.put(('warning', msg))")
    logger.info("")
    logger.info("    # Parent reads and deduplicates")
    logger.info("    seen = set()")
    logger.info("    while True:")
    logger.info("        msg_type, msg = message_queue.get()")
    logger.info("        if hash(msg) not in seen:")
    logger.info("            display_message(msg)")
    logger.info("            seen.add(hash(msg))")
    logger.info("")

    logger.info("Option 3: Track in shared file")
    logger.info("  ✅ Workers write message hashes to file with locking")
    logger.info("  ✅ Check file before showing warning")
    logger.info("  ⚠️  Slower due to file I/O")
    logger.info("  ⚠️  Locking overhead")
    logger.info("")

    logger.info("Recommended: Option 2 (proxy through parent)")
    logger.info("  • Solves both deduplication AND I/O isolation")
    logger.info("  • Clean architecture")
    logger.info("  • No shared memory complexity")
    logger.info("  • Easy to add features (rate limiting, etc.)")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Display deduplication in forks causes:")
    logger.info("  1. Each worker has separate Display instance")
    logger.info("  2. Deduplication cache is per-instance, not global")
    logger.info("  3. Same warning appears once per worker")
    logger.info("  4. Output cluttered with duplicates")
    logger.info("  5. Hard to see unique issues")
    logger.info("  6. Need global deduplication via queue or shared memory")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
