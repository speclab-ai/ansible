"""
Reproduction of Problem 5c225dc0: Lack of Public Methods for PlayIterator._host_states

This example demonstrates the problem with PlayIterator exposing _host_states
as a private attribute without public methods for controlled access.

PROBLEM:
- PlayIterator._host_states is private but accessed directly by external code
- No public methods to set/modify host states in a controlled manner
- No type validation when manipulating states
- External code like strategy plugins need to manipulate states but have no clean API

EXPECTED:
- Public methods like set_state_for_host(), set_run_state_for_host()
- Type validation for state changes
- Controlled manipulation of host states
- Proper encapsulation
"""

import logging

from ansible_simulator.shared.models import (
    Host, Inventory, Playbook, Play, Task
)
from ansible_simulator.components.executor import PlayIterator, HostState

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def demonstrate_problem():
    """Demonstrate the lack of public API for host state manipulation."""

    logger.info("=" * 80)
    logger.info("PROBLEM 5c225dc0: Lack of Public Methods for PlayIterator._host_states")
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
        ]
    )

    # Create iterator
    iterator = PlayIterator(play=play, inventory=inventory)

    logger.info("PROBLEM 1: host_states is public but should have controlled access")
    logger.info("-" * 80)
    logger.info(f"Type: {type(iterator.host_states)}")
    logger.info(f"Available: {hasattr(iterator, 'host_states')}")
    logger.info("")
    logger.info("❌ host_states is directly accessible - no encapsulation")
    logger.info("❌ External code (strategy plugins, executors) access it directly")
    logger.info("")

    logger.info("PROBLEM 2: No public methods to manipulate states")
    logger.info("-" * 80)
    logger.info("Current way to set a host's state (direct manipulation):")
    logger.info("")
    logger.info("  # Strategy plugin wants to set host state")
    logger.info("  iterator.host_states['web1'].run_state = 2  # Direct manipulation!")
    logger.info("  iterator.host_states['web1'].fail_state = 1")
    logger.info("")

    # Demonstrate direct manipulation (the problem!)
    print("Demonstrating direct manipulation:")
    print(f"  Before: {iterator.host_states['web1']}")

    # PROBLEM: Direct manipulation without validation
    iterator.host_states['web1'].run_state = 99  # Invalid state!
    iterator.host_states['web1'].fail_state = -1  # Invalid state!

    print(f"  After: {iterator.host_states['web1']}")
    logger.info("")
    logger.info("❌ No validation! Set run_state=99 (invalid) and fail_state=-1 (invalid)")
    logger.info("❌ Code can set invalid states without any checks")
    logger.info("")

    logger.info("PROBLEM 3: No methods to set complete state")
    logger.info("-" * 80)
    logger.info("What's needed:")
    logger.info("")
    logger.info("  # Desired public API")
    logger.info("  iterator.set_state_for_host(host, state)")
    logger.info("  iterator.set_run_state_for_host(host, run_state)")
    logger.info("  iterator.set_fail_state_for_host(host, fail_state)")
    logger.info("  iterator.get_state_for_host(host)")
    logger.info("")
    logger.info("❌ None of these methods exist!")
    logger.info("")

    logger.info("PROBLEM 4: Can't intercept or log state changes")
    logger.info("-" * 80)
    logger.info("Without public methods:")
    logger.info("  - Can't log when states change")
    logger.info("  - Can't validate state transitions")
    logger.info("  - Can't trigger side effects on state changes")
    logger.info("  - Hard to debug state-related issues")
    logger.info("")

    logger.info("PROBLEM 5: Direct dict manipulation is error-prone")
    logger.info("-" * 80)
    logger.info("Example errors that can happen:")
    logger.info("")

    try:
        # Try to access non-existent host
        iterator.host_states['nonexistent'].run_state = 1
    except KeyError as e:
        logger.info(f"  KeyError when accessing non-existent host: {e}")

    logger.info("")
    logger.info("❌ No protection against accessing invalid hosts")
    logger.info("❌ No default/safe handling")
    logger.info("")

    logger.info("PROBLEM 6: Type safety is missing")
    logger.info("-" * 80)
    logger.info("Can assign anything to host_states:")
    logger.info("")

    # PROBLEM: Can assign wrong type
    iterator.host_states['web2'] = "not a HostState object!"  # type: ignore[assignment]  # Wrong type!
    print(f"  Assigned string to host_states['web2']: {iterator.host_states['web2']}")

    logger.info("")
    logger.info("❌ No type checking! Assigned a string instead of HostState")
    logger.info("❌ Will cause runtime errors later when code expects HostState")
    logger.info("")

    # Fix it for demonstration
    iterator.host_states['web2'] = HostState(
        host_name='web2',
        run_state=iterator.ITERATING_SETUP
    )

    logger.info("SOLUTION NEEDED:")
    logger.info("-" * 80)
    logger.info("✅ Add public instance method: set_state_for_host(host, state)")
    logger.info("✅ Add public instance method: set_run_state_for_host(host, run_state)")
    logger.info("✅ Add public instance method: set_fail_state_for_host(host, fail_state)")
    logger.info("✅ Add public instance method: get_state_for_host(host)")
    logger.info("✅ Validate state types and values")
    logger.info("✅ Handle missing hosts gracefully")
    logger.info("✅ Enable logging/debugging of state changes")
    logger.info("")

    logger.info("Example of desired API:")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  # Clean, validated API")
    logger.info("  iterator.set_run_state_for_host(")
    logger.info("      host=host_obj,")
    logger.info("      run_state=IteratingState.ITERATING_TASKS  # Type-safe!")
    logger.info("  )")
    logger.info("")
    logger.info("  state = iterator.get_state_for_host(host_obj)")
    logger.info("  if state.run_state == IteratingState.ITERATING_SETUP:")
    logger.info("      # ...")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Direct _host_states access causes:")
    logger.info("  1. No encapsulation")
    logger.info("  2. No validation")
    logger.info("  3. No type safety")
    logger.info("  4. Error-prone direct manipulation")
    logger.info("  5. Can't log or intercept changes")
    logger.info("  6. Hard to maintain and extend")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
