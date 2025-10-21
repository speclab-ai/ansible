"""
Reproduction of Problem 9142be2f: Python Module Shebang Not Honored

This example demonstrates how Ansible rewrites module shebangs to /usr/bin/python
instead of respecting the explicit interpreter declaration in the module file.

PROBLEM:
- Python modules can specify interpreter via shebang: #!/usr/bin/python3.8
- Ansible's ModuleCommon rewrites ALL module shebangs to /usr/bin/python
- Ignores explicit interpreter declarations
- ansible_python_interpreter overrides shebang (expected)
- But without that, should use module's shebang (doesn't)

IMPACT:
- Cannot target specific Python versions via shebang
- Modules requiring specific Python features break
- Module authors lose control over interpreter selection
- Workaround: set ansible_python_interpreter everywhere (tedious)

EXPECTED:
- If ansible_python_interpreter is set → use it (override shebang)
- If ansible_python_interpreter NOT set:
  - If module has shebang → use it
  - If no shebang → use /usr/bin/python (discovery)
"""

import logging
import re
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ModuleCommon:
    """
    Simulates Ansible's module_common.py module payload construction.

    PROBLEM REPRODUCTION (9142be2f):
    - Always rewrites shebang to /usr/bin/python
    - Ignores module's explicit interpreter declaration
    """

    def __init__(self):
        self.default_python = "/usr/bin/python"

    def process_module(self, module_source: str, ansible_python_interpreter: Optional[str] = None) -> str:
        """
        Process module source and construct final payload.

        PROBLEM: Always rewrites shebang, ignoring module's choice.

        Args:
            module_source: The module source code
            ansible_python_interpreter: Override from ansible_python_interpreter variable

        Returns:
            Modified module source
        """
        # Extract original shebang
        original_shebang = self._extract_shebang(module_source)

        # PROBLEM: Determine interpreter (always ignores module shebang!)
        if ansible_python_interpreter:
            # User explicitly set interpreter - use it
            final_interpreter = ansible_python_interpreter
            logger.info(f"  Using ansible_python_interpreter: {final_interpreter}")
        else:
            # PROBLEM: Should check module shebang here, but doesn't!
            # Instead, just uses default
            final_interpreter = self.default_python
            logger.warning(
                f"  ⚠️  PROBLEM 9142be2f: Ignoring module shebang '{original_shebang}'"
            )
            logger.warning(
                f"  ⚠️  Rewriting to: {final_interpreter}"
            )

        # Rewrite shebang
        modified_source = self._rewrite_shebang(module_source, final_interpreter)

        return modified_source

    def _extract_shebang(self, source: str) -> str:
        """Extract shebang from module source."""
        lines = source.split('\n')
        if lines and lines[0].startswith('#!'):
            return lines[0]
        return ""

    def _rewrite_shebang(self, source: str, interpreter: str) -> str:
        """Rewrite module shebang."""
        lines = source.split('\n')
        if lines and lines[0].startswith('#!'):
            lines[0] = f"#!{interpreter}"
        else:
            lines.insert(0, f"#!{interpreter}")
        return '\n'.join(lines)


