"""
Reproduction of Problem c616e54a: module_utils Collection Resolution

This example demonstrates how module_common fails to resolve module_utils from
collections, especially with redirects, relative imports, and missing __init__.py.

PROBLEM:
- module_common builds module payload by analyzing imports
- Fails to resolve module_utils from collections properly
- Issues with:
  1. Redirected module_utils (defined in meta/runtime.yml)
  2. Relative imports in package __init__.py
  3. Nested packages without __init__.py
  4. Cross-collection redirects
- Error messages confusing and unhelpful

IMPACT:
- Modules from collections fail at runtime
- Missing module_utils files in payload
- ImportError with unclear messages
- Difficult to debug collection issues

SCENARIO:
```
Collection: community.example
Structure:
  plugins/modules/my_module.py
  plugins/module_utils/
    helper.py
    network/
      __init__.py  (has: from .utils import connect)
      utils.py
      transport/
        ssh.py

Module code (my_module.py):
  from ansible_collections.community.example.plugins.module_utils.helper import process
  from ansible_collections.community.example.plugins.module_utils.network import connect

meta/runtime.yml:
  plugin_routing:
    module_utils:
      helper:
        redirect: community.example.plugins.module_utils.core.helper
      network:
        redirect: community.other.plugins.module_utils.network

Problems:
1. Redirect not followed → helper.py not found
2. Relative import in network/__init__.py fails → utils.py not bundled
3. Error message: "ImportError: No module named 'helper'" (unhelpful!)
```
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CollectionMetadata:
    """Collection metadata from meta/runtime.yml."""
    name: str
    redirects: Dict[str, str]  # module_utils name → redirect target


class ModuleUtilsResolver:
    """
    Simulates module_utils resolution from module_common.

    PROBLEM REPRODUCTION (c616e54a):
    - Fails to follow redirects
    - Doesn't handle relative imports
    - Confusing error messages
    """

    def __init__(self):
        # Simulated collection metadata
        self.collections = {
            "community.example": CollectionMetadata(
                name="community.example",
                redirects={
                    "helper": "community.example.plugins.module_utils.core.helper",
                    "network": "community.other.plugins.module_utils.network"
                }
            ),
            "community.other": CollectionMetadata(
                name="community.other",
                redirects={}
            )
        }

        # Simulated available module_utils files
        self.available_files = {
            # Original location (will be redirected)
            "ansible_collections.community.example.plugins.module_utils.helper": False,

            # Actual location after redirect
            "ansible_collections.community.example.plugins.module_utils.core.helper": True,

            # Network package
            "ansible_collections.community.example.plugins.module_utils.network.__init__": True,
            "ansible_collections.community.example.plugins.module_utils.network.utils": True,

            # After redirect
            "ansible_collections.community.other.plugins.module_utils.network.__init__": True,
            "ansible_collections.community.other.plugins.module_utils.network.utils": True,
        }

        # Track what's in the payload
        self.bundled_files: Set[str] = set()

    def resolve_import(self, import_path: str) -> Optional[str]:
        """
        Resolve module_utils import.

        PROBLEM: Doesn't follow redirects!
        """
        logger.info(f"  Resolving import: {import_path}")

        # PROBLEM: Doesn't check for redirects!
        # Should check collection metadata for plugin_routing
        logger.warning("  ⚠️  PROBLEM c616e54a: Not checking redirects")

        # Try to find file directly
        if import_path in self.available_files and self.available_files[import_path]:
            logger.info(f"  ✅ Found: {import_path}")
            self.bundled_files.add(import_path)
            return import_path
        else:
            logger.error(f"  ❌ NOT FOUND: {import_path}")
            logger.error("  ❌ Confusing error: File doesn't exist")
            logger.error("  ❌ Should show: 'Redirect defined but not followed'")
            return None

    def resolve_with_redirect(self, import_path: str, collection: str) -> Optional[str]:
        """
        Resolve import WITH redirect support (correct behavior).
        """
        logger.info(f"  Resolving import with redirects: {import_path}")

        # Extract module_utils name
        parts = import_path.split('.')
        if 'module_utils' in parts:
            idx = parts.index('module_utils')
            if idx + 1 < len(parts):
                module_utils_name = parts[idx + 1]

                # Check for redirect
                if collection in self.collections:
                    metadata = self.collections[collection]
                    if module_utils_name in metadata.redirects:
                        redirect_target = metadata.redirects[module_utils_name]
                        logger.info(f"  🔀 Redirect found: {module_utils_name} → {redirect_target}")

                        # Build redirected path
                        redirected_path = f"ansible_collections.{redirect_target}"
                        if redirected_path in self.available_files and self.available_files[redirected_path]:
                            logger.info(f"  ✅ Found at redirect target: {redirected_path}")
                            self.bundled_files.add(redirected_path)
                            return redirected_path

        # No redirect or redirect failed, try direct
        if import_path in self.available_files and self.available_files[import_path]:
            logger.info(f"  ✅ Found directly: {import_path}")
            self.bundled_files.add(import_path)
            return import_path

        logger.error(f"  ❌ NOT FOUND: {import_path}")
        return None

    def analyze_relative_imports(self, module_path: str):
        """
        Analyze relative imports in __init__.py.

        PROBLEM: Doesn't detect or bundle relative imports!
        """
        logger.info(f"  Analyzing relative imports in: {module_path}")

        # Simulate __init__.py with relative imports
        if "__init__" in module_path:
            logger.info("  Found __init__.py with relative imports:")
            logger.info("    from .utils import connect")
            logger.info("    from ..core import helper")

            logger.warning("  ⚠️  PROBLEM c616e54a: Relative imports not resolved")
            logger.warning("  ⚠️  utils.py will NOT be bundled")
            logger.warning("  ⚠️  Runtime ImportError!")

    def build_module_payload(self, module_imports: List[str], use_redirects: bool = False):
        """Build module payload with module_utils."""
        logger.info("Building module payload...")
        logger.info("")

        self.bundled_files.clear()

        for import_path in module_imports:
            if use_redirects:
                # Extract collection name
                parts = import_path.split('.')
                if len(parts) >= 3 and parts[0] == "ansible_collections":
                    collection = f"{parts[1]}.{parts[2]}"
                    self.resolve_with_redirect(import_path, collection)
                else:
                    self.resolve_import(import_path)
            else:
                # PROBLEM: Wrong behavior
                self.resolve_import(import_path)

            # Check for relative imports
            self.analyze_relative_imports(import_path)
            logger.info("")


def demonstrate_problem():
    """Demonstrate module_utils resolution problem."""

    logger.info("=" * 80)
    logger.info("PROBLEM c616e54a: module_utils Collection Resolution")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: How module_utils work in collections")
    logger.info("-" * 80)
    logger.info("")
    logger.info("Collections structure:")
    logger.info("  ansible_collections/")
    logger.info("    <namespace>/")
    logger.info("      <collection>/")
    logger.info("        plugins/")
    logger.info("          modules/")
    logger.info("            my_module.py")
    logger.info("          module_utils/")
    logger.info("            helper.py")
    logger.info("            network/")
    logger.info("              __init__.py")
    logger.info("              utils.py")
    logger.info("")
    logger.info("Module imports:")
    logger.info("  from ansible_collections.ns.coll.plugins.module_utils.helper import func")
    logger.info("  from ansible_collections.ns.coll.plugins.module_utils.network import connect")
    logger.info("")
    logger.info("module_common must:")
    logger.info("  1. Parse module imports")
    logger.info("  2. Find referenced module_utils files")
    logger.info("  3. Bundle them into module payload")
    logger.info("  4. Handle redirects from meta/runtime.yml")
    logger.info("  5. Resolve relative imports")
    logger.info("")

    resolver = ModuleUtilsResolver()

    logger.info("PROBLEM 1: Redirects not followed")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Collection: community.example")
    logger.info("meta/runtime.yml:")
    logger.info("  plugin_routing:")
    logger.info("    module_utils:")
    logger.info("      helper:")
    logger.info("        redirect: community.example.plugins.module_utils.core.helper")
    logger.info("")

    logger.info("Module import:")
    logger.info("  from ansible_collections.community.example.plugins.module_utils.helper import process")
    logger.info("")

    logger.info("Current behavior (WRONG):")
    logger.info("")

    module_imports = [
        "ansible_collections.community.example.plugins.module_utils.helper"
    ]

    resolver.build_module_payload(module_imports, use_redirects=False)

    logger.info("Bundled files:")
    if resolver.bundled_files:
        for f in sorted(resolver.bundled_files):
            logger.info(f"  • {f}")
    else:
        logger.info("  (none)")
    logger.info("")

    logger.info("❌ PROBLEM: Redirect not followed, file not found")
    logger.info("❌ Runtime error: ImportError: No module named 'helper'")
    logger.info("")

    logger.info("Expected behavior (CORRECT):")
    logger.info("")

    resolver.bundled_files.clear()
    resolver.build_module_payload(module_imports, use_redirects=True)

    logger.info("Bundled files:")
    for f in sorted(resolver.bundled_files):
        logger.info(f"  • {f}")
    logger.info("")

    logger.info("✅ CORRECT: Followed redirect, found actual file")
    logger.info("")

    logger.info("PROBLEM 2: Relative imports not resolved")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Package structure:")
    logger.info("  module_utils/")
    logger.info("    network/")
    logger.info("      __init__.py")
    logger.info("      utils.py")
    logger.info("")

    logger.info("network/__init__.py contains:")
    logger.info("  from .utils import connect")
    logger.info("")

    logger.info("Module import:")
    logger.info("  from ansible_collections.community.example.plugins.module_utils.network import connect")
    logger.info("")

    logger.info("Current behavior (WRONG):")
    logger.info("")

    network_imports = [
        "ansible_collections.community.example.plugins.module_utils.network.__init__"
    ]

    resolver.bundled_files.clear()
    resolver.build_module_payload(network_imports, use_redirects=False)

    logger.info("Bundled files:")
    for f in sorted(resolver.bundled_files):
        logger.info(f"  • {f}")
    logger.info("")

    logger.info("❌ PROBLEM: Only bundled __init__.py")
    logger.info("❌ Did NOT bundle utils.py (needed by relative import)")
    logger.info("❌ Runtime error: ImportError: cannot import name 'connect'")
    logger.info("")

    logger.info("Expected behavior:")
    logger.info("  Should analyze __init__.py")
    logger.info("  Should detect: from .utils import connect")
    logger.info("  Should bundle: network/utils.py")
    logger.info("")

    logger.info("PROBLEM 3: Cross-collection redirects")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Collection: community.example")
    logger.info("meta/runtime.yml:")
    logger.info("  plugin_routing:")
    logger.info("    module_utils:")
    logger.info("      network:")
    logger.info("        redirect: community.other.plugins.module_utils.network")
    logger.info("")

    logger.info("Module import:")
    logger.info("  from ansible_collections.community.example.plugins.module_utils.network import connect")
    logger.info("")

    logger.info("Expected:")
    logger.info("  1. Check community.example for 'network'")
    logger.info("  2. Find redirect to community.other")
    logger.info("  3. Load from community.other.plugins.module_utils.network")
    logger.info("  4. Bundle files from community.other (different collection!)")
    logger.info("")

    logger.info("Current behavior:")
    logger.info("  ❌ Cross-collection redirects not supported")
    logger.info("  ❌ Only checks original collection")
    logger.info("  ❌ Confusing error message")
    logger.info("")

    logger.info("PROBLEM 4: Missing __init__.py in nested packages")
    logger.info("-" * 80)
    logger.info("")

    logger.info("Package structure:")
    logger.info("  module_utils/")
    logger.info("    network/")
    logger.info("      (no __init__.py)")
    logger.info("      transport/")
    logger.info("        __init__.py")
    logger.info("        ssh.py")
    logger.info("")

    logger.info("Module import:")
    logger.info("  from ansible_collections.ns.coll.plugins.module_utils.network.transport.ssh import connect")
    logger.info("")

    logger.info("Problem:")
    logger.info("  • Python allows packages without __init__.py (PEP 420)")
    logger.info("  • module_common expects __init__.py")
    logger.info("  • Fails to resolve path")
    logger.info("  • Error: 'network' is not a package")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Issue #1: Community collections broken")
    logger.info("-" * 80)
    logger.info("  Many collections use redirects:")
    logger.info("    • community.general")
    logger.info("    • community.network")
    logger.info("    • ansible.netcommon")
    logger.info("  Problem:")
    logger.info("    • Modules fail at runtime")
    logger.info("    • 'Works in development, fails in production'")
    logger.info("    • Error messages don't mention redirects")
    logger.info("")

    logger.info("Issue #2: Relative imports common pattern")
    logger.info("-" * 80)
    logger.info("  Clean code structure uses relative imports:")
    logger.info("    network/__init__.py:")
    logger.info("      from .client import Client")
    logger.info("      from .errors import NetworkError")
    logger.info("  Problem:")
    logger.info("    • Only __init__.py bundled")
    logger.info("    • client.py and errors.py missing")
    logger.info("    • Runtime ImportError")
    logger.info("")

    logger.info("Issue #3: Confusing error messages")
    logger.info("-" * 80)
    logger.info("  Current error:")
    logger.info("    ImportError: No module named 'helper'")
    logger.info("")
    logger.info("  What it should say:")
    logger.info("    ImportError: module_utils 'helper' not found")
    logger.info("    Note: 'helper' is redirected to 'community.example.plugins.module_utils.core.helper'")
    logger.info("    in meta/runtime.yml, but target was not found.")
    logger.info("")
    logger.info("  Makes debugging nearly impossible!")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Fix #1: Follow redirects from meta/runtime.yml")
    logger.info("  ✅ Parse collection metadata")
    logger.info("  ✅ Check plugin_routing.module_utils")
    logger.info("  ✅ Follow redirect chains")
    logger.info("  ✅ Support cross-collection redirects")
    logger.info("")

    logger.info("Fix #2: Resolve relative imports")
    logger.info("  ✅ Parse __init__.py files for relative imports")
    logger.info("  ✅ Detect: from .submod import X")
    logger.info("  ✅ Detect: from ..parent.mod import Y")
    logger.info("  ✅ Bundle all transitively imported files")
    logger.info("")

    logger.info("Fix #3: Support namespace packages (PEP 420)")
    logger.info("  ✅ Allow packages without __init__.py")
    logger.info("  ✅ Check directory existence, not just __init__.py")
    logger.info("  ✅ Build correct import paths")
    logger.info("")

    logger.info("Fix #4: Better error messages")
    logger.info("  ✅ Show redirect chain if applicable")
    logger.info("  ✅ Show where resolver looked")
    logger.info("  ✅ Suggest fixes (check meta/runtime.yml, check spelling)")
    logger.info("  ✅ Distinguish: not found vs redirect failed vs wrong package")
    logger.info("")

    logger.info("Example improved resolution:")
    logger.info("  def resolve_module_utils(import_path):")
    logger.info("      # Step 1: Parse import")
    logger.info("      collection, module_utils_path = parse_import(import_path)")
    logger.info("")
    logger.info("      # Step 2: Check for redirect")
    logger.info("      redirect = check_routing(collection, module_utils_path)")
    logger.info("      if redirect:")
    logger.info("          target_collection, target_path = parse_redirect(redirect)")
    logger.info("          import_path = build_path(target_collection, target_path)")
    logger.info("")
    logger.info("      # Step 3: Find file")
    logger.info("      file_path = find_file(import_path)")
    logger.info("      if not file_path:")
    logger.info("          raise ResolutionError(import_path, redirect, searched_paths)")
    logger.info("")
    logger.info("      # Step 4: Analyze for relative imports")
    logger.info("      if is_package(file_path):")
    logger.info("          relative_imports = parse_relative_imports(file_path)")
    logger.info("          for rel_import in relative_imports:")
    logger.info("              # Recursively resolve")
    logger.info("              resolve_module_utils(rel_import)")
    logger.info("")
    logger.info("      return file_path")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: module_utils collection resolution causes:")
    logger.info("  1. Redirects from meta/runtime.yml not followed")
    logger.info("  2. Relative imports in __init__.py not resolved")
    logger.info("  3. Cross-collection redirects fail")
    logger.info("  4. Namespace packages (PEP 420) not supported")
    logger.info("  5. Error messages confusing and unhelpful")
    logger.info("  6. Community collections often broken")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
