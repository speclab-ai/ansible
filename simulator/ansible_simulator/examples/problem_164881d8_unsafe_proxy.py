"""
Reproduction of Problem 164881d8: UnsafeProxy Deprecation Inconsistency

This example demonstrates how UnsafeProxy is still used in many places despite
new wrap_var and AnsibleUnsafe classes, leading to inconsistent variable wrapping.

PROBLEM:
- New recommended way: wrap_var() and AnsibleUnsafe* classes
- Old deprecated way: UnsafeProxy class
- Many code paths still use UnsafeProxy
- Inconsistent: same data wrapped differently in different contexts
- No clear migration path
- Deprecation warnings not shown everywhere

IMPACT:
- Code using both old and new approaches
- Difficult to migrate off UnsafeProxy
- Inconsistent behavior with templating
- Some code wraps with UnsafeProxy, other code expects AnsibleUnsafe*
- Hard to track which approach is used where

BACKGROUND:
"Unsafe" variables contain untrusted/untemplated data:
- Output from shell/command modules
- File contents read with lookup plugins
- Data that should NOT be templated again

Two wrapping approaches:
1. OLD: UnsafeProxy(data) - wraps in proxy object
2. NEW: wrap_var(data) - converts to AnsibleUnsafe* types
"""

import logging
from typing import Any

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# OLD APPROACH: UnsafeProxy (deprecated)
# ============================================================================

class UnsafeProxy:
    """
    OLD/DEPRECATED way to mark variables as unsafe.

    PROBLEM: Still used in many places despite deprecation.
    """

    def __init__(self, obj: Any):
        self._obj = obj

    def __repr__(self):
        return f"UnsafeProxy({self._obj!r})"

    def __str__(self):
        return str(self._obj)

    def __getattr__(self, name):
        return getattr(self._obj, name)


# ============================================================================
# NEW APPROACH: AnsibleUnsafe classes
# ============================================================================

class AnsibleUnsafeText(str):
    """
    NEW way to mark text as unsafe.

    Subclass of str with special marker.
    """

    def __new__(cls, value):
        instance = super().__new__(cls, value)
        instance._is_unsafe = True  # type: ignore
        return instance

    def __repr__(self):
        return f"AnsibleUnsafeText({super().__repr__()})"


class AnsibleUnsafeBytes(bytes):
    """NEW way to mark bytes as unsafe."""

    def __new__(cls, value):
        instance = super().__new__(cls, value)
        instance._is_unsafe = True  # type: ignore
        return instance


def wrap_var(var: Any) -> Any:
    """
    NEW recommended function to wrap variables as unsafe.

    Converts to appropriate AnsibleUnsafe* type.
    """
    if isinstance(var, str):
        return AnsibleUnsafeText(var)
    elif isinstance(var, bytes):
        return AnsibleUnsafeBytes(var)
    elif isinstance(var, dict):
        return {k: wrap_var(v) for k, v in var.items()}
    elif isinstance(var, list):
        return [wrap_var(item) for item in var]
    else:
        # For other types, could use UnsafeProxy but shouldn't!
        return var


# ============================================================================
# Code paths demonstrating inconsistency
# ============================================================================

def module_returns_output_old() -> Any:
    """
    Simulates module returning output (old code path).

    PROBLEM: Uses UnsafeProxy (deprecated).
    """
    output = "command output with {{ jinja }}"

    # PROBLEM: Old code uses UnsafeProxy
    logger.info("  OLD code path: Wrapping with UnsafeProxy")
    return UnsafeProxy(output)


def module_returns_output_new() -> Any:
    """
    Simulates module returning output (new code path).

    Uses wrap_var() correctly.
    """
    output = "command output with {{ jinja }}"

    # NEW: Use wrap_var
    logger.info("  NEW code path: Wrapping with wrap_var()")
    return wrap_var(output)


def lookup_plugin_old(filename: str) -> Any:
    """
    Simulates lookup plugin (old code path).

    PROBLEM: Uses UnsafeProxy.
    """
    content = "file content with {{ variables }}"

    # PROBLEM: Uses UnsafeProxy
    logger.info("  OLD code path: Wrapping with UnsafeProxy")
    return UnsafeProxy(content)


