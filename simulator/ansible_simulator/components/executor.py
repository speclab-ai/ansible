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
from typing import Dict, List, Optional, Any, Tuple
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
        """Execute task with loop."""
        if not self.task.loop:
            return []

        logger.info(f"[{self.env.now:.4f}] TaskExecutor: Running loop with {len(self.task.loop)} items")

        loop_results = []

        for item in self.task.loop:
            # Add item to task vars
            self.task_vars["item"] = item

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

class IteratingStates(str, Enum):
    """States in the play iteration state machine."""
    SETUP = "setup"
    TASKS = "tasks"
    RESCUE = "rescue"
    ALWAYS = "always"
    HANDLERS = "handlers"
    COMPLETE = "complete"


class HostState(BaseModel):
    """State for a single host in play iteration."""
    host_name: str
    run_state: IteratingStates = IteratingStates.SETUP
    fail_state: bool = False
    task_index: int = 0
    notified_handlers: List[str] = Field(default_factory=list)


class PlayIterator(BaseModel):
    """
    Play Iterator - State Machine for Task Execution.

    Manages the state of task execution across all hosts.
    Mirrors lib/ansible/executor/play_iterator.py
    """
    play: Play
    inventory: Inventory
    host_states: Dict[str, HostState] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize host states
        hosts = self.inventory.get_hosts(self.play.hosts)
        for host in hosts:
            self.host_states[host.name] = HostState(host_name=host.name)

    def get_next_task_for_host(self, host_name: str) -> Optional[Tuple[Task, IteratingStates]]:
        """
        Get the next task for a host.

        Returns:
            Tuple of (task, state) or None if host is complete
        """
        if host_name not in self.host_states:
            return None

        state = self.host_states[host_name]

        # Complete state
        if state.run_state == IteratingStates.COMPLETE:
            return None

        # Setup state (fact gathering)
        if state.run_state == IteratingStates.SETUP:
            if self.play.gather_facts:
                setup_task = Task(
                    name="Gathering Facts",
                    action="setup",
                    task_id="setup"
                )
                return (setup_task, IteratingStates.SETUP)
            else:
                # Skip to tasks
                state.run_state = IteratingStates.TASKS
                return self.get_next_task_for_host(host_name)

        # Tasks state
        if state.run_state == IteratingStates.TASKS:
            all_tasks = self.play.pre_tasks + self.play.tasks + self.play.post_tasks

            if state.task_index < len(all_tasks):
                task = all_tasks[state.task_index]
                # Handle both Task and Block (simplified - treat Block tasks as flat list)
                if isinstance(task, Task):
                    return (task, IteratingStates.TASKS)
            else:
                # Move to handlers
                state.run_state = IteratingStates.HANDLERS
                state.task_index = 0
                return self.get_next_task_for_host(host_name)

        # Handlers state
        if state.run_state == IteratingStates.HANDLERS:
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
                    return (handler, IteratingStates.HANDLERS)

            # Move to complete
            state.run_state = IteratingStates.COMPLETE
            return None

        return None

    def mark_task_complete(self, host_name: str, task_result: TaskResult):
        """Mark a task as complete for a host."""
        if host_name not in self.host_states:
            return

        state = self.host_states[host_name]

        # Handle task failure
        if task_result.failed:
            state.fail_state = True
            # In real Ansible, this would move to RESCUE state
            # Simplified: just mark as complete
            state.run_state = IteratingStates.COMPLETE
            return

        # Advance task index
        state.task_index += 1

        # If task completed setup, move to tasks
        if state.run_state == IteratingStates.SETUP:
            state.run_state = IteratingStates.TASKS
            state.task_index = 0

    def is_host_complete(self, host_name: str) -> bool:
        """Check if a host has completed all tasks."""
        if host_name not in self.host_states:
            return True

        return self.host_states[host_name].run_state == IteratingStates.COMPLETE

    def all_hosts_complete(self) -> bool:
        """Check if all hosts have completed."""
        return all(self.is_host_complete(name) for name in self.host_states.keys())

    def notify_handler(self, host_name: str, handler_name: str):
        """Notify a handler for a host."""
        if host_name in self.host_states:
            if handler_name not in self.host_states[host_name].notified_handlers:
                self.host_states[host_name].notified_handlers.append(handler_name)
