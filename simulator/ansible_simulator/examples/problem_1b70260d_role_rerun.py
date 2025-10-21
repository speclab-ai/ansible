"""
Reproduction of Problem 1b70260d: Block with Tag Causes Role Re-run

This example demonstrates how using tags with blocks followed by tasks
causes dependent roles to execute twice.

PROBLEM:
- Play uses roles with dependencies (defined in meta/main.yml)
- Play has a block with tags, followed by regular tasks
- When filtering by tags (--tags), role dependencies execute TWICE
- Tag filtering creates a "gap" that breaks role deduplication

IMPACT:
- Role dependencies run twice (wasted execution)
- Idempotency issues (roles designed to run once)
- Performance degradation
- Potential state corruption

SCENARIO:
```yaml
- hosts: all
  roles:
    - role: app
      # meta/main.yml: dependencies: [common]
  tasks:
    - block:
        - debug: msg="Block task"
      tags: [config]

    - debug: msg="Regular task"
      tags: [deploy]
```

When running with --tags config,deploy:
- common role executes (dependency of app)
- Block with tag 'config' executes
- GAP in execution causes role tracking to reset
- common role executes AGAIN (before deploy tasks)
"""

import logging
from typing import Dict, Set, List

from ansible_simulator.shared.models import (
    Play, Task, Block, Role
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class RoleManager:
    """
    Manages role execution and dependency resolution.

    PROBLEM REPRODUCTION (1b70260d):
    - Tracks which roles have been executed
    - When tag filtering creates gaps, tracking fails
    - Roles get executed multiple times
    """

    def __init__(self):
        self.executed_roles: Set[str] = set()
        self.available_roles: Dict[str, Role] = {}

    def register_role(self, role: Role):
        """Register an available role."""
        self.available_roles[role.name] = role

    def execute_role(self, role_name: str, tags_filter: List[str] = None) -> List[str]:
        """
        Execute a role and its dependencies.

        PROBLEM: When tags are used, role tracking gets confused.

        Returns:
            List of executed role names
        """
        executed = []

        if role_name not in self.available_roles:
            logger.warning(f"Role '{role_name}' not found")
            return executed

        role = self.available_roles[role_name]

        # Execute dependencies first
        for dep_name in role.dependencies:
            # PROBLEM: Check if already executed
            if dep_name in self.executed_roles:
                logger.info(f"  ✓ Role '{dep_name}' already executed (skipping)")
                continue

            logger.info(f"  → Executing dependency role '{dep_name}'")
            self.executed_roles.add(dep_name)
            executed.append(dep_name)

        # Execute the role itself
        if role_name not in self.executed_roles:
            logger.info(f"  → Executing role '{role_name}'")
            self.executed_roles.add(role_name)
            executed.append(role_name)
        else:
            logger.info(f"  ✓ Role '{role_name}' already executed (skipping)")

        return executed

    def reset_tracking(self):
        """
        Reset role tracking.

        PROBLEM: Gets called incorrectly when tag filtering creates gaps.
        """
        logger.warning(
            "⚠️  PROBLEM 1b70260d: Resetting role tracking! "
            f"Previously executed: {self.executed_roles}"
        )
        self.executed_roles.clear()


def demonstrate_problem():
    """Demonstrate role re-execution with block tags."""

    logger.info("=" * 80)
    logger.info("PROBLEM 1b70260d: Block with Tag Causes Role Re-run")
    logger.info("=" * 80)
    logger.info("")

    # Setup roles with dependencies
    logger.info("SETUP: Defining roles with dependencies")
    logger.info("-" * 80)
    logger.info("")

    # Common role (no dependencies)
    common_role = Role(
        name="common",
        dependencies=[],
        tasks=[
            Task(name="Install base packages", action="apt", args={"name": "vim"}),
            Task(name="Configure timezone", action="timezone", args={"name": "UTC"}),
        ]
    )

    # App role (depends on common)
    app_role = Role(
        name="app",
        dependencies=["common"],  # Depends on common!
        tasks=[
            Task(name="Install app", action="apt", args={"name": "myapp"}),
            Task(name="Configure app", action="template", args={"src": "app.conf"}),
        ]
    )

    logger.info("Roles defined:")
    logger.info("  1. common (no dependencies)")
    logger.info("  2. app (depends on: common)")
    logger.info("")

    # Setup role manager
    role_mgr = RoleManager()
    role_mgr.register_role(common_role)
    role_mgr.register_role(app_role)

    # Define play with blocks and tags
    logger.info("SETUP: Defining play with blocks and tags")
    logger.info("-" * 80)
    logger.info("")

    play = Play(
        name="Deploy application",
        hosts="all",
        gather_facts=False,
        roles=[app_role],  # Role with dependency
        tasks=[
            # Block with tag
            Block(
                name="Configuration block",
                tags=["config"],
                tasks=[
                    Task(name="Update config file", action="template",
                         args={"src": "config.j2"}, tags=["config"]),
                    Task(name="Validate config", action="command",
                         args={"_raw_params": "validate-config"}, tags=["config"]),
                ]
            ),
            # Regular task with different tag
            Task(name="Deploy application", action="copy",
                 args={"src": "app.tar.gz"}, tags=["deploy"]),
            Task(name="Start service", action="service",
                 args={"name": "app", "state": "started"}, tags=["deploy"]),
        ]
    )

    logger.info("Play structure:")
    logger.info("  roles:")
    logger.info("    - app (depends on: common)")
    logger.info("  tasks:")
    logger.info("    - block: [2 tasks] tags: [config]")
    logger.info("    - task: Deploy application tags: [deploy]")
    logger.info("    - task: Start service tags: [deploy]")
    logger.info("")

    # Simulate tag filtering
    tags_filter = ["config", "deploy"]
    logger.info(f"EXECUTION: Running with --tags {tags_filter}")
    logger.info("=" * 80)
    logger.info("")

    # Phase 1: Execute roles
    logger.info("PHASE 1: Role execution")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Executing roles (with dependencies):")
    for role in play.roles:
        role_mgr.execute_role(role.name, tags_filter)
    logger.info("")

    # Phase 2: Execute block with tag 'config'
    logger.info("PHASE 2: Execute block with tag 'config'")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Processing block: 'Configuration block'")
    logger.info("  Block has tags: ['config']")
    logger.info("  Tags filter: ['config', 'deploy']")
    logger.info("  Match: YES (config in filter)")
    logger.info("")

    for task in play.tasks[0].tasks:  # type: ignore
        if any(tag in tags_filter for tag in task.tags):
            logger.info(f"  ✓ Executing: {task.name}")
    logger.info("")

    # PROBLEM: Gap in execution causes role tracking reset!
    logger.info("PHASE 3: Transitioning to regular tasks")
    logger.info("-" * 80)
    logger.info("")
    logger.info("⚠️  PROBLEM: Internal logic detects a 'gap' between block and tasks")
    logger.info("⚠️  This gap triggers role dependency re-evaluation")
    logger.info("")

    # PROBLEM REPRODUCTION: Reset role tracking
    role_mgr.reset_tracking()
    logger.info("")

    # Phase 4: Execute regular tasks with tag 'deploy'
    logger.info("PHASE 4: Execute tasks with tag 'deploy'")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Processing remaining tasks:")

    # PROBLEM: Role dependencies get re-executed!
    logger.info("")
    logger.info("⚠️  PROBLEM: Before executing deploy tasks, re-checking role dependencies")
    logger.info("")
    logger.info("Re-evaluating role dependencies:")
    for role in play.roles:
        role_mgr.execute_role(role.name, tags_filter)
    logger.info("")

    logger.info("🐛 BUG: 'common' role executed TWICE!")
    logger.info("")

    # Execute deploy tasks
    for task in play.tasks[1:]:  # type: ignore
        if isinstance(task, Task) and any(tag in tags_filter for tag in task.tags):
            logger.info(f"  ✓ Executing: {task.name}")
    logger.info("")

    # Analysis
    logger.info("=" * 80)
    logger.info("ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("What happened:")
    logger.info("  1. Roles executed (common → app)")
    logger.info("  2. Block with tag 'config' executed")
    logger.info("  3. Role tracking RESET (incorrectly!)")
    logger.info("  4. Roles executed AGAIN (common → app)")
    logger.info("  5. Tasks with tag 'deploy' executed")
    logger.info("")

    logger.info("Why this is bad:")
    logger.info("  ❌ 'common' role ran TWICE (wasted execution)")
    logger.info("  ❌ Breaks idempotency assumptions")
    logger.info("  ❌ Performance degradation (imagine 10+ dependencies)")
    logger.info("  ❌ Potential state corruption if role isn't idempotent")
    logger.info("")

    logger.info("Root cause:")
    logger.info("  • Tag filtering creates 'gaps' in execution")
    logger.info("  • Block execution ends → gap detected")
    logger.info("  • Regular task execution starts → role re-evaluation triggered")
    logger.info("  • Role deduplication tracking gets reset")
    logger.info("  • Dependencies execute again")
    logger.info("")

    logger.info("Expected behavior:")
    logger.info("  ✅ Roles should execute exactly ONCE")
    logger.info("  ✅ Tag filtering should NOT affect role deduplication")
    logger.info("  ✅ Blocks should NOT trigger role re-evaluation")
    logger.info("  ✅ Role tracking should persist across all task types")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Fix role deduplication:")
    logger.info("  ✅ Maintain global role execution tracking")
    logger.info("  ✅ Don't reset tracking between blocks and tasks")
    logger.info("  ✅ Tag filtering should only affect task selection")
    logger.info("  ✅ Once a role runs, it should never run again in same play")
    logger.info("")

    logger.info("Proper execution flow:")
    logger.info("  1. Evaluate all roles and dependencies ONCE at start")
    logger.info("  2. Execute roles in dependency order")
    logger.info("  3. Mark roles as executed globally")
    logger.info("  4. Execute tasks (blocks, regular tasks) based on tags")
    logger.info("  5. NEVER re-evaluate role dependencies during task execution")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Block with tag causing role re-run:")
    logger.info("  1. Tags create execution 'gaps' between blocks and tasks")
    logger.info("  2. Gaps trigger incorrect role dependency re-evaluation")
    logger.info("  3. Role deduplication tracking gets reset")
    logger.info("  4. Dependent roles execute multiple times")
    logger.info("  5. Breaks idempotency and wastes resources")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