def lookup_plugin_new(filename: str) -> Any:
    """
    Simulates lookup plugin (new code path).

    Uses wrap_var() correctly.
    """
    content = "file content with {{ variables }}"

    # NEW: Use wrap_var
    logger.info("  NEW code path: Wrapping with wrap_var()")
    return wrap_var(content)


def demonstrate_problem():
    """Demonstrate UnsafeProxy inconsistency."""

    logger.info("=" * 80)
    logger.info("PROBLEM 164881d8: UnsafeProxy Deprecation Inconsistency")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: Unsafe variable wrapping")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Why 'unsafe' variables?")
    logger.info("  • Prevent double templating")
    logger.info("  • Data from modules/plugins may contain {{ ... }}")
    logger.info("  • Should NOT be templated again")
    logger.info("")
    logger.info("Example:")
    logger.info("  1. shell module executes: echo '{{ inventory_hostname }}'")
    logger.info("  2. Output: '{{ inventory_hostname }}' (literal text)")
    logger.info("  3. Mark as unsafe to prevent templating it")
    logger.info("  4. Otherwise would try to template {{ inventory_hostname }} again!")
    logger.info("")

    logger.info("PROBLEM 1: Inconsistent wrapping across code paths")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Code path A: Module return (old):")
    output_old = module_returns_output_old()
    logger.info(f"  Result: {output_old}")
    logger.info(f"  Type: {type(output_old).__name__}")
    logger.info("")

    logger.info("Code path B: Module return (new):")
    output_new = module_returns_output_new()
    logger.info(f"  Result: {output_new}")
    logger.info(f"  Type: {type(output_new).__name__}")
    logger.info("")

    logger.info("❌ PROBLEM: Same data, different wrapping!")
    logger.info("  • Old: UnsafeProxy(str)")
    logger.info("  • New: AnsibleUnsafeText")
    logger.info("  • Inconsistent behavior downstream")
    logger.info("")

    logger.info("PROBLEM 2: Lookup plugins also inconsistent")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Lookup plugin A (old):")
    lookup_old = lookup_plugin_old("file.txt")
    logger.info(f"  Result: {lookup_old}")
    logger.info(f"  Type: {type(lookup_old).__name__}")
    logger.info("")

    logger.info("Lookup plugin B (new):")
    lookup_new = lookup_plugin_new("file.txt")
    logger.info(f"  Result: {lookup_new}")
    logger.info(f"  Type: {type(lookup_new).__name__}")
    logger.info("")

    logger.info("❌ PROBLEM: Same lookup, different wrapping!")
    logger.info("")

    logger.info("PROBLEM 3: Type checking is different")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Checking if variable is unsafe:")
    logger.info("")

    logger.info("OLD approach (UnsafeProxy):")
    logger.info(f"  isinstance(output_old, UnsafeProxy): {isinstance(output_old, UnsafeProxy)}")
    logger.info(f"  isinstance(output_old, str): {isinstance(output_old, str)}")
    logger.info("")

    logger.info("NEW approach (AnsibleUnsafeText):")
    logger.info(f"  isinstance(output_new, UnsafeProxy): {isinstance(output_new, UnsafeProxy)}")
    logger.info(f"  isinstance(output_new, str): {isinstance(output_new, str)}")
    logger.info(f"  isinstance(output_new, AnsibleUnsafeText): {isinstance(output_new, AnsibleUnsafeText)}")
    logger.info(f"  hasattr(output_new, '_is_unsafe'): {hasattr(output_new, '_is_unsafe')}")
    logger.info("")

    logger.info("❌ PROBLEM: Different type checks needed!")
    logger.info("  • Code checking isinstance(x, UnsafeProxy) fails for new approach")
    logger.info("  • Code checking hasattr(x, '_is_unsafe') fails for old approach")
    logger.info("  • No single way to detect unsafe variables")
    logger.info("")

    logger.info("PROBLEM 4: Deprecation warnings missing")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Creating UnsafeProxy:")
    _ = UnsafeProxy("test")
    logger.info("  ⚠️  No deprecation warning shown!")
    logger.info("")

    logger.info("Expected:")
    logger.info("  [DEPRECATED]: UnsafeProxy is deprecated, use wrap_var() instead")
    logger.info("")

    logger.info("❌ PROBLEM: Silent usage of deprecated class")
    logger.info("❌ Developers don't know they should migrate")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Issue #1: Code that checks for unsafe variables")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  Code that does:")
    logger.info("    if isinstance(var, UnsafeProxy):")
    logger.info("        # Don't template this")
    logger.info("")
    logger.info("  Problem:")
    logger.info("    • Fails for AnsibleUnsafeText variables")
    logger.info("    • May template data that should be unsafe")
    logger.info("    • Security implications!")
    logger.info("")

    logger.info("Issue #2: Unwrapping values")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  OLD way:")
    logger.info("    if isinstance(var, UnsafeProxy):")
    logger.info("        actual_value = var._obj")
    logger.info("")
    logger.info("  NEW way:")
    logger.info("    # AnsibleUnsafeText is already a str, just use it")
    logger.info("    actual_value = var")
    logger.info("")
    logger.info("  Problem:")
    logger.info("    • Different unwrapping logic")
    logger.info("    • Code needs to handle both")
    logger.info("")

    logger.info("Issue #3: Mixed wrapping in same playbook")
    logger.info("-" * 80)
    logger.info("")
    logger.info("  Task 1: shell module → UnsafeProxy (old code)")
    logger.info("  Task 2: command module → AnsibleUnsafeText (new code)")
    logger.info("  Task 3: lookup plugin → could be either!")
    logger.info("")
    logger.info("  Problem:")
    logger.info("    • Same playbook, different wrapping")
    logger.info("    • Difficult to reason about")
    logger.info("    • Template safety depends on code path")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Phase 1: Add deprecation warnings")
    logger.info("  ✅ UnsafeProxy.__init__() emits DeprecationWarning")
    logger.info("  ✅ Clear message: 'Use wrap_var() instead'")
    logger.info("  ✅ Developers become aware of deprecation")
    logger.info("")

    logger.info("Phase 2: Migrate all core code")
    logger.info("  ✅ Find all UnsafeProxy usage")
    logger.info("  ✅ Replace with wrap_var()")
    logger.info("  ✅ Test thoroughly")
    logger.info("")

    logger.info("Phase 3: Provide compatibility helpers")
    logger.info("  ✅ is_unsafe(var) - works with both approaches")
    logger.info("  ✅ unwrap_var(var) - unwraps both types")
    logger.info("")
    logger.info("  def is_unsafe(var):")
    logger.info("      return (")
    logger.info("          isinstance(var, UnsafeProxy) or")
    logger.info("          hasattr(var, '_is_unsafe')")
    logger.info("      )")
    logger.info("")

    logger.info("Phase 4: Remove UnsafeProxy")
    logger.info("  ✅ After migration period (2-3 versions)")
    logger.info("  ✅ Remove UnsafeProxy class entirely")
    logger.info("  ✅ Only AnsibleUnsafe* remains")
    logger.info("")

    logger.info("Consistent API:")
    logger.info("  # Wrapping")
    logger.info("  wrapped = wrap_var(data)")
    logger.info("")
    logger.info("  # Checking")
    logger.info("  if is_unsafe(wrapped):")
    logger.info("      ...")
    logger.info("")
    logger.info("  # Unwrapping (usually not needed)")
    logger.info("  unwrapped = unwrap_var(wrapped)")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: UnsafeProxy deprecation inconsistency causes:")
    logger.info("  1. Mixed usage of UnsafeProxy and wrap_var()")
    logger.info("  2. Inconsistent variable wrapping across code paths")
    logger.info("  3. Different type checking logic needed")
    logger.info("  4. No deprecation warnings for UnsafeProxy usage")
    logger.info("  5. Difficult migration path")
    logger.info("  6. Security implications (may template unsafe data)")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
