"""
Executor Components for Ansible Simulator.

Includes:
- TaskExecutor: Executes individual tasks
- WorkerProcess: Simulated worker process
- TaskQueueManager: Manages worker pool
- PlayIterator: State machine for task iteration
"""

import simpy
import random
from typing import Dict, List, Optional, Any, Tuple, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from collections import deque

from simulator.infra.network import Network

from ansible_simulator.shared.models import (
    Task, TaskResult, TaskState, Play, Inventory,
    ConnectionInfo, Host
)
from ansible_simulator.components.plugins import get_action_plugin

import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Task Executor
# ============================================================================

class TaskExecutor(BaseModel):
    """
    Task Executor.

    Executes a single task on a single host, mirroring
    lib/ansible/executor/task_executor.py
    """
    env: simpy.Environment
    network: Network
    task: Task
    host: Host
    task_vars: Dict[str, Any] = Field(default_factory=dict)
    play_context: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def run(self):
        """
        Execute the task.

        Follows the TaskExecutor.run() flow from Ansible:
        1. Handle loops
        2. Load action plugin
        3. Establish connection
        4. Execute module
        5. Process results

        PROBLEM REPRODUCTION (42355d18):
        When task uses both loop and delegate_to, they are evaluated TWICE
        causing inconsistent results when delegate_to uses random selection.
        """
        logger.info(
            f"[{self.env.now:.4f}] TaskExecutor: Executing task '{self.task.name}' "
            f"on host {self.host.name}"
        )

        start_time = self.env.now

        # Create task result
        result = TaskResult(
            task_name=self.task.name,
            host_name=self.host.name,
            state=TaskState.RUNNING,
            start_time=start_time
        )

        try:
            # Check if host is reachable
            if not self.host.is_reachable:
                result.state = TaskState.FAILED
                result.failed = True
                result.msg = "Host unreachable"
                return result

            # Evaluate conditional (when)
            if self.task.when:
                # Simplified - just check if it's a boolean or string "True"
                should_run = self._evaluate_conditional(self.task.when)
                if not should_run:
                    result.state = TaskState.SKIPPED
                    result.skipped = True
                    result.msg = "Skipped due to conditional"
                    return result

            # PROBLEM: Evaluate delegate_to FIRST TIME (early evaluation)
            if self.task.delegate_to:
                delegate_host_1 = self._evaluate_delegate_to(self.task.delegate_to)
                logger.warning(
                    f"[{self.env.now:.4f}] PROBLEM: Evaluated delegate_to (1st time) -> {delegate_host_1}"
                )

            # PROBLEM: Evaluate loop items FIRST TIME (early evaluation)
            if self.task.loop:
                loop_items_1 = self._evaluate_loop_items(self.task.loop)
                logger.warning(
                    f"[{self.env.now:.4f}] PROBLEM: Evaluated loop items (1st time) -> {loop_items_1}"
                )

            # Handle loops
            if self.task.loop:
                loop_results = yield from self._run_loop()
                result.loop_results = loop_results
                # Determine overall changed state
                result.changed = any(r.get("changed", False) for r in loop_results)
                result.failed = any(r.get("failed", False) for r in loop_results)
            else:
                # Execute single task
                module_result = yield from self._execute()

                result.changed = module_result.changed
                result.failed = module_result.failed
                result.msg = module_result.msg
                result.rc = module_result.rc
                result.stdout = module_result.stdout
                result.stderr = module_result.stderr
                result.ansible_facts = module_result.ansible_facts
                result.results = module_result.results

                # Update host facts
                if module_result.ansible_facts:
                    self.host.gathered_facts.update(module_result.ansible_facts)

            # Set final state
            if result.failed and not self.task.ignore_errors:
                result.state = TaskState.FAILED
            else:
                result.state = TaskState.SUCCESS

        except Exception as e:
            logger.error(f"[{self.env.now:.4f}] TaskExecutor: Error executing task: {e}")
            result.state = TaskState.FAILED
            result.failed = True
            result.msg = str(e)

        # Record timing
        result.end_time = self.env.now
        result.duration = result.end_time - result.start_time

        logger.info(
            f"[{self.env.now:.4f}] TaskExecutor: Task '{self.task.name}' "
            f"completed on {self.host.name} - "
            f"state={result.state.value}, changed={result.changed}, duration={result.duration:.3f}s"
        )

        return result

    def _execute(self):
        """Execute the task without loops."""
        # Build connection info
        connection_info = ConnectionInfo(
            host=self.host.name,
            port=self.host.ansible_port,
            user=self.host.ansible_user or self.play_context.get("remote_user", "root"),
            connection_type=self.host.ansible_connection,
            become=self.task.become if self.task.become is not None else self.play_context.get("become", False),
            become_user=self.task.become_user or self.play_context.get("become_user", "root"),
            become_method=self.play_context.get("become_method", "sudo")
        )

        # Get action plugin
        action_plugin = get_action_plugin(
            env=self.env,
            network=self.network,
            task=self.task,
            host_name=self.host.name,
            connection_info=connection_info,
            task_vars=self.task_vars
        )

        # Run action plugin
        result = yield from action_plugin.run()

        return result

    def _run_loop(self):
        """
        Execute task with loop.

        PROBLEM REPRODUCTION (42355d18):
        Evaluates loop items and delegate_to SECOND TIME during execution.
        """
        if not self.task.loop:
            return []

        # PROBLEM: Evaluate loop items SECOND TIME
        loop_items_2 = self._evaluate_loop_items(self.task.loop)
        logger.warning(
            f"[{self.env.now:.4f}] PROBLEM: Evaluated loop items (2nd time) -> {loop_items_2}"
        )

        logger.info(f"[{self.env.now:.4f}] TaskExecutor: Running loop with {len(loop_items_2)} items")

        loop_results = []

        for item in loop_items_2:
            # Add item to task vars
            self.task_vars["item"] = item

            # PROBLEM: Evaluate delegate_to SECOND TIME (once per loop iteration!)
            if self.task.delegate_to:
                delegate_host_2 = self._evaluate_delegate_to(self.task.delegate_to)
                logger.warning(
                    f"[{self.env.now:.4f}] PROBLEM: Evaluated delegate_to (2nd time, iteration) -> {delegate_host_2}"
                )

            # Execute task
            result = yield from self._execute()

            loop_results.append({
                "item": item,
                "changed": result.changed,
                "failed": result.failed,
                "msg": result.msg
            })

            # Stop on first failure unless ignore_errors
            if result.failed and not self.task.ignore_errors:
                break

        return loop_results

    def _evaluate_loop_items(self, loop_value):
        """
        Evaluate loop items (simulated).

        PROBLEM: This gets called TWICE - once early, once during execution.
        If loop uses dynamic values (e.g. query, random), results differ.
        """
        # For simulation, just return the loop value
        # In real Ansible, this would template/evaluate the loop expression
        if isinstance(loop_value, list):
            return loop_value
        return []

    def _evaluate_delegate_to(self, delegate_to_value):
        """
        Evaluate delegate_to target (simulated).

        PROBLEM: This gets called MULTIPLE TIMES:
        - Once early in run()
        - Once per loop iteration in _run_loop()

        If delegate_to uses random selection or dynamic lookup, each call
        returns different results causing inconsistent delegation!
        """
        # In real Ansible, this would template the delegate_to expression
        # For simulation, just return the value
        # But we add random selection to demonstrate the problem
        if delegate_to_value and "random" in delegate_to_value.lower():
            # Simulate random host selection
            import random
            hosts = ["host1", "host2", "host3"]
            selected = random.choice(hosts)
            return selected
        return delegate_to_value

    def _evaluate_conditional(self, condition: str) -> bool:
        """
        Evaluate a conditional expression (simplified).

        In real Ansible, this uses Jinja2 templating.
        """
        # Very simplified - just handle basic cases
        if condition in ["true", "True", "yes"]:
            return True
        elif condition in ["false", "False", "no"]:
            return False
        else:
            # Check if it's a variable reference
            # For simulation, return True by default
            return True


