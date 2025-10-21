"""
Reproduction of Problem 4c5ce5a1: Module Respawn & libselinux-python

This example demonstrates how modules requiring system-specific Python bindings
(libselinux-python, python-apt, etc.) fail when those bindings are not available
in Ansible's Python interpreter, and how module respawn can solve this.

PROBLEM:
- Modules like dnf, yum, apt need system-specific Python bindings
- These bindings may not be available in Ansible's Python environment
- Especially problematic on RHEL8+ with Python 3.8+ (no libselinux-python)
- No mechanism to respawn modules under compatible interpreter
- SELinux operations require libselinux-python even for basic checks

IMPACT:
- Modules fail with ImportError on systems with incompatible Python
- Users must install bindings in Ansible's venv (difficult/impossible)
- Limits Ansible's portability across Python environments
- SELinux-aware modules broken on newer systems

SCENARIO:
```
System: RHEL 9 with Python 3.9 (system) and Python 3.11 (Ansible venv)

Ansible Controller:
  - Python 3.11 (venv: /opt/ansible/venv)
  - libselinux-python NOT available for Python 3.11

Target Host:
  - Python 3.9 (system: /usr/bin/python3.9)
  - libselinux-python AVAILABLE for Python 3.9

Module Execution:
  1. Ansible runs dnf module with Python 3.11
  2. dnf module tries: import selinux
  3. ImportError: No module named 'selinux'
  4. Module fails!

Expected (with respawn):
  1. Ansible runs dnf module with Python 3.11
  2. Module detects missing selinux binding
  3. Module requests respawn with /usr/bin/python3.9
  4. Ansible reruns module with Python 3.9
  5. import selinux succeeds
  6. Module works!
```
"""

import logging
import sys
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class InterpreterDiscovery:
    """
    Simulates interpreter discovery on target host.

    PROBLEM REPRODUCTION (4c5ce5a1):
    - Finds available Python interpreters
    - Checks for required bindings
    - No automatic respawn mechanism
    """

    def __init__(self):
        # Simulate discovered interpreters on target
        self.available_interpreters = {
            "/usr/bin/python3.11": {
                "version": "3.11.2",
                "bindings": []  # No system bindings in venv!
            },
            "/usr/bin/python3.9": {
                "version": "3.9.16",
                "bindings": ["selinux", "rpm", "dnf", "yum"]
            },
            "/usr/bin/python2.7": {
                "version": "2.7.18",
                "bindings": ["selinux", "rpm", "yum"]
            }
        }

    def find_compatible_interpreter(self, required_bindings: List[str]) -> Optional[str]:
        """Find interpreter with required bindings."""
        for interpreter, info in self.available_interpreters.items():
            if all(binding in info["bindings"] for binding in required_bindings):
                return interpreter
        return None


class ModuleExecutor:
    """
    Simulates module execution.

    PROBLEM REPRODUCTION (4c5ce5a1):
    - Tries to import required bindings
    - Fails if not available
    - No respawn mechanism (should respawn but doesn't!)
    """

    def __init__(self, interpreter: str, discovery: InterpreterDiscovery):
        self.interpreter = interpreter
        self.discovery = discovery
        self.available_bindings = discovery.available_interpreters[interpreter]["bindings"]

    def execute_dnf_module(self, package_name: str) -> Dict[str, Any]:
        """
        Execute dnf module.

        PROBLEM: Fails if dnf/rpm/selinux bindings missing, no respawn!
        """
        logger.info(f"  Executing dnf module with {self.interpreter}")

        # Check for required bindings
        required = ["dnf", "rpm", "selinux"]

        for binding in required:
            if binding not in self.available_bindings:
                logger.error(f"  ❌ ImportError: No module named '{binding}'")
                logger.error(f"  ❌ Module execution FAILED")

                # PROBLEM: Should request respawn here, but doesn't!
                logger.warning("  ⚠️  PROBLEM 4c5ce5a1: No respawn mechanism")
                logger.warning("  ⚠️  Should respawn with compatible interpreter")

                # Show what should happen
                compatible = self.discovery.find_compatible_interpreter(required)
                if compatible:
                    logger.info(f"  💡 Compatible interpreter available: {compatible}")
                    logger.info(f"  💡 But no automatic respawn!")

                return {
                    "failed": True,
                    "msg": f"Failed to import required Python library ({binding})",
                    "exception": f"ImportError: No module named '{binding}'"
                }

        # If we get here, all bindings available
        logger.info("  ✅ All required bindings available")
        return {
            "changed": True,
            "msg": f"Package {package_name} installed",
            "rc": 0
        }

    def execute_apt_module(self, package_name: str) -> Dict[str, Any]:
        """
        Execute apt module.

        PROBLEM: Fails if apt bindings missing, no respawn!
        """
        logger.info(f"  Executing apt module with {self.interpreter}")

        # Check for required bindings
        required = ["apt", "apt_pkg"]  # python-apt / python3-apt

        for binding in required:
            if binding not in self.available_bindings:
                logger.error(f"  ❌ ImportError: No module named '{binding}'")
                logger.error(f"  ❌ Module execution FAILED")
                logger.warning("  ⚠️  PROBLEM 4c5ce5a1: No respawn mechanism")

                return {
                    "failed": True,
                    "msg": f"Failed to import required Python library ({binding})"
                }

        logger.info("  ✅ All required bindings available")
        return {
            "changed": True,
            "msg": f"Package {package_name} installed"
        }