def demonstrate_problem():
    """Demonstrate shebang rewriting problem."""

    logger.info("=" * 80)
    logger.info("PROBLEM 9142be2f: Python Module Shebang Not Honored")
    logger.info("=" * 80)
    logger.info("")

    # Create module common processor
    module_common = ModuleCommon()

    # Test Case 1: Module with specific Python version
    logger.info("TEST CASE 1: Module with explicit Python 3.8 shebang")
    logger.info("-" * 80)
    logger.info("")

    module1_source = """#!/usr/bin/python3.8
# Module requiring Python 3.8+ (walrus operator, etc.)

from ansible.module_utils.basic import AnsibleModule

def main():
    # Uses Python 3.8+ features
    if (data := get_data()):
        process(data)

if __name__ == '__main__':
    main()
"""

    logger.info("Original module shebang: #!/usr/bin/python3.8")
    logger.info("")
    logger.info("Processing module (no ansible_python_interpreter set):")

    processed1 = module_common.process_module(module1_source)

    logger.info("")
    logger.info("Result:")
    final_shebang1 = processed1.split('\n')[0]
    logger.info(f"  Final shebang: {final_shebang1}")
    logger.info("")
    logger.info("❌ PROBLEM: Module explicitly requested Python 3.8, got /usr/bin/python")
    logger.info("❌ Impact: Module will fail if /usr/bin/python is Python 2.7 or 3.6")
    logger.info("")

    # Test Case 2: Module with Python 3 requirement
    logger.info("TEST CASE 2: Module with Python 3 shebang")
    logger.info("-" * 80)
    logger.info("")

    module2_source = """#!/usr/bin/python3
# Module requiring Python 3

from ansible.module_utils.basic import AnsibleModule

def main():
    # Uses Python 3 features (type hints, f-strings, etc.)
    result: dict = {"changed": False}
    message = f"Hello from Python 3"

if __name__ == '__main__':
    main()
"""

    logger.info("Original module shebang: #!/usr/bin/python3")
    logger.info("")
    logger.info("Processing module (no ansible_python_interpreter set):")

    processed2 = module_common.process_module(module2_source)

    logger.info("")
    logger.info("Result:")
    final_shebang2 = processed2.split('\n')[0]
    logger.info(f"  Final shebang: {final_shebang2}")
    logger.info("")
    logger.info("❌ PROBLEM: Module requested Python 3, got /usr/bin/python")
    logger.info("❌ Impact: Will fail if /usr/bin/python points to Python 2.7")
    logger.info("")

    # Test Case 3: With ansible_python_interpreter set
    logger.info("TEST CASE 3: Module with shebang + ansible_python_interpreter set")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Original module shebang: #!/usr/bin/python3.8")
    logger.info("ansible_python_interpreter: /usr/bin/python3.10")
    logger.info("")
    logger.info("Processing module (WITH ansible_python_interpreter):")

    processed3 = module_common.process_module(module1_source, ansible_python_interpreter="/usr/bin/python3.10")

    logger.info("")
    logger.info("Result:")
    final_shebang3 = processed3.split('\n')[0]
    logger.info(f"  Final shebang: {final_shebang3}")
    logger.info("")
    logger.info("✅ CORRECT: ansible_python_interpreter overrides shebang")
    logger.info("   This is expected behavior when user explicitly sets interpreter")
    logger.info("")

    # Test Case 4: Module with no shebang
    logger.info("TEST CASE 4: Module without shebang")
    logger.info("-" * 80)
    logger.info("")

    module4_source = """# Module without shebang

from ansible.module_utils.basic import AnsibleModule

def main():
    pass

if __name__ == '__main__':
    main()
"""

    logger.info("Original module: No shebang")
    logger.info("")
    logger.info("Processing module (no ansible_python_interpreter set):")

    processed4 = module_common.process_module(module4_source)

    logger.info("")
    logger.info("Result:")
    final_shebang4 = processed4.split('\n')[0]
    logger.info(f"  Final shebang: {final_shebang4}")
    logger.info("")
    logger.info("✅ ACCEPTABLE: No shebang → use default /usr/bin/python")
    logger.info("   This is reasonable fallback behavior")
    logger.info("")

    # Analysis
    logger.info("=" * 80)
    logger.info("ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Current behavior (WRONG):")
    logger.info("  1. Check if ansible_python_interpreter is set")
    logger.info("     YES → use it (correct)")
    logger.info("     NO → use /usr/bin/python (WRONG - ignores module shebang!)")
    logger.info("")

    logger.info("Expected behavior (CORRECT):")
    logger.info("  1. Check if ansible_python_interpreter is set")
    logger.info("     YES → use it")
    logger.info("     NO → Check module shebang")
    logger.info("       HAS shebang → use it")
    logger.info("       NO shebang → use /usr/bin/python (discovery)")
    logger.info("")

    logger.info("Real-world scenarios:")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Scenario 1: Module uses Python 3.8+ features")
    logger.info("  Module author: #!/usr/bin/python3.8")
    logger.info("  Target system: /usr/bin/python → Python 2.7")
    logger.info("  Current: Module fails (Python 2.7 can't run it)")
    logger.info("  Expected: Module uses Python 3.8 (from shebang)")
    logger.info("")

    logger.info("Scenario 2: Module requires Python 3")
    logger.info("  Module author: #!/usr/bin/python3")
    logger.info("  Target system: /usr/bin/python → Python 2.7")
    logger.info("  Current: Module fails (syntax errors in Python 2)")
    logger.info("  Expected: Module uses Python 3 (from shebang)")
    logger.info("")

    logger.info("Scenario 3: Mixed Python environments")
    logger.info("  Module author: #!/usr/bin/python3.9")
    logger.info("  Target system: Has Python 2.7, 3.6, 3.9")
    logger.info("  Current: Module uses Python 2.7 (default), fails")
    logger.info("  Expected: Module uses Python 3.9 (from shebang)")
    logger.info("")

    logger.info("=" * 80)
    logger.info("WORKAROUNDS")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Current workaround (tedious):")
    logger.info("  • Set ansible_python_interpreter on EVERY host/group")
    logger.info("  • Or set in ansible.cfg globally")
    logger.info("  • Duplicates what module already specifies!")
    logger.info("")

    logger.info("Better approach (if shebang was honored):")
    logger.info("  • Module specifies interpreter requirement")
    logger.info("  • Ansible respects it by default")
    logger.info("  • Only override when truly needed")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Fix ModuleCommon to:")
    logger.info("  ✅ Check for ansible_python_interpreter (highest priority)")
    logger.info("  ✅ If not set, check module shebang")
    logger.info("  ✅ Extract interpreter from shebang (#!/usr/bin/python3.8)")
    logger.info("  ✅ Use shebang interpreter if present")
    logger.info("  ✅ Only fall back to /usr/bin/python if no shebang")
    logger.info("")

    logger.info("Precedence order:")
    logger.info("  1. ansible_python_interpreter (user override)")
    logger.info("  2. Module shebang (author's choice)")
    logger.info("  3. /usr/bin/python (default/discovery)")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: Python module shebang not honored causes:")
    logger.info("  1. Modules can't specify required Python version")
    logger.info("  2. Breaks on systems with Python 2 as default")
    logger.info("  3. Forces tedious ansible_python_interpreter everywhere")
    logger.info("  4. Module authors lose control over execution environment")
    logger.info("  5. Violates principle of least surprise")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
