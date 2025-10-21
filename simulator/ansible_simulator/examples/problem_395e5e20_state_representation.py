"""
Reproduction of Problem 395e5e20: PlayIterator State Representation

This example demonstrates the problem with PlayIterator using plain integers
for state representation instead of a public, explicit type.

PROBLEM:
- PlayIterator exposes run states and failure states as plain integers
- These integers are used directly in executor logic and strategy plugins
- Makes code harder to read (what does ITERATING_TASKS=1 mean?)
- HostState.__str__ shows opaque numeric values instead of readable names
- No public type to represent states consistently

EXPECTED:
- Single public, namespaced way to reference states
- Readable state names in string output
- Clear semantic meaning without looking up constants
"""

import simpy
import logging

from simulator.infra.network import Network
from simulator.infra.machine import Machine

from ansible_simulator.shared.models import (
    Host, Inventory, Playbook, Play, Task
)
from ansible_simulator.components.executor import PlayIterator

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def demonstrate_problem():
    """Demonstrate the confusing integer state representation."""

    logger.info("=" * 80)
    logger.info("PROBLEM 395e5e20: PlayIterator State Representation")
    logger.info("=" * 80)
    logger.info("")

    # Create simple inventory and play
    inventory = Inventory()
    inventory.add_host(Host(name="web1"))
    inventory.add_host(Host(name="web2"))

    play = Play(
        name="Test Play",
        hosts="all",
        gather_facts=True,
        tasks=[
            Task(name="Install nginx", action="apt", args={"name": "nginx"}),
            Task(name="Start nginx", action="service", args={"name": "nginx", "state": "started"})
        ]
    )

    # Create iterator
    iterator = PlayIterator(play=play, inventory=inventory)

    logger.info("PROBLEM 1: States are exposed as plain integers")
    logger.info("-" * 80)
    logger.info(f"PlayIterator.ITERATING_SETUP = {iterator.ITERATING_SETUP}")
    logger.info(f"PlayIterator.ITERATING_TASKS = {iterator.ITERATING_TASKS}")
    logger.info(f"PlayIterator.ITERATING_HANDLERS = {iterator.ITERATING_HANDLERS}")
    logger.info(f"PlayIterator.ITERATING_COMPLETE = {iterator.ITERATING_COMPLETE}")
    logger.info("")
    logger.info("❌ What does ITERATING_TASKS=1 mean? Not immediately clear!")
    logger.info("❌ External plugins access via PlayIterator.ITERATING_TASKS directly")
    logger.info("❌ No type safety - could accidentally use wrong integer")
    logger.info("")

    logger.info("PROBLEM 2: Failure states use bit flags (even more confusing)")
    logger.info("-" * 80)
    logger.info(f"PlayIterator.FAILED_NONE = {iterator.FAILED_NONE}")
    logger.info(f"PlayIterator.FAILED_SETUP = {iterator.FAILED_SETUP}")
    logger.info(f"PlayIterator.FAILED_TASKS = {iterator.FAILED_TASKS}")
    logger.info(f"PlayIterator.FAILED_RESCUE = {iterator.FAILED_RESCUE}")
    logger.info(f"PlayIterator.FAILED_ALWAYS = {iterator.FAILED_ALWAYS}")
    logger.info("")
    logger.info("❌ Bit flags (1, 2, 4, 8) require understanding binary operations")
    logger.info("❌ What does fail_state=6 mean? (FAILED_TASKS | FAILED_RESCUE)")
    logger.info("")

    logger.info("PROBLEM 3: HostState string representation is opaque")
    logger.info("-" * 80)
    for host_name, host_state in iterator.host_states.items():
        logger.info(f"Host: {host_name}")
        logger.info(f"  {host_state}")
        logger.info(f"  run_state={host_state.run_state} (what does this mean?)")
        logger.info(f"  fail_state={host_state.fail_state} (what does this mean?)")
        logger.info("")

    logger.info("❌ HostState(host=web1, run_state=0, fail_state=0)")
    logger.info("   → What is state 0? You have to look up the constant!")
    logger.info("")

    logger.info("PROBLEM 4: Code that uses states is hard to read")
    logger.info("-" * 80)
    logger.info("Example from executor code:")
    logger.info("")
    logger.info("  # What does this mean?")
    logger.info("  if state.run_state == 1:  # ??? ")
    logger.info("      do_something()")
    logger.info("")
    logger.info("  # vs. more readable (if we had enums)")
    logger.info("  if state.run_state == IteratingState.ITERATING_TASKS:")
    logger.info("      do_something()")
    logger.info("")

    logger.info("PROBLEM 5: Accessing states from instance vs class")
    logger.info("-" * 80)
    logger.info("Third-party strategy plugins access states via:")
    logger.info(f"  PlayIterator.ITERATING_TASKS = {PlayIterator.ITERATING_TASKS}")
    logger.info(f"  iterator.ITERATING_TASKS = {iterator.ITERATING_TASKS}")
    logger.info("")
    logger.info("❌ Can access through both class and instance")
    logger.info("❌ No clear public API or type for state representation")
    logger.info("")

    logger.info("SOLUTION NEEDED:")
    logger.info("-" * 80)
    logger.info("✅ Create public enum types: IteratingState, FailureState")
    logger.info("✅ HostState uses typed enums instead of integers")
    logger.info("✅ HostState.__str__ shows readable names: 'ITERATING_TASKS' not '1'")
    logger.info("✅ Backward compatibility: PlayIterator.ITERATING_TASKS still works")
    logger.info("✅ Deprecation warnings for old integer access pattern")
    logger.info("")

    # Demonstrate behavior with get_next_task
    logger.info("PROBLEM 6: Return values use integers")
    logger.info("-" * 80)
    result = iterator.get_next_task_for_host("web1")
    if result:
        task, state_int = result
        logger.info(f"get_next_task_for_host returned:")
        logger.info(f"  Task: {task.name}")
        logger.info(f"  State: {state_int}")
        logger.info("")
        logger.info(f"❌ State returned as integer: {state_int}")
        logger.info(f"   → What state is this? Have to look it up!")
        logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Integer-based state representation causes:")
    logger.info("  1. Poor readability")
    logger.info("  2. No type safety")
    logger.info("  3. Confusing debugging output")
    logger.info("  4. Inconsistent access patterns")
    logger.info("  5. No clear public API")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