class SELinuxModule:
    """
    Simulates SELinux operations in module_utils.

    PROBLEM REPRODUCTION (4c5ce5a1):
    - Requires libselinux-python for basic operations
    - No fallback implementation
    - Fails entirely if binding missing
    """

    def __init__(self, has_selinux_binding: bool):
        self.has_selinux_binding = has_selinux_binding

    def is_selinux_enabled(self) -> bool:
        """
        Check if SELinux is enabled.

        PROBLEM: Requires libselinux-python even for this basic check!
        """
        if not self.has_selinux_binding:
            logger.error("  ❌ ImportError: No module named 'selinux'")
            logger.error("  ❌ Cannot check SELinux status")
            logger.warning("  ⚠️  PROBLEM 4c5ce5a1: Should be able to check without binding")
            logger.warning("  ⚠️  Could read /sys/fs/selinux/enforce instead!")
            raise ImportError("No module named 'selinux'")

        # With binding, can check
        return True

    def get_file_context(self, path: str) -> Optional[str]:
        """Get file SELinux context."""
        if not self.has_selinux_binding:
            raise ImportError("No module named 'selinux'")

        return "unconfined_u:object_r:user_home_t:s0"


def demonstrate_problem():
    """Demonstrate module respawn problem."""

    logger.info("=" * 80)
    logger.info("PROBLEM 4c5ce5a1: Module Respawn & libselinux-python")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: System-specific Python bindings")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Ansible modules often need system-specific bindings:")
    logger.info("  • dnf/yum modules → python-dnf, python-rpm, libselinux-python")
    logger.info("  • apt modules → python-apt (python3-apt)")
    logger.info("  • SELinux operations → libselinux-python")
    logger.info("")
    logger.info("Problem: These bindings may not be available in Ansible's Python!")
    logger.info("")
    logger.info("Scenario:")
    logger.info("  • Ansible runs in Python 3.11 venv (/opt/ansible/venv/bin/python)")
    logger.info("  • System Python 3.9 has all bindings (/usr/bin/python3.9)")
    logger.info("  • Bindings are compiled C extensions, can't install in venv easily")
    logger.info("")

    # Create discovery
    discovery = InterpreterDiscovery()

    logger.info("Available interpreters on target:")
    for interp, info in discovery.available_interpreters.items():
        logger.info(f"  {interp}: Python {info['version']}")
        logger.info(f"    Bindings: {', '.join(info['bindings']) if info['bindings'] else 'none'}")
    logger.info("")

    logger.info("PROBLEM 1: dnf module fails without bindings")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Task: Install nginx with dnf module")
    logger.info("Ansible interpreter: /usr/bin/python3.11 (venv, no bindings)")
    logger.info("")

    executor = ModuleExecutor("/usr/bin/python3.11", discovery)
    result = executor.execute_dnf_module("nginx")

    logger.info("")
    logger.info(f"Result: {result}")
    logger.info("")
    logger.info("❌ PROBLEM: Module failed due to missing bindings")
    logger.info("❌ No mechanism to respawn with compatible interpreter")
    logger.info("")

    logger.info("PROBLEM 2: SELinux operations fail without libselinux-python")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Attempting basic SELinux check:")
    selinux = SELinuxModule(has_selinux_binding=False)

    try:
        enabled = selinux.is_selinux_enabled()
    except ImportError as e:
        logger.info("")
        logger.info("❌ PROBLEM: Even basic SELinux check requires binding")
        logger.info("❌ Could read /sys/fs/selinux/enforce without binding!")
        logger.info("")

    logger.info("SOLUTION: Module respawn mechanism")
    logger.info("-" * 80)
    logger.info("")

    logger.info("How respawn should work:")
    logger.info("")
    logger.info("Step 1: Module execution begins with Python 3.11")
    logger.info("  def main():")
    logger.info("      try:")
    logger.info("          import dnf")
    logger.info("          import rpm")
    logger.info("          import selinux")
    logger.info("      except ImportError:")
    logger.info("          # Request respawn!")
    logger.info("          return {'respawn_needed': True,")
    logger.info("                  'required_bindings': ['dnf', 'rpm', 'selinux']}")
    logger.info("")

    logger.info("Step 2: Controller receives respawn request")
    logger.info("  if result.get('respawn_needed'):")
    logger.info("      # Find compatible interpreter")
    logger.info("      compatible = discover_interpreter(required_bindings)")
    logger.info("      # Rerun with compatible interpreter")
    logger.info("      result = execute_module(module, interpreter=compatible)")
    logger.info("")

    logger.info("Step 3: Module executes with Python 3.9 (has bindings)")
    logger.info("  # Now imports succeed!")
    logger.info("  import dnf  # ✅")
    logger.info("  import rpm  # ✅")
    logger.info("  import selinux  # ✅")
    logger.info("")

    logger.info("Demonstrating successful execution with compatible interpreter:")
    logger.info("")

    executor_compatible = ModuleExecutor("/usr/bin/python3.9", discovery)
    result_success = executor_compatible.execute_dnf_module("nginx")

    logger.info("")
    logger.info(f"Result: {result_success}")
    logger.info("")
    logger.info("✅ SUCCESS: Module works with compatible interpreter")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Issue #1: RHEL 8/9 with modern Python")
    logger.info("-" * 80)
    logger.info("  RHEL 8+: Python 3.6/3.8/3.9 (system)")
    logger.info("  Ansible: Python 3.11 (venv or user install)")
    logger.info("  Problem:")
    logger.info("    • libselinux-python only for system Python")
    logger.info("    • dnf/yum modules fail completely")
    logger.info("    • Must use system Python for Ansible (not recommended)")
    logger.info("")

    logger.info("Issue #2: Debian/Ubuntu with python3-apt")
    logger.info("-" * 80)
    logger.info("  System: Python 3.10 with python3-apt installed")
    logger.info("  Ansible: Python 3.11 (venv)")
    logger.info("  Problem:")
    logger.info("    • python3-apt is .deb package, not pip installable")
    logger.info("    • apt module fails in venv")
    logger.info("    • Hard to maintain Ansible in venv")
    logger.info("")

    logger.info("Issue #3: SELinux awareness limited")
    logger.info("-" * 80)
    logger.info("  Many modules do SELinux checks:")
    logger.info("    • File modules (copy, template, file)")
    logger.info("    • Package modules (dnf, yum)")
    logger.info("    • Service modules")
    logger.info("  Problem:")
    logger.info("    • All require libselinux-python")
    logger.info("    • Basic checks could use /sys/fs/selinux/*")
    logger.info("    • Over-dependency on binding")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Part 1: Module respawn mechanism")
    logger.info("  ✅ Modules can request respawn with required bindings")
    logger.info("  ✅ Controller discovers compatible interpreter")
    logger.info("  ✅ Module automatically rerun with compatible Python")
    logger.info("  ✅ Transparent to playbook author")
    logger.info("")

    logger.info("Part 2: SELinux compatibility layer")
    logger.info("  ✅ Basic operations without libselinux-python:")
    logger.info("      • is_selinux_enabled() → read /sys/fs/selinux/enforce")
    logger.info("      • get_enforcing_mode() → read /sys/fs/selinux/enforce")
    logger.info("  ✅ Advanced operations still need binding:")
    logger.info("      • set_file_context()")
    logger.info("      • get_selinux_booleans()")
    logger.info("  ✅ Graceful fallback, clear error messages")
    logger.info("")

    logger.info("Part 3: Interpreter discovery caching")
    logger.info("  ✅ Discovery results cached per host")
    logger.info("  ✅ Avoid repeated discovery overhead")
    logger.info("  ✅ Respect ansible_python_interpreter override")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Module respawn & libselinux-python causes:")
    logger.info("  1. Modules fail on modern systems (RHEL8+, Python 3.8+)")
    logger.info("  2. Cannot use Ansible in venv reliably")
    logger.info("  3. Package modules (dnf, yum, apt) broken without bindings")
    logger.info("  4. SELinux operations require libselinux-python unnecessarily")
    logger.info("  5. No automatic respawn under compatible interpreter")
    logger.info("  6. Limits Ansible portability across Python environments")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
