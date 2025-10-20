"""
Strategy Comparison Example.

Demonstrates the difference between Linear and Free strategies
by running the same playbook with both strategies and comparing
execution time and behavior.
"""

import simpy
import logging
from typing import Dict, Optional

from simulator.infra.network import Network
from simulator.infra.machine import Machine

from ansible_simulator.shared.models import (
    Host, Inventory, Playbook, Play, Task
)
from ansible_simulator.components.control_node import ControlNode
from ansible_simulator.components.managed_host import ManagedHost

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class StrategyComparisonSimulation:
    """Compare Linear vs Free strategies."""

    def __init__(self, num_hosts: int = 6):
        self.num_hosts = num_hosts
        self.env = simpy.Environment()
        self.network = Network(self.env, latency_mean=0.02, latency_std=0.005)

        self.machines: Dict[str, Machine] = {}
        self.managed_hosts: Dict[str, ManagedHost] = {}
        self.control_node: Optional[ControlNode] = None

        self._setup()

    def _setup(self):
        """Set up infrastructure."""
        # Create machines
        for i in range(self.num_hosts):
            machine_id = f"machine-{i+1}"
            self.machines[machine_id] = Machine(id=machine_id, az="az-1")

        control_machine = Machine(id="control-machine", az="az-1")
        self.machines["control-machine"] = control_machine

        # Create inventory
        inventory = Inventory()

        # Create managed hosts
        for i in range(self.num_hosts):
            host_name = f"host-{i+1}"
            machine_id = f"machine-{i+1}"

            host_info = Host(
                name=host_name,
                ansible_host=host_name,
                ansible_connection="ssh"
            )

            inventory.add_host(host_info)

            managed_host = ManagedHost(
                id=host_name,
                env=self.env,
                network=self.network,
                machine=self.machines[machine_id],
                host_info=host_info
            )

            self.managed_hosts[host_name] = managed_host

        # Create control node
        self.control_node = ControlNode(
            id="control_node",
            env=self.env,
            network=self.network,
            machine=self.machines["control-machine"],
            inventory=inventory,
            forks=3  # Limit forks to see strategy differences
        )

    def _create_test_playbook(self, strategy: str) -> Playbook:
        """Create a playbook with tasks of varying duration."""
        return Playbook(plays=[
            Play(
                name=f"Test Play ({strategy} strategy)",
                hosts="all",
                gather_facts=True,
                strategy=strategy,
                tasks=[
                    Task(
                        name="Quick task - ping",
                        action="ping"
                    ),
                    Task(
                        name="Medium task - install package",
                        action="apt",
                        args={"name": "nginx", "state": "present"}
                    ),
                    Task(
                        name="Long task - clone repository",
                        action="git",
                        args={
                            "repo": "https://github.com/example/repo.git",
                            "dest": "/opt/app"
                        }
                    ),
                    Task(
                        name="Quick task - create directory",
                        action="file",
                        args={"path": "/data", "state": "directory"}
                    ),
                    Task(
                        name="Medium task - copy file",
                        action="copy",
                        args={
                            "content": "test content",
                            "dest": "/tmp/test.txt"
                        }
                    )
                ]
            )
        ])

    def run_comparison(self):
        """Run both strategies and compare."""
        assert self.control_node is not None
        logger.info("=" * 80)
        logger.info("ANSIBLE STRATEGY COMPARISON SIMULATION")
        logger.info("=" * 80)
        logger.info(f"Hosts: {self.num_hosts}")
        logger.info(f"Forks: {self.control_node.forks}")
        logger.info("")

        # Test Linear Strategy
        self.env.process(self._test_linear_strategy())

        # Wait between tests
        self.env.process(self._wait_and_test_free_strategy())

        # Run simulation
        self.env.run(until=120.0)

        logger.info("")
        logger.info("=" * 80)
        logger.info("COMPARISON COMPLETE")
        logger.info("=" * 80)

    def _test_linear_strategy(self):
        """Test linear strategy."""
        assert self.control_node is not None
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: LINEAR STRATEGY")
        logger.info("=" * 80)
        logger.info("\nLinear strategy executes tasks in lockstep:")
        logger.info("- All hosts complete task N before any host starts task N+1")
        logger.info("- Ensures consistency across hosts")
        logger.info("- May be slower if hosts have different performance")
        logger.info("")

        start_time = self.env.now

        playbook = self._create_test_playbook("linear")
        stats = yield from self.control_node.ansible_playbook(playbook)

        duration = self.env.now - start_time

        logger.info("\n" + "-" * 80)
        logger.info("LINEAR STRATEGY RESULTS")
        logger.info("-" * 80)
        logger.info(f"Total Duration: {duration:.3f}s")
        logger.info(f"Total Tasks: {stats.total_tasks}")
        logger.info(f"Tasks OK: {stats.play_stats[0].tasks_ok}")
        logger.info(f"Tasks Changed: {stats.play_stats[0].tasks_changed}")
        logger.info("")
        logger.info("Observation: Notice how tasks complete in waves,")
        logger.info("with all hosts finishing each task before moving to the next.")
        logger.info("")

    def _wait_and_test_free_strategy(self):
        """Wait and then test free strategy."""
        assert self.control_node is not None
        yield self.env.timeout(30.0)

        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: FREE STRATEGY")
        logger.info("=" * 80)
        logger.info("\nFree strategy allows independent host execution:")
        logger.info("- Each host proceeds through tasks independently")
        logger.info("- Maximum parallelism within fork limit")
        logger.info("- Better for heterogeneous environments")
        logger.info("")

        start_time = self.env.now

        playbook = self._create_test_playbook("free")
        stats = yield from self.control_node.ansible_playbook(playbook)

        duration = self.env.now - start_time

        logger.info("\n" + "-" * 80)
        logger.info("FREE STRATEGY RESULTS")
        logger.info("-" * 80)
        logger.info(f"Total Duration: {duration:.3f}s")
        logger.info(f"Total Tasks: {stats.total_tasks}")
        logger.info(f"Tasks OK: {stats.play_stats[0].tasks_ok}")
        logger.info(f"Tasks Changed: {stats.play_stats[0].tasks_changed}")
        logger.info("")
        logger.info("Observation: Hosts complete at different times,")
        logger.info("faster hosts don't wait for slower ones.")
        logger.info("")


def main():
    """Run the comparison."""
    sim = StrategyComparisonSimulation(num_hosts=6)
    sim.run_comparison()


if __name__ == "__main__":
    main()