# ============================================================================
# Worker Process
# ============================================================================

class WorkerProcess(BaseModel):
    """
    Simulated Worker Process.

    Represents a forked worker process that executes a single task.
    Mirrors lib/ansible/executor/process/worker.py
    """
    worker_id: str
    env: simpy.Environment
    network: Network
    task: Task
    host: Host
    task_vars: Dict[str, Any]
    play_context: Dict[str, Any]

    # Result
    result: Optional[TaskResult] = None

    class Config:
        arbitrary_types_allowed = True

    def run(self):
        """
        Run the worker process.

        This simulates the forked process lifecycle:
        1. Detach from parent
        2. Execute task via TaskExecutor
        3. Return result
        """
        logger.info(
            f"[{self.env.now:.4f}] Worker {self.worker_id}: Started for task '{self.task.name}' "
            f"on {self.host.name}"
        )

        # Simulate process fork overhead
        yield self.env.timeout(random.uniform(0.001, 0.005))

        # Create task executor
        executor = TaskExecutor(
            env=self.env,
            network=self.network,
            task=self.task,
            host=self.host,
            task_vars=self.task_vars,
            play_context=self.play_context
        )

        # Execute task
        self.result = yield from executor.run()

        logger.info(f"[{self.env.now:.4f}] Worker {self.worker_id}: Completed")

        return self.result


