"""
Main Ansible Simulator Runner.

This module provides a complete simulation of Ansible's architecture,
demonstrating all user-facing APIs and component interactions.
"""

import simpy
import argparse
import logging
from typing import Dict, Optional

from simulator.infra.network import Network
from simulator.infra.machine import Machine
from simulator.infra.availability_zone import AvailabilityZone

from ansible_simulator.shared.models import (
    Host, Group, Inventory, Playbook, Play, Task
)
from ansible_simulator.components.control_node import ControlNode
from ansible_simulator.components.managed_host import ManagedHost

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class AnsibleSimulation:
    """
    Complete Ansible simulation.

    Simulates:
    - Ansible control node with all CLI APIs
    - Multiple managed hosts
    - Network communication
    - Playbook execution
    - Ad-hoc commands
    - Inventory management
    """

    def __init__(self, args):
        self.args = args
        self.env = simpy.Environment()
        self.network = Network(
            self.env,
            latency_mean=args.network_latency,
            latency_std=args.network_latency * 0.2
        )

        # Infrastructure
        self.machines: Dict[str, Machine] = {}
        self.azs: Dict[str, AvailabilityZone] = {}

        # Ansible components
        self.control_node: Optional[ControlNode] = None
        self.managed_hosts: Dict[str, ManagedHost] = {}

        self._setup_infrastructure()
        self._setup_ansible()

    def _setup_infrastructure(self):
        """Set up simulated infrastructure."""
        logger.info("=" * 70)
        logger.info("Setting up infrastructure...")
        logger.info("=" * 70)

        # Create availability zones
        for i in range(self.args.num_azs):
            az_id = f"az-{i+1}"
            az = AvailabilityZone(id=az_id)
            self.azs[az_id] = az
            logger.info(f"Created availability zone: {az_id}")

        # Create machines for managed hosts
        hosts_per_az = self.args.num_hosts // self.args.num_azs
        for i in range(self.args.num_azs):
            az_id = f"az-{i+1}"
            for j in range(hosts_per_az):
                machine_id = f"machine-{az_id}-{j+1}"
                machine = Machine(id=machine_id, az=az_id)
                self.machines[machine_id] = machine
                self.azs[az_id].add_machine(machine)
                logger.info(f"Created machine: {machine_id} in {az_id}")

        # Create control node machine
        control_machine = Machine(id="control-machine", az="az-1")
        self.machines["control-machine"] = control_machine
        logger.info(f"Created control node machine: control-machine")

        logger.info("")

    def _setup_ansible(self):
        """Set up Ansible components."""
        logger.info("=" * 70)
        logger.info("Setting up Ansible components...")
        logger.info("=" * 70)

        # Create inventory
        inventory = Inventory()

        # Add groups
        inventory.add_group(Group(name="all", hosts=[]))
        inventory.add_group(Group(name="webservers", hosts=[]))
        inventory.add_group(Group(name="databases", hosts=[]))
        inventory.add_group(Group(name="loadbalancers", hosts=[]))

        # Create managed hosts
        machine_ids = [m for m in self.machines.keys() if m != "control-machine"]

        for i, machine_id in enumerate(machine_ids):
            host_name = f"host-{i+1}"

            # Determine groups
            groups = []
            if i < len(machine_ids) // 3:
                groups.append("webservers")
            elif i < 2 * len(machine_ids) // 3:
                groups.append("databases")
            else:
                groups.append("loadbalancers")

            # Create host info
            host_info = Host(
                name=host_name,
                groups=groups,
                ansible_host=host_name,
                ansible_port=22,
                ansible_user="ubuntu",
                ansible_connection="ssh"
            )

            # Add to inventory
            inventory.add_host(host_info)

            # Update groups
            for group_name in groups:
                inventory.groups[group_name].hosts.append(host_name)

            # Create managed host component
            managed_host = ManagedHost(
                id=host_name,
                env=self.env,
                network=self.network,
                machine=self.machines[machine_id],
                host_info=host_info
            )

            self.managed_hosts[host_name] = managed_host

            logger.info(f"Created managed host: {host_name} (groups: {', '.join(groups)})")

        # Create control node
        self.control_node = ControlNode(
            id="control_node",
            env=self.env,
            network=self.network,
            machine=self.machines["control-machine"],
            inventory=inventory,
            forks=self.args.forks
        )

        logger.info(f"Created control node with {len(inventory.hosts)} hosts in inventory")
        logger.info("")

    def run(self, duration: float = 60.0):
        """Run the simulation."""
        logger.info("=" * 70)
        logger.info(f"Starting Ansible Simulation for {duration}s")
        logger.info("=" * 70)
        logger.info("")

        # Run demo workloads
        self.env.process(self._demo_playbook())
        self.env.process(self._demo_adhoc_commands())
        self.env.process(self._demo_inventory_commands())

        # Run simulation
        self.env.run(until=duration)

        logger.info("")
        logger.info("=" * 70)
        logger.info(f"Simulation Completed at {self.env.now:.4f}s")
        logger.info("=" * 70)
        self._report_stats()

    def _demo_playbook(self):
        """Demonstrate ansible-playbook."""
        assert self.control_node is not None
        # Wait a bit before starting
        yield self.env.timeout(1.0)

        logger.info("")
        logger.info("=" * 70)
        logger.info("DEMO: ansible-playbook")
        logger.info("=" * 70)
        logger.info("")

        # Create a sample playbook
        playbook = Playbook(
            name="Web Server Setup",
            plays=[
                Play(
                    name="Configure web servers",
                    hosts="webservers",
                    gather_facts=True,
                    strategy="linear",
                    tasks=[
                        Task(
                            name="Install nginx",
                            action="apt",
                            args={"name": "nginx", "state": "present"},
                            become=True
                        ),
                        Task(
                            name="Start nginx service",
                            action="service",
                            args={"name": "nginx", "state": "started", "enabled": True},
                            become=True
                        ),
                        Task(
                            name="Deploy nginx config",
                            action="copy",
                            args={
                                "content": "server { listen 80; }",
                                "dest": "/etc/nginx/sites-available/default"
                            },
                            become=True,
                            notify=["Reload nginx"]
                        )
                    ],
                    handlers=[
                        Task(
                            name="Reload nginx",
                            action="service",
                            args={"name": "nginx", "state": "restarted"}
                        )
                    ]
                ),
                Play(
                    name="Configure databases",
                    hosts="databases",
                    gather_facts=True,
                    strategy="linear",
                    tasks=[
                        Task(
                            name="Install postgresql",
                            action="apt",
                            args={"name": "postgresql", "state": "present"},
                            become=True
                        ),
                        Task(
                            name="Start postgresql service",
                            action="service",
                            args={"name": "postgresql", "state": "started"},
                            become=True
                        )
                    ]
                )
            ]
        )

        # Execute playbook
        stats = yield from self.control_node.ansible_playbook(
            playbook=playbook,
            forks=self.args.forks
        )

        logger.info("")
        logger.info("-" * 70)
        logger.info("Playbook Execution Complete")
        logger.info("-" * 70)
        logger.info(f"Total plays: {len(stats.play_stats)}")
        logger.info(f"Total tasks: {stats.total_tasks}")
        logger.info(f"Duration: {stats.duration:.3f}s")

        for play_stat in stats.play_stats:
            logger.info(f"\nPlay: {play_stat.play_name}")
            logger.info(f"  Tasks OK: {play_stat.tasks_ok}")
            logger.info(f"  Tasks Changed: {play_stat.tasks_changed}")
            logger.info(f"  Tasks Failed: {play_stat.tasks_failed}")
            logger.info(f"  Tasks Skipped: {play_stat.tasks_skipped}")

        logger.info("")

    def _demo_adhoc_commands(self):
        """Demonstrate ansible ad-hoc commands."""
        assert self.control_node is not None
        yield self.env.timeout(5.0)

        logger.info("")
        logger.info("=" * 70)
        logger.info("DEMO: ansible (ad-hoc commands)")
        logger.info("=" * 70)
        logger.info("")

        # Example 1: Ping all hosts
        logger.info("Running: ansible all -m ping")
        stats = yield from self.control_node.ansible(
            pattern="all",
            module_name="ping"
        )
        logger.info(f"Result: {stats.play_stats[0].tasks_ok} hosts responded")
        logger.info("")

        # Example 2: Run command on webservers
        logger.info("Running: ansible webservers -m command -a 'uptime'")
        stats = yield from self.control_node.ansible(
            pattern="webservers",
            module_name="command",
            module_args={"_raw_params": "uptime"}
        )
        logger.info(f"Result: {stats.play_stats[0].tasks_ok} hosts executed command")
        logger.info("")

        # Example 3: Create directory on databases
        logger.info("Running: ansible databases -m file -a 'path=/data state=directory'")
        stats = yield from self.control_node.ansible(
            pattern="databases",
            module_name="file",
            module_args={"path": "/data", "state": "directory"},
            become=True
        )
        logger.info(f"Result: {stats.play_stats[0].tasks_changed} hosts changed")
        logger.info("")

    def _demo_inventory_commands(self):
        """Demonstrate ansible-inventory."""
        assert self.control_node is not None
        yield self.env.timeout(10.0)

        logger.info("")
        logger.info("=" * 70)
        logger.info("DEMO: ansible-inventory")
        logger.info("=" * 70)
        logger.info("")

        # List all hosts
        inventory_info = self.control_node.ansible_inventory(pattern="all")

        logger.info(f"Total hosts: {len(inventory_info['hosts'])}")
        logger.info(f"Hosts: {', '.join(inventory_info['hosts'])}")
        logger.info(f"\nGroups: {', '.join(inventory_info['groups'])}")

        # List webservers
        webserver_info = self.control_node.ansible_inventory(pattern="webservers")
        logger.info(f"\nWebservers: {', '.join(webserver_info['hosts'])}")

        logger.info("")

    def _report_stats(self):
        """Report simulation statistics."""
        assert self.control_node is not None
        stats = self.control_node.get_stats()

        logger.info("")
        logger.info("SIMULATION STATISTICS")
        logger.info("=" * 70)
        logger.info(f"Playbook Runs: {stats['playbook_runs']}")
        logger.info(f"Ad-hoc Commands: {stats['adhoc_commands']}")
        logger.info(f"Total Tasks Executed: {stats['total_tasks_executed']}")
        logger.info(f"Inventory Hosts: {stats['inventory_hosts']}")
        logger.info(f"Inventory Groups: {stats['inventory_groups']}")
        logger.info("")

        # Host statistics
        logger.info("MANAGED HOST STATISTICS")
        logger.info("=" * 70)

        for host_name, host in self.managed_hosts.items():
            logger.info(f"\n{host_name}:")
            logger.info(f"  SSH Sessions: {host.session_counter}")
            logger.info(f"  Commands Executed: {len(host.command_history)}")
            logger.info(f"  Installed Packages: {len(host.installed_packages)}")
            logger.info(f"  Services: {len(host.services)}")
            logger.info(f"  Files Created: {len(host.filesystem)}")

        logger.info("")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Ansible Core Simulation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--duration", type=float, default=60.0,
        help="Simulation duration in seconds"
    )
    parser.add_argument(
        "--num-hosts", type=int, default=9,
        help="Number of managed hosts"
    )
    parser.add_argument(
        "--num-azs", type=int, default=3,
        help="Number of availability zones"
    )
    parser.add_argument(
        "--forks", type=int, default=5,
        help="Number of parallel forks for Ansible"
    )
    parser.add_argument(
        "--network-latency", type=float, default=0.01,
        help="Mean network latency in seconds"
    )

    args = parser.parse_args()

    # Print configuration
    print("\n" + "=" * 70)
    print("ANSIBLE CORE SIMULATION CONFIGURATION")
    print("=" * 70)
    print(f"Duration: {args.duration}s")
    print(f"Managed Hosts: {args.num_hosts}")
    print(f"Availability Zones: {args.num_azs}")
    print(f"Ansible Forks: {args.forks}")
    print(f"Network Latency: {args.network_latency}s")
    print("=" * 70)
    print()

    # Run simulation
    sim = AnsibleSimulation(args)
    sim.run(duration=args.duration)


if __name__ == "__main__":
    main()
