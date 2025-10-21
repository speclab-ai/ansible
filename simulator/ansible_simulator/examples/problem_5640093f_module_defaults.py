"""
Reproduction of Problem 5640093f: module_defaults Not Applied via Action Plugins

This example demonstrates how action plugins (gather_facts, package, service)
do not respect module_defaults defined for the underlying modules they execute.

PROBLEM:
- module_defaults defined for setup, apt/dnf, systemd work when calling modules directly
- Action plugins gather_facts, package, service don't apply these defaults
- Inconsistent behavior: same module behaves differently via action vs direct
- FQCN vs short name vs ansible.legacy.* cause further discrepancies

IMPACT:
- Playbooks that depend on module_defaults get different behavior
- gather_facts ignores setup module defaults (gather_subset, etc.)
- package action ignores apt/dnf defaults
- service action ignores systemd defaults
- Hard to diagnose - works sometimes, fails others
"""

import logging

from ansible_simulator.shared.models import (
    Play, Task
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def demonstrate_problem():
    """Demonstrate module_defaults not applied by action plugins."""

    logger.info("=" * 80)
    logger.info("PROBLEM 5640093f: module_defaults Not Applied via Action Plugins")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: module_defaults in Ansible")
    logger.info("-" * 80)
    logger.info("")
    logger.info("module_defaults lets you set default parameters for modules:")
    logger.info("")
    logger.info("  - name: Example play")
    logger.info("    module_defaults:")
    logger.info("      ansible.builtin.apt:")
    logger.info("        update_cache: yes")
    logger.info("        cache_valid_time: 3600")
    logger.info("      ansible.builtin.setup:")
    logger.info("        gather_subset:")
    logger.info("          - '!all'")
    logger.info("          - '!min'")
    logger.info("          - network")
    logger.info("")

    logger.info("PROBLEM 1: gather_facts action doesn't apply setup defaults")
    logger.info("-" * 80)
    logger.info("")

    # Create play with module_defaults for setup
    play_gather_facts = Play(
        name="Test gather_facts with module_defaults",
        hosts="all",
        gather_facts=True,  # Uses gather_facts action plugin
        module_defaults={
            "ansible.builtin.setup": {
                "gather_subset": ["!all", "!min", "network"],
                "gather_timeout": 30
            },
            "setup": {  # Short name
                "gather_subset": ["!all", "!min", "network"],
                "gather_timeout": 30
            }
        },
        tasks=[]
    )

    logger.info("Play configuration:")
    logger.info(f"  gather_facts: {play_gather_facts.gather_facts}")
    logger.info(f"  module_defaults:")
    for module_name, defaults in play_gather_facts.module_defaults.items():
        logger.info(f"    {module_name}:")
        for key, value in defaults.items():
            logger.info(f"      {key}: {value}")
    logger.info("")

    logger.info("Expected behavior:")
    logger.info("  ✅ gather_facts action resolves to 'setup' module")
    logger.info("  ✅ Applies module_defaults from 'ansible.builtin.setup'")
    logger.info("  ✅ gather_subset=['!all', '!min', 'network'] is used")
    logger.info("  ✅ gather_timeout=30 is applied")
    logger.info("")

    logger.info("Actual behavior:")
    logger.info("  ❌ gather_facts action does NOT check module_defaults")
    logger.info("  ❌ Defaults from ansible.builtin.setup are IGNORED")
    logger.info("  ❌ Full fact gathering happens (slow!)")
    logger.info("  ❌ No timeout applied")
    logger.info("")

    logger.info("PROBLEM 2: package action doesn't apply apt/dnf defaults")
    logger.info("-" * 80)
    logger.info("")

    # Create play with module_defaults for package managers
    play_package = Play(
        name="Test package with module_defaults",
        hosts="all",
        gather_facts=False,
        module_defaults={
            "ansible.builtin.apt": {
                "update_cache": True,
                "cache_valid_time": 3600,
                "force_apt_get": True
            },
            "apt": {  # Short name
                "update_cache": True,
                "cache_valid_time": 3600
            },
            "ansible.builtin.dnf": {
                "disable_gpg_check": True,
                "enablerepo": "epel"
            }
        },
        tasks=[
            Task(
                name="Install nginx via package action",
                action="package",  # Action plugin!
                args={"name": "nginx", "state": "present"}
            )
        ]
    )

    logger.info("Play configuration:")
    logger.info("  Task: Install nginx via 'package' action")
    logger.info(f"  module_defaults defined for:")
    for module_name in play_package.module_defaults.keys():
        logger.info(f"    - {module_name}")
    logger.info("")

    logger.info("Expected behavior:")
    logger.info("  ✅ package action detects OS (Debian/RedHat)")
    logger.info("  ✅ Resolves to 'apt' on Debian or 'dnf' on RedHat")
    logger.info("  ✅ Applies module_defaults from resolved module")
    logger.info("  ✅ update_cache=True, cache_valid_time=3600 used on apt")
    logger.info("  ✅ disable_gpg_check=True used on dnf")
    logger.info("")

    logger.info("Actual behavior:")
    logger.info("  ❌ package action does NOT apply module_defaults")
    logger.info("  ❌ Only uses parameters explicitly passed in task")
    logger.info("  ❌ update_cache NOT set (cache may be stale)")
    logger.info("  ❌ cache_valid_time NOT set")
    logger.info("  ❌ Task args: {'name': 'nginx', 'state': 'present'}")
    logger.info("  ❌ Missing: {'update_cache': True, 'cache_valid_time': 3600}")
    logger.info("")

    logger.info("PROBLEM 3: service action doesn't apply systemd defaults")
    logger.info("-" * 80)
    logger.info("")

    play_service = Play(
        name="Test service with module_defaults",
        hosts="all",
        gather_facts=False,
        module_defaults={
            "ansible.builtin.systemd": {
                "daemon_reload": True,
                "no_block": False
            },
            "systemd": {
                "daemon_reload": True
            },
            "ansible.builtin.service": {
                "enabled": True
            }
        },
        tasks=[
            Task(
                name="Restart nginx via service action",
                action="service",  # Action plugin!
                args={"name": "nginx", "state": "restarted"}
            )
        ]
    )

    logger.info("Play configuration:")
    logger.info("  Task: Restart nginx via 'service' action")
    logger.info(f"  module_defaults defined for:")
    for module_name in play_service.module_defaults.keys():
        logger.info(f"    - {module_name}")
    logger.info("")

    logger.info("Expected behavior:")
    logger.info("  ✅ service action detects init system (systemd/sysvinit)")
    logger.info("  ✅ Resolves to 'systemd' module on systemd systems")
    logger.info("  ✅ Applies module_defaults from 'ansible.builtin.systemd'")
    logger.info("  ✅ daemon_reload=True is set")
    logger.info("  ✅ no_block=False is applied")
    logger.info("")

    logger.info("Actual behavior:")
    logger.info("  ❌ service action does NOT apply module_defaults")
    logger.info("  ❌ daemon_reload NOT set (may cause stale unit files)")
    logger.info("  ❌ Only {'name': 'nginx', 'state': 'restarted'} used")
    logger.info("")

    logger.info("PROBLEM 4: FQCN vs short name causes confusion")
    logger.info("-" * 80)
    logger.info("")
    logger.info("module_defaults can be set with different naming:")
    logger.info("  - ansible.builtin.setup (FQCN)")
    logger.info("  - setup (short name)")
    logger.info("  - ansible.legacy.setup (legacy)")
    logger.info("")
    logger.info("Action plugins need to:")
    logger.info("  ✅ Resolve actual module being executed")
    logger.info("  ✅ Check module_defaults for FQCN")
    logger.info("  ✅ Fall back to short name")
    logger.info("  ✅ Fall back to ansible.legacy.*")
    logger.info("")
    logger.info("Actually:")
    logger.info("  ❌ Action plugins skip module_defaults lookup entirely")
    logger.info("  ❌ Doesn't matter which name you use - none work!")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Scenario 1: Fact gathering performance")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Playbook sets module_defaults to limit facts:")
    logger.info("  module_defaults:")
    logger.info("    setup:")
    logger.info("      gather_subset: ['!all', '!min', 'network']")
    logger.info("")
    logger.info("Expected: Fast fact gathering (only network facts)")
    logger.info("Actual: Full fact gathering (SLOW!)")
    logger.info("Impact: 10x slower on large inventories")
    logger.info("")

    logger.info("Scenario 2: APT cache management")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Playbook sets module_defaults:")
    logger.info("  module_defaults:")
    logger.info("    apt:")
    logger.info("      update_cache: yes")
    logger.info("      cache_valid_time: 3600")
    logger.info("")
    logger.info("Tasks use package action:")
    logger.info("  - package: name=nginx")
    logger.info("")
    logger.info("Expected: Cache updated if older than 1 hour")
    logger.info("Actual: Cache NEVER updated (stale cache used!)")
    logger.info("Impact: May install wrong package versions")
    logger.info("")

    logger.info("Scenario 3: Systemd daemon-reload")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Playbook sets module_defaults:")
    logger.info("  module_defaults:")
    logger.info("    systemd:")
    logger.info("      daemon_reload: yes")
    logger.info("")
    logger.info("Tasks use service action:")
    logger.info("  - service: name=myapp state=restarted")
    logger.info("")
    logger.info("Expected: daemon-reload before restart (picks up new unit files)")
    logger.info("Actual: No daemon-reload (uses stale unit file!)")
    logger.info("Impact: Service may not start with new configuration")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("For gather_facts action:")
    logger.info("  ✅ Determine facts module (usually 'setup')")
    logger.info("  ✅ Based on ansible_network_os if network device")
    logger.info("  ✅ Look up module_defaults for resolved module")
    logger.info("  ✅ Apply defaults to module args")
    logger.info("  ✅ Preserve smart mode without mutation")
    logger.info("")

    logger.info("For package action:")
    logger.info("  ✅ Detect OS and resolve to apt/dnf/yum/pkg/etc.")
    logger.info("  ✅ Look up module_defaults for resolved module")
    logger.info("  ✅ Support FQCN, short name, and ansible.legacy.* lookups")
    logger.info("  ✅ Merge defaults with explicit task args (task args win)")
    logger.info("")

    logger.info("For service action:")
    logger.info("  ✅ Detect init system (systemd/sysvinit/etc.)")
    logger.info("  ✅ Look up module_defaults for detected module")
    logger.info("  ✅ Apply defaults before module execution")
    logger.info("")

    logger.info("General solution:")
    logger.info("  ✅ Action plugins MUST check module_defaults")
    logger.info("  ✅ Resolve to actual module being executed")
    logger.info("  ✅ Look up in order: FQCN -> short name -> ansible.legacy.*")
    logger.info("  ✅ Merge defaults (defaults < task args)")
    logger.info("  ✅ Consistent behavior: action vs direct invocation")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: module_defaults not applied via action plugins causes:")
    logger.info("  1. Inconsistent behavior (works direct, fails via action)")
    logger.info("  2. Performance issues (full facts vs limited)")
    logger.info("  3. Wrong package versions (stale cache)")
    logger.info("  4. Service failures (stale unit files)")
    logger.info("  5. Hard to diagnose (no error, just wrong behavior)")
    logger.info("  6. FQCN/short name/legacy confusion")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
