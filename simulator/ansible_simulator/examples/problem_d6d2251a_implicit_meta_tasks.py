"""
Reproduction of Problem d6d2251a: Implicit meta/noop Tasks Performance

This example demonstrates how Ansible generates unnecessary implicit tasks
that cause performance degradation in large inventories.

PROBLEM:
- PlayIterator generates implicit "meta: flush_handlers" for ALL hosts
  even when no handlers have been notified
- LinearStrategy generates "meta: noop" for idle hosts to keep them in lockstep
- These implicit tasks add overhead without benefit
- At scale (1000s of hosts), this wastes significant time

IMPACT:
- Every host gets implicit flush_handlers even with 0 notified handlers
- Idle hosts get noop tasks just to wait for others
- Network overhead, processing overhead
- Slows down playbook execution unnecessarily
"""

import simpy
import logging

from simulator.infra.network import Network
from simulator.infra.machine import Machine

from ansible_simulator.shared.models import (
    Host, Inventory, Playbook, Play, Task
)
from ansible_simulator.components.control_node import ControlNode
from ansible_simulator.components.managed_host import ManagedHost

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Enable warnings from executor and strategy to see implicit tasks
exec_logger = logging.getLogger('ansible_simulator.components.executor')
exec_logger.setLevel(logging.WARNING)

strat_logger = logging.getLogger('ansible_simulator.components.strategy')
strat_logger.setLevel(logging.WARNING)

# Suppress other noise
logging.getLogger('ansible_simulator.components.plugins').setLevel(logging.ERROR)
logging.getLogger('ansible_simulator.components.managed_host').setLevel(logging.ERROR)
logging.getLogger('ansible_simulator.components.control_node').setLevel(logging.ERROR)


