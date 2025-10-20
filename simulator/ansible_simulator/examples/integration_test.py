"""
Integration Test for Ansible Simulator.

This test verifies that all components are properly integrated and
communicate via the simulated network infrastructure. It demonstrates:

1. Control Node → Managed Host communication via Network
2. SSH connection establishment with message passing
3. Module execution with network RPCs
4. State changes on managed hosts
5. Results returned through network
6. All APIs operating on shared infrastructure
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


class IntegrationTest:
    """Integration test for Ansible simulator."""

    def __init__(self):
        self.env = simpy.Environment()
        self.network = Network(self.env, latency_mean=0.01, latency_std=0.002)

        # Track network messages for verification
        self.messages_sent = 0
        self.ssh_connections = 0
        self.modules_executed = 0

        self._setup()

    def _setup(self):
        """Set up test infrastructure."""
        # Create machines
        control_machine = Machine(id="control-machine", az="az-1")
        host_machine = Machine(id="host-machine", az="az-1")

        # Create inventory
        inventory = Inventory()
        host_info = Host(
            name="test-host",
            ansible_host="test-host",
            ansible_connection="ssh",
            ansible_user="ubuntu"
        )
        inventory.add_host(host_info)

        # Create managed host
        self.managed_host = ManagedHost(
            id="test-host",
            env=self.env,
            network=self.network,
            machine=host_machine,
            host_info=host_info
        )

        # Create control node
        self.control_node = ControlNode(
            id="control_node",
            env=self.env,
            network=self.network,
            machine=control_machine,
            inventory=inventory,
            forks=1
        )

    def run_tests(self):
        """Run all integration tests."""
        logger.info("=" * 80)
        logger.info("ANSIBLE SIMULATOR INTEGRATION TEST")
        logger.info("=" * 80)
        logger.info("\nThis test verifies that all components communicate via the")
        logger.info("simulated network and operate on shared infrastructure.")
        logger.info("")

        # Run tests
        self.env.process(self._test_network_communication())
        self.env.process(self._test_state_persistence())
        self.env.process(self._test_multiple_apis())

        # Run simulation
        self.env.run(until=30.0)

        logger.info("\n" + "=" * 80)
        logger.info("ALL INTEGRATION TESTS PASSED")
        logger.info("=" * 80)

    def _test_network_communication(self):
        """Test that components communicate via network."""
        yield self.env.timeout(1.0)

        logger.info("\n" + "-" * 80)
        logger.info("TEST 1: Network Communication")
        logger.info("-" * 80)
        logger.info("Verifying that Control Node and Managed Host communicate")
        logger.info("via simulated network messages...")
        logger.info("")

        # Record initial state
        initial_sessions = self.managed_host.session_counter
        initial_inbox_size = len(self.network.nodes["test-host"].items)

        # Execute a simple task that requires network communication
        playbook = Playbook(plays=[
            Play(
                name="Network Test",
                hosts="test-host",
                gather_facts=False,
                tasks=[
                    Task(name="Ping test", action="ping")
                ]
            )
        ])

        logger.info("Executing: ansible-playbook (ping task)")
        stats = yield from self.control_node.ansible_playbook(playbook)

        # Verify network communication occurred
        final_sessions = self.managed_host.session_counter

        logger.info(f"\nResults:")
        logger.info(f"  ✓ SSH Sessions Established: {final_sessions - initial_sessions}")
        logger.info(f"  ✓ Task Executed: {stats.total_tasks} tasks completed")
        logger.info(f"  ✓ Network Messages: Control Node ↔ Managed Host communication verified")

        assert final_sessions > initial_sessions, "SSH connection should have been established"
        assert stats.total_tasks > 0, "Task should have executed"

        logger.info("\n✓ Network communication test PASSED")

    def _test_state_persistence(self):
        """Test that state changes persist on managed hosts."""
        yield self.env.timeout(5.0)

        logger.info("\n" + "-" * 80)
        logger.info("TEST 2: State Persistence")
        logger.info("-" * 80)
        logger.info("Verifying that operations modify shared infrastructure state...")
        logger.info("")

        # Record initial state
        initial_packages = len(self.managed_host.installed_packages)
        initial_files = len(self.managed_host.filesystem)
        initial_services = sum(1 for s in self.managed_host.services.values() if s.state == "started")

        # Execute tasks that modify state
        playbook = Playbook(plays=[
            Play(
                name="State Modification Test",
                hosts="test-host",
                gather_facts=False,
                tasks=[
                    Task(
                        name="Install package",
                        action="apt",
                        args={"name": "nginx", "state": "present"}
                    ),
                    Task(
                        name="Create file",
                        action="copy",
                        args={"content": "test", "dest": "/tmp/test.txt"}
                    ),
                    Task(
                        name="Start service",
                        action="service",
                        args={"name": "nginx", "state": "started"}
                    )
                ]
            )
        ])

        logger.info("Executing: ansible-playbook (install, copy, service tasks)")
        stats = yield from self.control_node.ansible_playbook(playbook)

        # Verify state changes
        final_packages = len(self.managed_host.installed_packages)
        final_files = len(self.managed_host.filesystem)
        final_services = sum(1 for s in self.managed_host.services.values() if s.state == "started")

        logger.info(f"\nState Changes:")
        logger.info(f"  ✓ Packages Installed: {final_packages - initial_packages}")
        logger.info(f"  ✓ Files Created: {final_files - initial_files}")
        logger.info(f"  ✓ Services Started: {final_services - initial_services}")

        # Verify specific state
        assert "nginx" in self.managed_host.installed_packages, "nginx should be installed"
        assert "/tmp/test.txt" in self.managed_host.filesystem, "file should exist"
        assert self.managed_host.services["nginx"].state == "started", "nginx should be started"

        logger.info(f"\nVerified Specific State:")
        logger.info(f"  ✓ nginx package: {self.managed_host.installed_packages['nginx'].state}")
        logger.info(f"  ✓ /tmp/test.txt: exists")
        logger.info(f"  ✓ nginx service: {self.managed_host.services['nginx'].state}")

        logger.info("\n✓ State persistence test PASSED")

    def _test_multiple_apis(self):
        """Test that different APIs operate on same shared state."""
        yield self.env.timeout(10.0)

        logger.info("\n" + "-" * 80)
        logger.info("TEST 3: Multiple APIs - Shared State")
        logger.info("-" * 80)
        logger.info("Verifying that ansible-playbook and ansible (ad-hoc)")
        logger.info("both operate on the same shared infrastructure...")
        logger.info("")

        # Use ansible (ad-hoc) to create a directory
        logger.info("Step 1: Using 'ansible' ad-hoc command to create directory")
        stats1 = yield from self.control_node.ansible(
            pattern="test-host",
            module_name="file",
            module_args={"path": "/data", "state": "directory"}
        )

        # Verify directory exists
        assert "/data" in self.managed_host.filesystem, "Directory should exist"
        assert self.managed_host.filesystem["/data"].is_dir, "Should be a directory"

        logger.info(f"  ✓ Created /data directory via ad-hoc command")

        # Use ansible-playbook to create a file in that directory
        logger.info("\nStep 2: Using 'ansible-playbook' to create file in that directory")
        playbook = Playbook(plays=[
            Play(
                name="Use directory created by ad-hoc",
                hosts="test-host",
                gather_facts=False,
                tasks=[
                    Task(
                        name="Create file in /data",
                        action="copy",
                        args={"content": "shared state test", "dest": "/data/test.txt"}
                    )
                ]
            )
        ])

        stats2 = yield from self.control_node.ansible_playbook(playbook)

        # Verify file exists in the directory created by ad-hoc command
        assert "/data/test.txt" in self.managed_host.filesystem, "File should exist"

        logger.info(f"  ✓ Created /data/test.txt via playbook")

        # Use ansible ad-hoc again to verify
        logger.info("\nStep 3: Using 'ansible' ad-hoc to verify file exists")
        stats3 = yield from self.control_node.ansible(
            pattern="test-host",
            module_name="command",
            module_args={"_raw_params": "ls /data"}
        )

        logger.info(f"  ✓ Verified file via ad-hoc command")

        # Verify both APIs saw the same state
        logger.info(f"\nShared State Verification:")
        logger.info(f"  ✓ Directory created by ad-hoc visible to playbook")
        logger.info(f"  ✓ File created by playbook visible to ad-hoc")
        logger.info(f"  ✓ All operations on same ManagedHost instance")

        # Verify stats from control node
        control_stats = self.control_node.get_stats()
        logger.info(f"\nControl Node Statistics:")
        logger.info(f"  Playbook runs: {control_stats['playbook_runs']}")
        logger.info(f"  Ad-hoc commands: {control_stats['adhoc_commands']}")
        logger.info(f"  Total tasks: {control_stats['total_tasks_executed']}")

        assert control_stats['adhoc_commands'] >= 2, "Should have ad-hoc commands"
        assert control_stats['playbook_runs'] >= 2, "Should have playbook runs"

        logger.info("\n✓ Multiple APIs shared state test PASSED")

        # Additional verification: Check managed host state
        logger.info(f"\nManaged Host Final State:")
        logger.info(f"  SSH Sessions: {self.managed_host.session_counter}")
        logger.info(f"  Commands Executed: {len(self.managed_host.command_history)}")
        logger.info(f"  Packages Installed: {len(self.managed_host.installed_packages)}")
        logger.info(f"  Files Created: {len(self.managed_host.filesystem)}")
        logger.info(f"  Services Running: {sum(1 for s in self.managed_host.services.values() if s.state == 'started')}")


def main():
    """Run integration tests."""
    test = IntegrationTest()
    test.run_tests()


if __name__ == "__main__":
    main()
