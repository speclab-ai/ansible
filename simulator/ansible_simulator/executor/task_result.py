"""
Task Result classes for Ansible simulator.

Mirrors lib/ansible/executor/task_result.py for proper result handling.
"""

import dataclasses
from typing import Dict, Any, Mapping, MutableMapping, Optional
from collections.abc import Sequence

from ansible_simulator.shared.models import TaskState


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class WireTaskResult:
    """
    A thin version of task result which can be sent over the worker queue.

    This matches Ansible's _WireTaskResult exactly.
    """
    host_name: str
    task_uuid: str
    return_data: MutableMapping[str, Any]
    task_fields: Mapping[str, Any]


class BaseTaskResult:
    """
    Base class for interpreting task results.

    Provides helper methods for determining the result of a task.
    Mirrors Ansible's _BaseTaskResult.
    """

    def __init__(
        self,
        host_name: str,
        task_uuid: str,
        task_name: str,
        return_data: MutableMapping[str, Any],
        task_fields: Mapping[str, Any]
    ):
        self._host_name = host_name
        self._task_uuid = task_uuid
        self._task_name = task_name
        self._return_data = return_data
        self._task_fields = task_fields

    @property
    def host_name(self) -> str:
        """The host name associated with this result."""
        return self._host_name

    @property
    def task_uuid(self) -> str:
        """The task UUID associated with this result."""
        return self._task_uuid

    @property
    def task_name(self) -> str:
        """The task name."""
        return self._task_name

    @property
    def task_fields(self) -> Mapping[str, Any]:
        """The task fields associated with this result."""
        return self._task_fields

    @property
    def return_data(self) -> MutableMapping[str, Any]:
        """The raw return data from module execution."""
        return self._return_data

    @property
    def _loop_results(self) -> Sequence[MutableMapping[str, Any]]:
        """Return a list of loop results. If no loop results are present, an empty list is returned."""
        results = self._return_data.get('results')

        if not isinstance(results, list):
            return []

        return results

    def is_changed(self) -> bool:
        """Check if the task made changes."""
        return self._check_key('changed')

    def is_skipped(self) -> bool:
        """Check if the task was skipped."""
        if self._loop_results:
            # Loop tasks are only considered skipped if all items were skipped
            if all(isinstance(loop_res, dict) and loop_res.get('skipped', False) for loop_res in self._loop_results):
                return True

        # Regular tasks
        return bool(self._return_data.get('skipped', False))

    def is_failed(self) -> bool:
        """Check if the task failed."""
        if 'failed_when_result' in self._return_data or any(
            isinstance(loop_res, dict) and 'failed_when_result' in loop_res
            for loop_res in self._loop_results
        ):
            return self._check_key('failed_when_result')

        return self._check_key('failed')

    def is_unreachable(self) -> bool:
        """Check if the host was unreachable."""
        return self._check_key('unreachable')

    def _check_key(self, key: str) -> bool:
        """
        Fetch a specific named boolean value from the result.

        If missing, returns a logical OR of the value from nested loop results.
        Returns False for non-loop results.
        """
        value = self._return_data.get(key)
        if value is not None:
            return bool(value)

        return any(isinstance(result, dict) and result.get(key) for result in self._loop_results)

    def to_wire_result(self) -> WireTaskResult:
        """Convert to wire format for transmission."""
        return WireTaskResult(
            host_name=self._host_name,
            task_uuid=self._task_uuid,
            return_data=self._return_data,
            task_fields=self._task_fields,
        )


class RawTaskResult(BaseTaskResult):
    """
    Raw task result from worker execution.

    Provides conversion methods to wire format and legacy TaskResult format.
    """

    @classmethod
    def from_wire_result(
        cls,
        wire_result: WireTaskResult,
        task_name: Optional[str] = None
    ) -> 'RawTaskResult':
        """Create RawTaskResult from wire format."""
        if task_name is None:
            task_name = str(wire_result.task_fields.get('name', ''))

        return cls(
            host_name=wire_result.host_name,
            task_uuid=wire_result.task_uuid,
            task_name=task_name,
            return_data=wire_result.return_data,
            task_fields=wire_result.task_fields,
        )

    def to_legacy_result(self) -> Dict[str, Any]:
        """
        Convert to legacy TaskResult format for backward compatibility.

        Returns a dict matching the TaskResult pydantic model.
        """
        # Determine state
        if self.is_failed():
            state = TaskState.FAILED
        elif self.is_skipped():
            state = TaskState.SKIPPED
        elif self.is_unreachable():
            state = TaskState.FAILED
        else:
            state = TaskState.SUCCESS

        return {
            'task_name': self._task_name,
            'host_name': self._host_name,
            'state': state,
            'changed': self.is_changed(),
            'failed': self.is_failed(),
            'skipped': self.is_skipped(),
            'msg': self._return_data.get('msg', ''),
            'rc': self._return_data.get('rc'),
            'stdout': self._return_data.get('stdout', ''),
            'stderr': self._return_data.get('stderr', ''),
            'ansible_facts': self._return_data.get('ansible_facts', {}),
            'results': self._return_data.get('results', {}),
            'loop_results': [
                {
                    'item': r.get('item'),
                    'changed': r.get('changed', False),
                    'failed': r.get('failed', False),
                    'msg': r.get('msg', ''),
                }
                for r in self._loop_results
                if isinstance(r, dict)
            ] if self._loop_results else [],
            'start_time': 0.0,  # Set by caller
            'end_time': 0.0,    # Set by caller
            'duration': 0.0,    # Set by caller
        }
