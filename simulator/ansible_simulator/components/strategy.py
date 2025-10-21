"""
Strategy Plugins for Ansible Simulator.

Strategy plugins control the flow of task execution across hosts:
- Linear: Lockstep execution (default)
- Free: Independent host execution
"""

import simpy
from typing import Dict, List, Optional, Any, Deque
from pydantic import BaseModel, Field
from collections import deque

from simulator.infra.network import Network

from ansible_simulator.shared.models import (
    Play, Inventory, PlayStats, TaskResult, TaskState, Task
)
from ansible_simulator.components.executor import (
    WorkerProcess, PlayIterator
)
from ansible_simulator.executor.stats import AggregateStats

import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Task Queue Manager
# ============================================================================

class TaskQueueManager(BaseModel):
    """
    Task Queue Manager.

    Manages the worker pool and coordinates task execution.
    Mirrors lib/ansible/executor/task_queue_manager.py
    """
    env: simpy.Environment
    network: Network
    inventory: Inventory
    forks: int = 5  # Number of parallel workers

    # Worker tracking
    worker_counter: int = 0
    active_workers: Dict[str, simpy.Process] = Field(default_factory=dict)
    pending_results: Deque[TaskResult] = Field(default_factory=deque)

    # Stats
    stats: AggregateStats = Field(default_factory=AggregateStats)
    failed_hosts: Dict[str, bool] = Field(default_factory=dict)
    unreachable_hosts: Dict[str, bool] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def run_play(self, play: Play, strategy_name: str = "linear"):
        """
        Run a play using the specified strategy.

        Args:
            play: The play to execute
            strategy_name: Strategy to use (linear, free)

        Returns:
            PlayStats for the play
        """
        logger.info(f"[{self.env.now:.4f}] TaskQueueManager: Running play '{play.name}' with strategy '{strategy_name}'")

        start_time = self.env.now

        # Create strategy
        strategy: StrategyBase
        if strategy_name == "free":
            strategy = FreeStrategy(
                env=self.env,
                network=self.network,
                play=play,
                inventory=self.inventory,
                task_queue_manager=self
            )
        else:
            strategy = LinearStrategy(
                env=self.env,
                network=self.network,
                play=play,
                inventory=self.inventory,
                task_queue_manager=self
            )

        # Run strategy
        stats = yield from strategy.run()

        # Update timing
        stats.duration = self.env.now - start_time

        logger.info(
            f"[{self.env.now:.4f}] TaskQueueManager: Play '{play.name}' completed - "
            f"duration={stats.duration:.3f}s"
        )

        return stats

    def queue_task(self, task, host, task_vars: Dict[str, Any], play_context: Dict[str, Any]):
        """
        Queue a task for execution on a host.

        This creates a worker process to execute the task.

        Returns:
            SimPy process for the worker
        """
        # Wait if we've hit the fork limit
        while len(self.active_workers) >= self.forks:
            # Wait for a worker to complete
            yield self.env.timeout(0.01)

        # Create worker
        self.worker_counter += 1
        worker_id = f"worker_{self.worker_counter}"

        worker = WorkerProcess(
            worker_id=worker_id,
            env=self.env,
            network=self.network,
            task=task,
            host=host,
            task_vars=task_vars,
            play_context=play_context
        )

        # Start worker
        process = self.env.process(worker.run())

        # Track active worker
        self.active_workers[worker_id] = process

        # Set up callback to remove from active workers when done
        def worker_done(event):
            if worker_id in self.active_workers:
                del self.active_workers[worker_id]
            # Add result to pending
            if worker.result:
                self.pending_results.append(worker.result)

        process.callbacks.append(worker_done)

        return process

    def get_pending_results(self) -> List[TaskResult]:
        """Get all pending results."""
        results = list(self.pending_results)
        self.pending_results.clear()
        return results

    def wait_for_all_workers(self):
        """Wait for all active workers to complete."""
        while self.active_workers:
            yield self.env.timeout(0.01)


# ============================================================================
# Base Strategy
# ============================================================================

class StrategyBase(BaseModel):
    """
    Base class for strategy plugins.

    Mirrors lib/ansible/plugins/strategy/__init__.py
    """
    env: simpy.Environment
    network: Network
    play: Play
    inventory: Inventory
    task_queue_manager: TaskQueueManager

    class Config:
        arbitrary_types_allowed = True

    def run(self):
        """Execute the strategy."""
        raise NotImplementedError()

    def _build_play_context(self) -> Dict[str, Any]:
        """Build play context from play settings."""
        return {
            "remote_user": self.play.remote_user or "root",
            "become": self.play.become or False,
            "become_user": self.play.become_user or "root",
            "become_method": self.play.become_method or "sudo"
        }


# ============================================================================
# Linear Strategy
# ============================================================================