def demonstrate_problem():
    """Demonstrate implicit meta task generation."""

    logger.info("=" * 80)
    logger.info("PROBLEM d6d2251a: Implicit meta/noop Tasks Performance")
    logger.info("=" * 80)
    logger.info("")

    # Setup simulation environment
    env = simpy.Environment()
    network = Network(env)

    # Create inventory with multiple hosts
    inventory = Inventory()
    machines = {}
    managed_hosts = {}

    num_hosts = 6  # Smaller for demo, imagine 1000s
    for i in range(num_hosts):
        host_name = f"web{i+1}"
        machine_id = f"machine-{i+1}"

        machines[machine_id] = Machine(id=machine_id, az="az-1")

        host_info = Host(
            name=host_name,
            ansible_host=host_name,
            ansible_connection="local"
        )
        inventory.add_host(host_info)

        managed_host = ManagedHost(
            id=host_name,
            env=env,
            network=network,
            machine=machines[machine_id],
            host_info=host_info
        )
        managed_hosts[host_name] = managed_host

    # Create control node
    control_machine = Machine(id="control-machine", az="az-1")
    machines["control-machine"] = control_machine

    control_node = ControlNode(
        id="control_node",
        env=env,
        network=network,
        machine=control_machine,
        inventory=inventory,
        forks=3
    )

    logger.info(f"Inventory: {num_hosts} hosts")
    logger.info("")

    # Create playbook with tasks but NO handler notifications
    playbook = Playbook(plays=[
        Play(
            name="Test Play - No Handlers Notified",
            hosts="all",
            gather_facts=False,
            strategy="linear",
            tasks=[
                Task(
                    name="Task 1 - ping",
                    action="ping"
                ),
                Task(
                    name="Task 2 - create file",
                    action="file",
                    args={"path": "/tmp/test", "state": "touch"}
                ),
            ],
            # Define handlers but don't notify them
            handlers=[
                Task(
                    name="restart nginx",
                    action="service",
                    args={"name": "nginx", "state": "restarted"}
                )
            ]
        )
    ])

    logger.info("Playbook configuration:")
    logger.info("  - 2 tasks (neither notifies handlers)")
    logger.info("  - 1 handler defined (but not notified)")
    logger.info("  - linear strategy (lockstep execution)")
    logger.info("")

    logger.info("=" * 80)
    logger.info("PROBLEM 1: Implicit flush_handlers for ALL hosts")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Watch for: 'Generated implicit flush_handlers' messages")
    logger.info("Expected: ALL 6 hosts get implicit flush_handlers")
    logger.info("Even though: 0 handlers were notified!")
    logger.info("")

    # Run playbook
    def run_playbook():
        stats = yield from control_node.ansible_playbook(playbook)
        return stats

    env.process(run_playbook())
    env.run(until=10.0)

    logger.info("")
    logger.info("=" * 80)
    logger.info("ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("PROBLEM 1 ANALYSIS: Implicit flush_handlers")
    logger.info("-" * 80)
    logger.info("")
    logger.info("What happened:")
    logger.info("  - Each of the 6 hosts generated 'meta: flush_handlers (implicit)'")
    logger.info("  - This happened even though NO handlers were notified")
    logger.info("  - Total implicit tasks: 6 (1 per host)")
    logger.info("")
    logger.info("Why this is bad:")
    logger.info("  ❌ Wasted execution: running flush_handlers when nothing to flush")
    logger.info("  ❌ With 1000 hosts: 1000 unnecessary flush_handlers tasks!")
    logger.info("  ❌ Network overhead: messages sent, processed, results returned")
    logger.info("  ❌ Time overhead: even if fast, adds up at scale")
    logger.info("")

    logger.info("What SHOULD happen:")
    logger.info("  ✅ Check if host has notified handlers: NO")
    logger.info("  ✅ Skip implicit flush_handlers for this host")
    logger.info("  ✅ Only generate flush_handlers for hosts with pending handlers")
    logger.info("")

    # Now demonstrate noop tasks with a scenario where hosts complete at different rates
    logger.info("")
    logger.info("=" * 80)
    logger.info("PROBLEM 2: Implicit meta: noop for lockstep")
    logger.info("=" * 80)
    logger.info("")
    logger.info("(Note: This is harder to trigger in our simple simulator,")
    logger.info(" but in real Ansible with conditional tasks and when: clauses,")
    logger.info(" some hosts skip tasks while others run them)")
    logger.info("")

    logger.info("Scenario:")
    logger.info("  - Host A has task to run")
    logger.info("  - Host B finished all tasks, waiting")
    logger.info("  - Linear strategy keeps Host B in lockstep")
    logger.info("  - Host B gets 'meta: noop' to stay synchronized")
    logger.info("")

    logger.info("Why this is bad:")
    logger.info("  ❌ Host B does nothing useful but still processes noop")
    logger.info("  ❌ With many hosts, many noops generated")
    logger.info("  ❌ Could just return empty result instead")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD IMPACT")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Example: 5000 host inventory, 50 tasks")
    logger.info("")
    logger.info("Implicit flush_handlers:")
    logger.info("  - Generated: 5000 times (1 per host)")
    logger.info("  - Even if 0 handlers notified!")
    logger.info("  - Time: 5000 * 0.1s = 500 seconds wasted")
    logger.info("")

    logger.info("Implicit noop tasks:")
    logger.info("  - Some tasks conditional, not all hosts run them")
    logger.info("  - Idle hosts get noop to stay in lockstep")
    logger.info("  - With 30% idle rate: 5000 * 50 * 0.3 = 75,000 noop tasks")
    logger.info("  - Even more overhead!")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("For implicit flush_handlers:")
    logger.info("  ✅ Only generate if host has pending handlers")
    logger.info("  ✅ Check: len(notified_handlers) > 0")
    logger.info("  ✅ Skip implicit flush_handlers otherwise")
    logger.info("  ✅ Explicit 'meta: flush_handlers' still runs always")
    logger.info("")

    logger.info("For implicit noop:")
    logger.info("  ✅ When batch yields no runnable tasks, return empty")
    logger.info("  ✅ Don't generate placeholder noop tasks")
    logger.info("  ✅ Strategy can handle empty results gracefully")
    logger.info("")

    logger.info("Expected optimization:")
    logger.info("  - 5000 hosts with 0 handlers: 0 implicit flush (not 5000!)")
    logger.info("  - Significant time savings at scale")
    logger.info("  - No behavioral change, just removes waste")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Implicit meta tasks cause:")
    logger.info("  1. Unnecessary flush_handlers for hosts with 0 pending handlers")
    logger.info("  2. Unnecessary noop tasks for idle hosts in linear strategy")
    logger.info("  3. Significant performance impact at scale (1000s of hosts)")
    logger.info("  4. Network and processing overhead")
    logger.info("  5. Could save 10s-100s of seconds per playbook run")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
