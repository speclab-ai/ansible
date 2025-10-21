"""
Reproduction of Problem 5e369604: Forked Display.display Deadlock Risk

This example demonstrates how Display.display() called from worker processes
writes directly to stdout/stderr, causing deadlock risk during shutdown.

PROBLEM:
- Worker processes call Display.display() directly
- display() writes to stdout/stderr without buffering
- Workers inherit parent's file descriptors
- During shutdown, if pipe buffer is full, write() blocks
- Can deadlock if main process is also trying to write
- Cleanup handlers can't redirect to /dev/null in time

IMPACT:
- Ansible hangs during shutdown
- Ctrl-C doesn't work properly
- Process cleanup fails
- Need to kill -9 to terminate

SCENARIO:
```
Main Process:
  - Spawns workers
  - Workers inherit stdout/stderr pipes
  - Each worker calls display() frequently

Worker Process:
  - Calls Display.display("message")
  - Writes directly to inherited stdout
  - If pipe full → write() blocks
  - Worker hangs waiting for pipe space

Shutdown:
  - Main tries to close stdout
  - Workers still writing
  - Deadlock!
```
"""

import logging
import time
from typing import List

from ansible_simulator.utils.display import Display

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class WorkerSimulation:
    """
    Simulates a worker process that uses Display.

    PROBLEM REPRODUCTION (5e369604):
    - Worker has its own Display instance
    - Calls display() directly from worker context
    - No message queue or proxy
    - Direct stdout/stderr writes
    """

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        # PROBLEM: Each worker has its own Display instance
        # All share the same stdout/stderr file descriptors
        self.display = Display()

    def run_task(self, task_name: str):
        """
        Simulate running a task with display output.

        PROBLEM: Calls display() which writes directly to stdout/stderr.
        """
        # PROBLEM: Direct write to stdout from worker
        self.display.display(f"Worker {self.worker_id}: Starting task '{task_name}'")

        # Simulate work
        time.sleep(0.01)

        # PROBLEM: More direct writes
        self.display.display(f"Worker {self.worker_id}: Task '{task_name}' completed", color='green')

        # PROBLEM: Warning also writes directly to stderr
        if self.worker_id % 2 == 0:
            self.display.warning(f"Worker {self.worker_id}: Example warning from task")