class LinearStrategy(StrategyBase):
    """
    Linear Strategy Plugin.

    Default strategy - executes tasks in lockstep across all hosts.
    All hosts must complete task N before any host starts task N+1.

    Mirrors lib/ansible/plugins/strategy/linear.py
    """

    def run(self):
        """
        Run the linear strategy.

        Algorithm:
        1. For each task in the play:
           a. Queue task for all hosts
           b. Wait for all hosts to complete
           c. Process results
           d. Move to next task
        """
        logger.info(f"[{self.env.now:.4f}] LinearStrategy: Starting play '{self.play.name}'")

        # Initialize stats
        stats = PlayStats(play_name=self.play.name)

        # Get hosts
        hosts = self.inventory.get_hosts(self.play.hosts)
        stats.total_hosts = len(hosts)

        if not hosts:
            logger.warning(f"[{self.env.now:.4f}] LinearStrategy: No hosts found for pattern '{self.play.hosts}'")
            return stats

        # Create play iterator
        iterator = PlayIterator(
            play=self.play,
            inventory=self.inventory
        )

        # Build play context
        play_context = self._build_play_context()

        # Track results
        host_results: Dict[str, List[TaskResult]] = {h.name: [] for h in hosts}

        # Main execution loop
        while not iterator.all_hosts_complete():
            # Get next tasks for all non-failed hosts
            tasks_to_run = []
            hosts_with_work = []
            hosts_without_work = []

            for host in hosts:
                # PROBLEM REPRODUCTION (811093f0):
                # Don't skip failed hosts entirely - let them run handlers!
                # This demonstrates the problem of handlers running on failed hosts
                is_failed = host.name in self.task_queue_manager.failed_hosts

                next_task = iterator.get_next_task_for_host(host.name)
                if next_task:
                    task, state = next_task
                    tasks_to_run.append((task, host, state))
                    hosts_with_work.append(host.name)
                else:
                    # PROBLEM REPRODUCTION (d6d2251a):
                    # Host has no work but we're in linear strategy
                    # Generate "meta: noop" to keep it in lockstep
                    if not iterator.is_host_complete(host.name):
                        hosts_without_work.append(host.name)

            # PROBLEM (d6d2251a): Generate noop tasks for idle hosts
            if hosts_without_work and hosts_with_work:
                for host_name in hosts_without_work:
                    # Find the host object
                    host_obj = next((h for h in hosts if h.name == host_name), None)
                    if host_obj:
                        noop_task = Task(
                            name="meta: noop (implicit)",
                            action="meta",
                            args={"_raw_params": "noop"},
                            task_id=f"implicit_noop_{host_name}"
                        )
                        tasks_to_run.append((noop_task, host_obj, iterator.ITERATING_TASKS))
                        logger.warning(
                            f"[{self.env.now:.4f}] PROBLEM d6d2251a: Generated implicit noop for "
                            f"{host_name} to keep in lockstep with {len(hosts_with_work)} hosts with work"
                        )

            if not tasks_to_run:
                break

            # Queue all tasks
            processes = []
            for task, host, state in tasks_to_run:
                logger.info(
                    f"[{self.env.now:.4f}] LinearStrategy: Queueing task '{task.name}' "
                    f"for host {host.name}"
                )

                # Build task vars
                task_vars = dict(self.play.vars)
                task_vars.update(host.vars)
                task_vars.update(host.gathered_facts)

                # Queue task
                process = yield from self.task_queue_manager.queue_task(
                    task=task,
                    host=host,
                    task_vars=task_vars,
                    play_context=play_context
                )
                processes.append(process)

            # Wait for all tasks to complete (lockstep)
            yield from self.task_queue_manager.wait_for_all_workers()

            # Get results
            results = self.task_queue_manager.get_pending_results()

            # Process results
            for result in results:
                host_results[result.host_name].append(result)
                stats.total_tasks += 1

                # Update iterator
                iterator.mark_task_complete(result.host_name, result)

                # Update aggregate stats (per-host)
                if result.state == TaskState.SUCCESS:
                    self.task_queue_manager.stats.increment('ok', result.host_name)
                    stats.tasks_ok += 1
                    if result.changed:
                        self.task_queue_manager.stats.increment('changed', result.host_name)
                        stats.tasks_changed += 1
                elif result.state == TaskState.FAILED:
                    self.task_queue_manager.stats.increment('failures', result.host_name)
                    stats.tasks_failed += 1
                    self.task_queue_manager.failed_hosts[result.host_name] = True
                elif result.state == TaskState.SKIPPED:
                    self.task_queue_manager.stats.increment('skipped', result.host_name)
                    stats.tasks_skipped += 1

                # Handle handler notifications
                # PROBLEM REPRODUCTION (811093f0):
                # Notify handlers if task was changed, even if it later failed
                # This allows us to demonstrate handlers running on failed hosts
                if result.changed:
                    # Check if task should notify handlers
                    for task, host, state in tasks_to_run:
                        if task.name == result.task_name and host.name == result.host_name:
                            for handler_name in task.notify:
                                iterator.notify_handler(result.host_name, handler_name)
                                logger.warning(
                                    f"[{self.env.now:.4f}] PROBLEM 811093f0: Notified handler '{handler_name}' "
                                    f"on {result.host_name} (task state={result.state.value}, failed={result.failed})"
                                )

        # Update host stats
        for host_name, results in host_results.items():
            if any(r.state == TaskState.FAILED for r in results):
                stats.hosts_failed += 1
            elif any(r.changed for r in results):
                stats.hosts_changed += 1
            else:
                stats.hosts_ok += 1

        logger.info(f"[{self.env.now:.4f}] LinearStrategy: Play completed")

        return stats