# ============================================================================
# Play Iterator
# ============================================================================

class HostState(BaseModel):
    """
    State for a single host in play iteration.

    PROBLEM REPRODUCTION (395e5e20):
    - Uses plain integers for run_state and fail_state
    - No explicit type or readable representation
    - Hard to understand what state values mean

    PROBLEM REPRODUCTION (d6d2251a):
    - Tracks whether implicit flush_handlers has been generated
    """
    host_name: str
    run_state: int = 0  # Plain integer - confusing! What does 0 mean?
    fail_state: int = 0  # Plain integer for failure state
    task_index: int = 0
    notified_handlers: List[str] = Field(default_factory=list)

    # PROBLEM (d6d2251a): Track implicit flush_handlers generation
    implicit_flush_generated: bool = False

    def __str__(self) -> str:
        """
        PROBLEM: String representation shows opaque numeric values.
        Makes debugging difficult - what does "run_state=1, fail_state=0" mean?
        """
        return f"HostState(host={self.host_name}, run_state={self.run_state}, fail_state={self.fail_state})"


class PlayIterator(BaseModel):
    """
    Play Iterator - State Machine for Task Execution.

    Manages the state of task execution across all hosts.
    Mirrors lib/ansible/executor/play_iterator.py

    PROBLEM REPRODUCTION (395e5e20):
    - Run states and failure states are exposed as plain integers
    - Used directly by executor logic and strategy plugins
    - Makes code harder to read (what does ITERATING_TASKS=1 mean?)
    - External plugins access via PlayIterator.ITERATING_TASKS
    - No public type to represent these states
    """

    # Run state constants - exposed as plain integers
    # PROBLEM: Just numbers, no semantic meaning
    ITERATING_SETUP: ClassVar[int] = 0
    ITERATING_TASKS: ClassVar[int] = 1
    ITERATING_RESCUE: ClassVar[int] = 2
    ITERATING_ALWAYS: ClassVar[int] = 3
    ITERATING_HANDLERS: ClassVar[int] = 4
    ITERATING_COMPLETE: ClassVar[int] = 5

    # Failure state constants - bit flags as integers
    # PROBLEM: Bit manipulation makes it even more confusing
    FAILED_NONE: ClassVar[int] = 0
    FAILED_SETUP: ClassVar[int] = 1
    FAILED_TASKS: ClassVar[int] = 2
    FAILED_RESCUE: ClassVar[int] = 4
    FAILED_ALWAYS: ClassVar[int] = 8

    play: Play
    inventory: Inventory
    host_states: Dict[str, HostState] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize host states with integer state
        hosts = self.inventory.get_hosts(self.play.hosts)
        for host in hosts:
            self.host_states[host.name] = HostState(
                host_name=host.name,
                run_state=self.ITERATING_SETUP,  # Using integer constant
                fail_state=self.FAILED_NONE
            )

    def get_next_task_for_host(self, host_name: str) -> Optional[Tuple[Task, int]]:
        """
        Get the next task for a host.

        PROBLEM: Returns integer state instead of typed enum
        Makes caller code harder to understand

        Returns:
            Tuple of (task, state_integer) or None if host is complete
        """
        if host_name not in self.host_states:
            return None

        state = self.host_states[host_name]

        # Complete state - PROBLEM: comparing integer directly
        if state.run_state == self.ITERATING_COMPLETE:  # What does 5 mean?
            return None

        # Setup state (fact gathering)
        if state.run_state == self.ITERATING_SETUP:  # What does 0 mean?
            if self.play.gather_facts:
                setup_task = Task(
                    name="Gathering Facts",
                    action="setup",
                    task_id="setup"
                )
                # PROBLEM: Returning integer state
                return (setup_task, self.ITERATING_SETUP)
            else:
                # Skip to tasks
                state.run_state = self.ITERATING_TASKS  # Magic number 1
                return self.get_next_task_for_host(host_name)

        # Tasks state
        if state.run_state == self.ITERATING_TASKS:  # What does 1 mean?
            all_tasks = self.play.pre_tasks + self.play.tasks + self.play.post_tasks

            if state.task_index < len(all_tasks):
                task = all_tasks[state.task_index]
                # Handle both Task and Block (simplified - treat Block tasks as flat list)
                if isinstance(task, Task):
                    # PROBLEM: Returning integer
                    return (task, self.ITERATING_TASKS)
            else:
                # PROBLEM REPRODUCTION (d6d2251a):
                # Generate implicit "meta: flush_handlers" for ALL hosts
                # even if they have NO notified handlers!
                if not state.implicit_flush_generated:
                    state.implicit_flush_generated = True
                    implicit_flush = Task(
                        name="meta: flush_handlers (implicit)",
                        action="meta",
                        args={"_raw_params": "flush_handlers"},
                        task_id="implicit_flush_handlers"
                    )
                    logger.warning(
                        f"[{logger.name}] PROBLEM d6d2251a: Generated implicit flush_handlers for "
                        f"{host_name} (has {len(state.notified_handlers)} notified handlers)"
                    )
                    # Return implicit flush_handlers without changing state yet
                    return (implicit_flush, self.ITERATING_TASKS)

                # Move to handlers - PROBLEM: Magic number 4
                state.run_state = self.ITERATING_HANDLERS
                state.task_index = 0
                return self.get_next_task_for_host(host_name)

        # Handlers state
        if state.run_state == self.ITERATING_HANDLERS:  # What does 4 mean?
            # Only run notified handlers
            if state.task_index < len(state.notified_handlers):
                handler_name = state.notified_handlers[state.task_index]
                # Find handler by name
                handler = None
                for h in self.play.handlers:
                    if h.name == handler_name:
                        handler = h
                        break

                if handler:
                    # PROBLEM: Returning integer
                    return (handler, self.ITERATING_HANDLERS)

            # Move to complete - PROBLEM: Magic number 5
            state.run_state = self.ITERATING_COMPLETE
            return None

        return None

    def mark_task_complete(self, host_name: str, task_result: TaskResult):
        """Mark a task as complete for a host."""
        if host_name not in self.host_states:
            return

        state = self.host_states[host_name]

        # Handle task failure
        if task_result.failed:
            # PROBLEM: Setting fail_state as integer bit flag
            state.fail_state = self.FAILED_TASKS  # Magic number 2
            # In real Ansible, this would move to RESCUE state
            # Simplified: just mark as complete
            state.run_state = self.ITERATING_COMPLETE  # Magic number 5
            return

        # Advance task index
        state.task_index += 1

        # If task completed setup, move to tasks
        if state.run_state == self.ITERATING_SETUP:  # Comparing with 0
            state.run_state = self.ITERATING_TASKS  # Setting to 1
            state.task_index = 0

    def is_host_complete(self, host_name: str) -> bool:
        """Check if a host has completed all tasks."""
        if host_name not in self.host_states:
            return True

        # PROBLEM: Comparing with integer constant
        return self.host_states[host_name].run_state == self.ITERATING_COMPLETE

    def all_hosts_complete(self) -> bool:
        """Check if all hosts have completed."""
        return all(self.is_host_complete(name) for name in self.host_states.keys())

    def notify_handler(self, host_name: str, handler_name: str):
        """Notify a handler for a host."""
        if host_name in self.host_states:
            if handler_name not in self.host_states[host_name].notified_handlers:
                self.host_states[host_name].notified_handlers.append(handler_name)