def demonstrate_problem():
    """Demonstrate Display deadlock risk."""

    logger.info("=" * 80)
    logger.info("PROBLEM 5e369604: Forked Display.display Deadlock Risk")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: How Display works in workers")
    logger.info("-" * 80)
    logger.info("")
    logger.info("In Ansible:")
    logger.info("  1. Main process spawns worker processes (fork)")
    logger.info("  2. Workers inherit parent's file descriptors (stdout, stderr)")
    logger.info("  3. Workers import Display utility")
    logger.info("  4. Display.display() writes directly to stdout/stderr")
    logger.info("  5. No message queue, no proxy, no buffering")
    logger.info("")

    logger.info("PROBLEM 1: Direct stdout/stderr writes from workers")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Simulating workers calling Display.display():")
    logger.info("")

    # Simulate multiple workers
    workers: List[WorkerSimulation] = []
    for i in range(5):
        workers.append(WorkerSimulation(worker_id=i))

    # Each worker runs tasks and calls display()
    for worker in workers:
        logger.info(f"Spawning worker {worker.worker_id}...")

    logger.info("")
    logger.info("Workers executing tasks (each calls display() directly):")
    logger.info("")

    # PROBLEM: All workers write to same stdout/stderr
    for worker in workers:
        worker.run_task(f"task-{worker.worker_id}")

    logger.info("")
    logger.info("❌ PROBLEM: All workers wrote directly to stdout/stderr")
    logger.info("❌ No isolation, no queuing, no proxying")
    logger.info("❌ Writes can block if pipe buffer fills up")
    logger.info("")

    logger.info("PROBLEM 2: Deadlock scenario during shutdown")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Scenario that causes deadlock:")
    logger.info("")
    logger.info("  1. Main process spawns 100 workers")
    logger.info("  2. Each worker frequently calls display()")
    logger.info("  3. Output pipe buffer has limited size (typically 64KB)")
    logger.info("  4. Main process reads from pipe slowly (or not at all)")
    logger.info("  5. Pipe buffer fills up")
    logger.info("")
    logger.info("  6. Worker calls display.display('message')")
    logger.info("  7. write() to stdout blocks (pipe full)")
    logger.info("  8. Worker hangs waiting for pipe space")
    logger.info("")
    logger.info("  9. User presses Ctrl-C")
    logger.info(" 10. Main tries to shutdown workers")
    logger.info(" 11. Workers blocked in write() can't respond")
    logger.info(" 12. Main tries to close stdout")
    logger.info(" 13. DEADLOCK: Workers can't finish, main can't shutdown")
    logger.info("")

    logger.info("❌ Result: Ansible hangs, need kill -9 to terminate")
    logger.info("")

    logger.info("PROBLEM 3: Cleanup handlers can't fix it")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Current workaround attempt:")
    logger.info("  • Redirect stdout/stderr to /dev/null during cleanup")
    logger.info("  • But this happens LATE in shutdown sequence")
    logger.info("  • Workers already blocked in write()")
    logger.info("  • Redirect doesn't unblock them")
    logger.info("")

    logger.info("Code from TaskQueueManager cleanup:")
    logger.info("  try:")
    logger.info("      # Redirect to /dev/null")
    logger.info("      sys.stdout = open(os.devnull, 'w')")
    logger.info("      sys.stderr = open(os.devnull, 'w')")
    logger.info("  except:")
    logger.info("      pass  # Too late, workers already deadlocked!")
    logger.info("")

    logger.info("❌ Workaround is unreliable and racy")
    logger.info("")

    logger.info("PROBLEM 4: File descriptor inheritance")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Workers inherit parent's file descriptors:")
    logger.info("")
    logger.info("  Main Process:")
    logger.info("    stdout (fd 1) → Terminal")
    logger.info("    stderr (fd 2) → Terminal")
    logger.info("")
    logger.info("  Worker Process (after fork):")
    logger.info("    stdout (fd 1) → Same Terminal (inherited!)")
    logger.info("    stderr (fd 2) → Same Terminal (inherited!)")
    logger.info("")

    logger.info("❌ All workers share same file descriptors")
    logger.info("❌ No isolation between worker outputs")
    logger.info("❌ Writes from any worker affect all others")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Issue #1: Playbook hangs during shutdown")
    logger.info("  Symptoms:")
    logger.info("    - Playbook completes but doesn't exit")
    logger.info("    - Ctrl-C doesn't work")
    logger.info("    - Must kill -9 to terminate")
    logger.info("  Cause:")
    logger.info("    - Workers blocked in display() write()")
    logger.info("    - Pipe buffer full")
    logger.info("    - Deadlock during cleanup")
    logger.info("")

    logger.info("Issue #2: Large inventories more affected")
    logger.info("  With 1000 hosts:")
    logger.info("    - Many workers spawned")
    logger.info("    - Each worker calls display() frequently")
    logger.info("    - Pipe buffer fills quickly")
    logger.info("    - Higher deadlock probability")
    logger.info("")

    logger.info("Issue #3: Verbose output makes it worse")
    logger.info("  With -vvv:")
    logger.info("    - Even more display() calls")
    logger.info("    - More data written to pipes")
    logger.info("    - Pipe fills even faster")
    logger.info("    - Almost guaranteed deadlock")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Fix #1: Use message queue instead of direct writes")
    logger.info("  ✅ Workers send messages to queue")
    logger.info("  ✅ Main process drains queue and writes to stdout")
    logger.info("  ✅ Workers never block on write()")
    logger.info("  ✅ Clean shutdown possible")
    logger.info("")

    logger.info("Implementation:")
    logger.info("  class Display:")
    logger.info("      def __init__(self):")
    logger.info("          if in_worker_process():")
    logger.info("              self.queue = get_worker_queue()")
    logger.info("          else:")
    logger.info("              self.queue = None")
    logger.info("")
    logger.info("      def display(self, msg):")
    logger.info("          if self.queue:")
    logger.info("              # Worker: Send to queue (non-blocking)")
    logger.info("              self.queue.put(msg)")
    logger.info("          else:")
    logger.info("              # Main: Write directly")
    logger.info("              sys.stdout.write(msg)")
    logger.info("")

    logger.info("Fix #2: Redirect worker stdout/stderr at fork time")
    logger.info("  ✅ Before worker starts, redirect to /dev/null or pipe")
    logger.info("  ✅ Workers can't write to parent's stdout/stderr")
    logger.info("  ✅ Prevents inheritance issues")
    logger.info("")

    logger.info("Fix #3: Make Display.display() non-blocking in workers")
    logger.info("  ✅ Use O_NONBLOCK flag on write")
    logger.info("  ✅ If write would block, buffer or drop message")
    logger.info("  ✅ Never hang in write()")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Forked Display.display deadlock causes:")
    logger.info("  1. Workers write directly to stdout/stderr (no queue)")
    logger.info("  2. Pipe buffer fills up with many workers")
    logger.info("  3. write() blocks when pipe full")
    logger.info("  4. Workers can't shutdown (blocked in write)")
    logger.info("  5. Deadlock during cleanup")
    logger.info("  6. Ansible hangs, requires kill -9")
    logger.info("  7. Worse with large inventories and verbose output")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