# ============================================================================
# Free Strategy
# ============================================================================

class FreeStrategy(StrategyBase):
    """
    Free Strategy Plugin.

    Hosts execute tasks independently without waiting for others.
    Provides maximum parallelism.

    Mirrors lib/ansible/plugins/strategy/free.py
    """

    def run(self):
        """
        Run the free strategy.

        Algorithm:
        1. For each host, run tasks independently
        2. Hosts don't wait for each other
        3. Maximum parallelism within fork limit
        """
        logger.info(f"[{self.env.now:.4f}] FreeStrategy: Starting play '{self.play.name}'")

        # Initialize stats
        stats = PlayStats(play_name=self.play.name)

        # Get hosts
        hosts = self.inventory.get_hosts(self.play.hosts)
        stats.total_hosts = len(hosts)

        if not hosts:
            logger.warning(f"[{self.env.now:.4f}] FreeStrategy: No hosts found for pattern '{self.play.hosts}'")
            return stats

        # Create play iterator
        iterator = PlayIterator(
            play=self.play,
            inventory=self.inventory
        )

        # Build play context
        play_context = self._build_play_context()

        # Start a process for each host to run tasks independently
        host_processes = []

        for host in hosts:
            process = self.env.process(
                self._run_host_tasks(host, iterator, play_context, stats)
            )
            host_processes.append(process)

        # Wait for all hosts to complete
        for process in host_processes:
            yield process

        logger.info(f"[{self.env.now:.4f}] FreeStrategy: Play completed")

        return stats

    def _run_host_tasks(self, host, iterator: PlayIterator, play_context: Dict[str, Any], stats: PlayStats):
        """Run all tasks for a single host."""
        logger.info(f"[{self.env.now:.4f}] FreeStrategy: Starting tasks for host {host.name}")

        while not iterator.is_host_complete(host.name):
            # Get next task
            next_task = iterator.get_next_task_for_host(host.name)
            if not next_task:
                break

            task, state = next_task

            logger.info(
                f"[{self.env.now:.4f}] FreeStrategy: Running task '{task.name}' "
                f"on host {host.name}"
            )

            # Build task vars
            task_vars = dict(self.play.vars)
            task_vars.update(host.vars)
            task_vars.update(host.gathered_facts)

            # Queue and wait for task
            process = yield from self.task_queue_manager.queue_task(
                task=task,
                host=host,
                task_vars=task_vars,
                play_context=play_context
            )

            # Wait for this specific task to complete
            yield process

            # Get result
            results = self.task_queue_manager.get_pending_results()

            for result in results:
                if result.host_name == host.name:
                    stats.total_tasks += 1

                    # Update iterator
                    iterator.mark_task_complete(result.host_name, result)

                    # Update aggregate stats (per-host)
                    if result.state == TaskState.SUCCESS:
                        self.task_queue_manager.stats.increment('ok', result.host_name)
                        stats.tasks_ok += 1
                        if result.changed:
                            self.task_queue_manager.stats.increment('changed', result.host_name)
                            stats.tasks_changed += 1
                    elif result.state == TaskState.FAILED:
                        self.task_queue_manager.stats.increment('failures', result.host_name)
                        stats.tasks_failed += 1
                        self.task_queue_manager.failed_hosts[result.host_name] = True
                    elif result.state == TaskState.SKIPPED:
                        self.task_queue_manager.stats.increment('skipped', result.host_name)
                        stats.tasks_skipped += 1

                    # Handle handler notifications
                    if result.state == TaskState.SUCCESS and not result.failed:
                        for handler_name in task.notify:
                            iterator.notify_handler(result.host_name, handler_name)

        # Update host stats
        if host.name in self.task_queue_manager.failed_hosts:
            stats.hosts_failed += 1
        else:
            stats.hosts_ok += 1

        logger.info(f"[{self.env.now:.4f}] FreeStrategy: Host {host.name} completed")
