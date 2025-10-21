"""
Reproduction of Problem 42355d18: Double Calculation of loops and delegate_to

This example demonstrates the problem where tasks with both loops and delegate_to
evaluate these values multiple times, causing inconsistent results.

PROBLEM:
- When a task uses both loop and delegate_to, values are calculated TWICE
- Loop items evaluated: once early, once during execution
- delegate_to evaluated: once early, once PER LOOP ITERATION
- Causes inconsistent results when delegate_to uses random/dynamic selection

IMPACT:
- If delegate_to uses random selection: {{ groups['servers'] | random }}
  Each evaluation picks a different host!
- Loop items could differ if using dynamic queries
- Wasted computation
- Unpredictable behavior
"""

import simpy
import logging

from simulator.infra.network import Network
from simulator.infra.machine import Machine

from ansible_simulator.shared.models import (
    Host, Inventory, Task
)
from ansible_simulator.components.executor import TaskExecutor

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Also adjust executor logger to show warnings
exec_logger = logging.getLogger('ansible_simulator.components.executor')
exec_logger.setLevel(logging.WARNING)


def demonstrate_problem():
    """Demonstrate double calculation of loop and delegate_to."""

    logger.info("=" * 80)
    logger.info("PROBLEM 42355d18: Double Calculation of loops and delegate_to")
    logger.info("=" * 80)
    logger.info("")

    # Setup simulation environment
    env = simpy.Environment()
    network = Network(env)

    # Create host
    host = Host(name="web1", ansible_connection="local")

    # Create task with BOTH loop and delegate_to
    task = Task(
        name="Install packages",
        action="apt",
        args={"name": "{{ item }}", "state": "present"},
        loop=["nginx", "redis", "postgresql"],
        delegate_to="random_host"  # Special marker for random selection
    )

    logger.info("Task configuration:")
    logger.info(f"  name: {task.name}")
    logger.info(f"  loop: {task.loop}")
    logger.info(f"  delegate_to: {task.delegate_to}")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Watch the evaluation sequence:")
    logger.info("=" * 80)
    logger.info("")

    # Create executor
    executor = TaskExecutor(
        env=env,
        network=network,
        task=task,
        host=host,
        task_vars={},
        play_context={}
    )

    # Run the task
    def run_task():
        result = yield from executor.run()
        return result

    env.process(run_task())

    # Run simulation for a bit
    env.run(until=2.0)

    logger.info("")
    logger.info("=" * 80)
    logger.info("PROBLEM ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("1. delegate_to evaluated MULTIPLE times:")
    logger.info("   - 1st time: Early in TaskExecutor.run() -> may get 'host1'")
    logger.info("   - 2nd time: In loop iteration 1 (nginx) -> may get 'host2'")
    logger.info("   - 3rd time: In loop iteration 2 (redis) -> may get 'host3'")
    logger.info("   - 4th time: In loop iteration 3 (postgresql) -> may get 'host1'")
    logger.info("")
    logger.info("   ❌ delegate_to changes for each loop iteration!")
    logger.info("   ❌ Inconsistent delegation - nginx goes to host2, redis to host3!")
    logger.info("")

    logger.info("2. Loop items evaluated TWICE:")
    logger.info("   - 1st time: Early in TaskExecutor.run()")
    logger.info("   - 2nd time: When actually running the loop")
    logger.info("")
    logger.info("   ❌ Wasted computation")
    logger.info("   ❌ Could get different results if query/lookup is dynamic")
    logger.info("")

    logger.info("3. Real-world impact:")
    logger.info("")
    logger.info("   Playbook example:")
    logger.info("   ```yaml")
    logger.info("   - name: Deploy config")
    logger.info("     copy:")
    logger.info("       src: {{ item }}")
    logger.info("       dest: /etc/app/")
    logger.info("     loop: {{ query('fileglob', '*.conf') }}  # Dynamic!")
    logger.info("     delegate_to: {{ groups['managers'] | random }}  # Random!")
    logger.info("   ```")
    logger.info("")
    logger.info("   Problems:")
    logger.info("   - query('fileglob') runs twice - finds different files?")
    logger.info("   - groups['managers'] | random evaluated 1 + N times")
    logger.info("     → Each file goes to a DIFFERENT random manager!")
    logger.info("   - Expected: all files to same random manager")
    logger.info("   - Actual: files scattered across different managers")
    logger.info("")

    logger.info("SOLUTION NEEDED:")
    logger.info("-" * 80)
    logger.info("✅ Evaluate loop items ONCE, cache the result")
    logger.info("✅ Evaluate delegate_to ONCE before loop, reuse for all iterations")
    logger.info("✅ delegate_to resolution happens BEFORE loop processing")
    logger.info("✅ Both use cached values throughout execution")
    logger.info("")

    logger.info("Expected flow:")
    logger.info("  1. Resolve delegate_to -> cache 'host2'")
    logger.info("  2. Evaluate loop items -> cache ['nginx', 'redis', 'postgresql']")
    logger.info("  3. For each cached item:")
    logger.info("     - Use cached delegate_to host")
    logger.info("     - Execute on that host")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Double calculation causes:")
    logger.info("  1. Inconsistent delegation (different host per loop item)")
    logger.info("  2. Wasted computation (evaluate same expression multiple times)")
    logger.info("  3. Unpredictable behavior with dynamic lookups")
    logger.info("  4. Difficult to debug issues")
    logger.info("=" * 80)


def demonstrate_with_counts():
    """Show exactly how many times things are evaluated."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("EVALUATION COUNT DEMONSTRATION")
    logger.info("=" * 80)
    logger.info("")

    # Track evaluation counts
    loop_eval_count = 0
    delegate_eval_count = 0

    def count_loop_eval(items):
        nonlocal loop_eval_count
        loop_eval_count += 1
        logger.info(f"  Loop evaluated: count={loop_eval_count}, items={items}")
        return items

    def count_delegate_eval(target):
        nonlocal delegate_eval_count
        delegate_eval_count += 1
        import random
        hosts = ["host1", "host2", "host3"]
        selected = random.choice(hosts)
        logger.info(f"  delegate_to evaluated: count={delegate_eval_count}, target={selected}")
        return selected

    logger.info("Simulating task execution with loop and delegate_to:")
    logger.info("")

    # Simulate TaskExecutor.run()
    logger.info("TaskExecutor.run() called:")

    # Early evaluations
    count_delegate_eval("{{ groups['servers'] | random }}")  # 1st eval
    count_loop_eval(["nginx", "redis", "postgresql"])  # 1st eval

    logger.info("")
    logger.info("_run_loop() called:")

    # Loop execution
    count_loop_eval(["nginx", "redis", "postgresql"])  # 2nd eval

    for item in ["nginx", "redis", "postgresql"]:
        count_delegate_eval("{{ groups['servers'] | random }}")  # 2nd, 3rd, 4th eval
        logger.info(f"    Executing item: {item}")

    logger.info("")
    logger.info(f"Total loop evaluations: {loop_eval_count} (should be 1!)")
    logger.info(f"Total delegate_to evaluations: {delegate_eval_count} (should be 1!)")
    logger.info("")
    logger.info("❌ loop evaluated 2 times (expected: 1)")
    logger.info("❌ delegate_to evaluated 4 times for 3 items! (expected: 1)")
    logger.info("")


if __name__ == "__main__":
    demonstrate_problem()
    demonstrate_with_counts()
