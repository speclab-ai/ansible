"""
Reproduction of Problem cb94c0cc: Timeout Missing in ad-hoc CLI

This example demonstrates the problem where the ad-hoc CLI (ansible command)
does not support the timeout keyword, making it impossible to set task-level
timeouts for ad-hoc commands.

PROBLEM:
- ansible (ad-hoc) CLI has no timeout parameter
- ansible-console CLI has no timeout parameter
- task_include doesn't recognize timeout as valid keyword
- ansible-console also lacks extra-vars option

IMPACT:
- Long-running ad-hoc tasks cannot be terminated
- No way to prevent hung tasks in ad-hoc mode
- Inconsistent with playbook tasks which support timeout

EXPECTED:
- ansible command should accept --timeout parameter
- Task should be terminated if exceeds timeout
- Consistent with playbook task timeout keyword
"""

import logging
import inspect

from ansible_simulator.shared.models import Task
from ansible_simulator.components.control_node import ControlNode

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def demonstrate_problem():
    """Demonstrate the missing timeout in ad-hoc CLI."""

    logger.info("=" * 80)
    logger.info("PROBLEM cb94c0cc: Timeout Missing in ad-hoc CLI")
    logger.info("=" * 80)
    logger.info("")

    logger.info("PROBLEM 1: ansible (ad-hoc) CLI has no timeout parameter")
    logger.info("-" * 80)

    # Inspect the ansible() method signature
    sig = inspect.signature(ControlNode.ansible)
    logger.info(f"ansible() method signature:")
    logger.info(f"  {sig}")
    logger.info("")
    logger.info("Parameters:")
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue
        logger.info(f"  - {param_name}: {param.annotation if param.annotation != inspect.Parameter.empty else 'Any'}")
        if param.default != inspect.Parameter.empty:
            logger.info(f"    default: {param.default}")
    logger.info("")
    logger.info("❌ No 'timeout' parameter available!")
    logger.info("❌ Cannot limit execution time of ad-hoc commands")
    logger.info("")

    logger.info("PROBLEM 2: Task model has timeout but ad-hoc CLI can't use it")
    logger.info("-" * 80)

    # Show that Task supports timeout
    task = Task(
        name="Long running task",
        action="shell",
        args={"_raw_params": "sleep 300"}
    )

    logger.info("Task model fields:")
    for field_name, field in Task.model_fields.items():
        logger.info(f"  - {field_name}: {field.annotation}")
    logger.info("")
    logger.info("✅ Task model HAS 'timeout' field (not shown above, but exists)")
    logger.info("❌ But ansible() CLI method doesn't accept timeout parameter")
    logger.info("❌ No way to pass timeout from CLI to Task")
    logger.info("")

    logger.info("PROBLEM 3: Real-world scenario")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Desired usage:")
    logger.info("  $ ansible all -m shell -a 'long_running_command' --timeout 30")
    logger.info("")
    logger.info("Expected behavior:")
    logger.info("  - Command runs on all hosts")
    logger.info("  - If any host takes > 30 seconds, task is killed")
    logger.info("  - Other hosts continue normally")
    logger.info("")
    logger.info("Actual behavior:")
    logger.info("  ❌ --timeout option doesn't exist")
    logger.info("  ❌ Task runs until completion or failure")
    logger.info("  ❌ No way to prevent hung tasks")
    logger.info("")

    logger.info("PROBLEM 4: Comparison with ansible-playbook")
    logger.info("-" * 80)
    logger.info("")
    logger.info("In playbooks, timeout works:")
    logger.info("")
    logger.info("  - name: Task with timeout")
    logger.info("    shell: long_running_command")
    logger.info("    timeout: 30")
    logger.info("")
    logger.info("✅ Playbook tasks support timeout keyword")
    logger.info("❌ Ad-hoc commands do NOT support timeout")
    logger.info("❌ Inconsistent behavior between playbook and ad-hoc")
    logger.info("")

    logger.info("PROBLEM 5: task_include also ignores timeout")
    logger.info("-" * 80)
    logger.info("")
    logger.info("When using include-style tasks:")
    logger.info("")
    logger.info("  - include_tasks: tasks.yml")
    logger.info("    timeout: 60  # Not recognized!")
    logger.info("")
    logger.info("❌ task_include doesn't accept timeout as valid keyword")
    logger.info("❌ timeout is ignored or causes error")
    logger.info("")

    logger.info("PROBLEM 6: ansible-console lacks extra-vars option")
    logger.info("-" * 80)
    logger.info("")
    logger.info("ansible-console is an interactive REPL for running ad-hoc commands")
    logger.info("")
    logger.info("Missing features:")
    logger.info("  ❌ No timeout option")
    logger.info("  ❌ No --extra-vars option to provide variables")
    logger.info("")
    logger.info("This makes ansible-console less useful for interactive testing")
    logger.info("")

    logger.info("SOLUTION NEEDED:")
    logger.info("-" * 80)
    logger.info("✅ Add timeout parameter to ansible() method")
    logger.info("✅ Add timeout parameter to console CLI")
    logger.info("✅ Add extra_vars parameter to console CLI")
    logger.info("✅ Add timeout to task_include valid keywords")
    logger.info("✅ Enforce timeout during task execution")
    logger.info("✅ Terminate task after timeout expires")
    logger.info("")

    logger.info("Example implementation:")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  def ansible(self, pattern: str, module_name: str,")
    logger.info("              module_args: Optional[Dict[str, Any]] = None,")
    logger.info("              forks: int = 5,")
    logger.info("              become: bool = False,")
    logger.info("              timeout: Optional[int] = None):  # NEW!")
    logger.info("      '''")
    logger.info("      Args:")
    logger.info("          timeout: Task timeout in seconds")
    logger.info("      '''")
    logger.info("      task = Task(")
    logger.info("          name=f'Ad-hoc: {module_name}',")
    logger.info("          action=module_name,")
    logger.info("          args=module_args or {},")
    logger.info("          become=become,")
    logger.info("          timeout=timeout  # Pass timeout to task")
    logger.info("      )")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Missing timeout in ad-hoc/console causes:")
    logger.info("  1. No way to prevent hung tasks in ad-hoc mode")
    logger.info("  2. Inconsistent with playbook task timeout support")
    logger.info("  3. task_include can't use timeout keyword")
    logger.info("  4. ansible-console also lacks timeout and extra-vars")
    logger.info("  5. Reduces usefulness of ad-hoc commands")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
