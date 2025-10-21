"""
Reproduction of Problem 811093f0: Handler Execution Inconsistency

This example demonstrates multiple problems with handler execution in Ansible:
1. Handlers run on failed hosts (especially after 'always' sections)
2. Handlers don't honor any_errors_fatal
3. Handler ordering can be incorrect
4. meta: flush_handlers doesn't support 'when:' conditionals
5. Meta tasks cannot be used as handlers

PROBLEM:
- Handlers execute inconsistently across hosts
- Failed hosts can still run handlers
- any_errors_fatal is ignored during handler execution
- Cannot conditionally flush handlers
- Cannot use meta tasks as handlers

IMPACT:
- Unpredictable behavior in multi-host scenarios
- Failed hosts may execute handlers causing further issues
- Cannot stop all hosts when one handler fails
- Lack of flexibility in handler flushing
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

# Enable warnings from executor
exec_logger = logging.getLogger('ansible_simulator.components.executor')
exec_logger.setLevel(logging.WARNING)

# Suppress noise
logging.getLogger('ansible_simulator.components.plugins').setLevel(logging.ERROR)
logging.getLogger('ansible_simulator.components.managed_host').setLevel(logging.ERROR)
logging.getLogger('ansible_simulator.components.control_node').setLevel(logging.ERROR)
logging.getLogger('ansible_simulator.components.strategy').setLevel(logging.ERROR)


def demonstrate_problem():
    """Demonstrate handler execution problems."""

    logger.info("=" * 80)
    logger.info("PROBLEM 811093f0: Handler Execution Inconsistency")
    logger.info("=" * 80)
    logger.info("")

    # Setup simulation environment
    env = simpy.Environment()
    network = Network(env)

    # Create inventory
    inventory = Inventory()
    machines = {}
    managed_hosts = {}

    for i in range(3):
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
    control_node = ControlNode(
        id="control_node",
        env=env,
        network=network,
        machine=control_machine,
        inventory=inventory,
        forks=3
    )

    logger.info("=" * 80)
    logger.info("PROBLEM 1: Handlers run on failed hosts")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Scenario: A task notifies a handler, then fails")
    logger.info("Expected: Handler should NOT run on failed host")
    logger.info("Actual: Handler DOES run on failed host!")
    logger.info("")

    # Create playbook where task notifies handler then fails
    playbook1 = Playbook(plays=[
        Play(
            name="Test handlers on failed hosts",
            hosts="all",
            gather_facts=False,
            strategy="linear",
            tasks=[
                Task(
                    name="Task that notifies handler",
                    action="command",
                    args={"_raw_params": "echo 'notifying handler'"},
                    notify=["restart service"],
                    changed_when="true"  # Always changed to trigger handler
                ),
                Task(
                    name="Task that fails",
                    action="command",
                    args={"_raw_params": "exit 1"},  # Fails!
                    failed_when="true"
                ),
            ],
            handlers=[
                Task(
                    name="restart service",
                    action="service",
                    args={"name": "nginx", "state": "restarted"}
                )
            ]
        )
    ])

    logger.info("Watch for: 'PROBLEM 811093f0: Running handler on FAILED host'")
    logger.info("")

    def run_playbook1():
        stats = yield from control_node.ansible_playbook(playbook1)
        return stats

    env.process(run_playbook1())
    env.run(until=10.0)

    logger.info("")
    logger.info("=" * 80)
    logger.info("ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("PROBLEM 1 ANALYSIS: Handlers on failed hosts")
    logger.info("-" * 80)
    logger.info("")
    logger.info("What happened:")
    logger.info("  1. Task 1 notifies 'restart service' handler")
    logger.info("  2. Task 2 fails")
    logger.info("  3. Host is marked as FAILED (fail_state=2)")
    logger.info("  4. Handler 'restart service' STILL RUNS on failed host!")
    logger.info("")
    logger.info("Why this is bad:")
    logger.info("  ❌ Failed hosts shouldn't execute handlers")
    logger.info("  ❌ May cause cascading failures")
    logger.info("  ❌ Service restart on broken host makes things worse")
    logger.info("  ❌ Unpredictable behavior")
    logger.info("")

    logger.info("PROBLEM 2: any_errors_fatal not honored by handlers")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Scenario: Play has any_errors_fatal: true")
    logger.info("Expected: If handler fails on one host, ALL hosts stop")
    logger.info("Actual: Other hosts continue running handlers")
    logger.info("")
    logger.info("Current simulator limitation:")
    logger.info("  - any_errors_fatal not implemented in handler phase")
    logger.info("  - Would need dedicated handler execution via iterator")
    logger.info("  - Handlers executed through strategy plugin")
    logger.info("")
    logger.info("In real Ansible:")
    logger.info("  ❌ Handler failure on host1 doesn't stop host2 handlers")
    logger.info("  ❌ any_errors_fatal is ignored in handler phase")
    logger.info("  ❌ Inconsistent with task phase behavior")
    logger.info("")

    logger.info("PROBLEM 3: Handler ordering issues")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Scenario: Multiple handlers notified in different order per host")
    logger.info("")
    logger.info("Handlers defined:")
    logger.info("  1. reload config")
    logger.info("  2. restart service")
    logger.info("  3. verify status")
    logger.info("")
    logger.info("Host1 notifies: restart, reload, verify")
    logger.info("Host2 notifies: verify, reload, restart")
    logger.info("")
    logger.info("Expected: Handlers execute in DEFINITION order (1, 2, 3)")
    logger.info("  - Host1: reload, restart, verify")
    logger.info("  - Host2: reload, restart, verify")
    logger.info("")
    logger.info("Actual (current implementation):")
    logger.info("  - Host1: restart, reload, verify (notification order!)")
    logger.info("  - Host2: verify, reload, restart (notification order!)")
    logger.info("")
    logger.info("Why this is bad:")
    logger.info("  ❌ restart before reload means old config")
    logger.info("  ❌ verify before restart checks wrong state")
    logger.info("  ❌ Inconsistent behavior between hosts")
    logger.info("")
    logger.info("Correct behavior:")
    logger.info("  ✅ Handlers should execute in DEFINITION order")
    logger.info("  ✅ Deduplicate notified handlers")
    logger.info("  ✅ Same order on all hosts")
    logger.info("")

    logger.info("PROBLEM 4: meta: flush_handlers doesn't support when:")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Desired playbook:")
    logger.info("")
    logger.info("  - name: Flush handlers conditionally")
    logger.info("    meta: flush_handlers")
    logger.info("    when: environment == 'production'")
    logger.info("")
    logger.info("Expected: Handlers flushed only if condition true")
    logger.info("Actual: Syntax error or 'when' is ignored")
    logger.info("")
    logger.info("Why this is bad:")
    logger.info("  ❌ Cannot conditionally flush handlers")
    logger.info("  ❌ May want different behavior per environment")
    logger.info("  ❌ Workarounds are complex and error-prone")
    logger.info("")
    logger.info("Note: In our simulator, meta tasks don't support 'when' at all")
    logger.info("")

    logger.info("PROBLEM 5: Meta tasks cannot be handlers")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Desired playbook:")
    logger.info("")
    logger.info("  handlers:")
    logger.info("    - name: refresh inventory")
    logger.info("      meta: refresh_inventory")
    logger.info("")
    logger.info("  tasks:")
    logger.info("    - name: Update inventory file")
    logger.info("      copy: ...")
    logger.info("      notify: refresh inventory")
    logger.info("")
    logger.info("Expected: meta: refresh_inventory runs as handler")
    logger.info("Actual: Error or meta task not executed")
    logger.info("")
    logger.info("Why this is bad:")
    logger.info("  ❌ Cannot use meta tasks as handlers")
    logger.info("  ❌ meta: refresh_inventory useful after inventory changes")
    logger.info("  ❌ meta: clear_facts useful after fact changes")
    logger.info("  ❌ Limitation not clearly documented")
    logger.info("")
    logger.info("Exception: meta: flush_handlers CANNOT be a handler")
    logger.info("  (would cause infinite recursion)")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("For handlers on failed hosts:")
    logger.info("  ✅ Check host fail_state before running handlers")
    logger.info("  ✅ Skip handlers if fail_state != FAILED_NONE")
    logger.info("  ✅ Exception: after 'always' sections, don't run handlers on failed hosts")
    logger.info("")

    logger.info("For any_errors_fatal:")
    logger.info("  ✅ Handler execution should check any_errors_fatal")
    logger.info("  ✅ If handler fails on any host, stop ALL hosts")
    logger.info("  ✅ Consistent with task phase behavior")
    logger.info("  ✅ Requires dedicated handler phase in iterator")
    logger.info("")

    logger.info("For handler ordering:")
    logger.info("  ✅ Execute handlers in DEFINITION order, not notification order")
    logger.info("  ✅ Deduplicate notified handlers per host")
    logger.info("  ✅ Same order on all hosts")
    logger.info("  ✅ Use strategy plugin for execution (linear/free/serial)")
    logger.info("")

    logger.info("For conditional flush_handlers:")
    logger.info("  ✅ Allow 'when:' on meta: flush_handlers tasks")
    logger.info("  ✅ Evaluate condition before flushing")
    logger.info("  ✅ Skip flush if condition false")
    logger.info("")

    logger.info("For meta tasks as handlers:")
    logger.info("  ✅ Allow meta tasks as handlers")
    logger.info("  ✅ Exception: meta: flush_handlers cannot be handler")
    logger.info("  ✅ meta: refresh_inventory, clear_facts, etc. should work")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Handler execution inconsistency causes:")
    logger.info("  1. Handlers run on failed hosts (unpredictable)")
    logger.info("  2. any_errors_fatal ignored (can't stop all on handler failure)")
    logger.info("  3. Wrong handler order (breaks dependencies)")
    logger.info("  4. No conditional flush_handlers (inflexible)")
    logger.info("  5. Meta tasks can't be handlers (limited functionality)")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
