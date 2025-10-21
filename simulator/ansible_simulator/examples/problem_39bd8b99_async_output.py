"""
Reproduction of Problem 39bd8b99: async_wrapper Inconsistent Output

This example demonstrates how async_wrapper returns inconsistent and incomplete
JSON across different exit paths.

PROBLEM:
- async_wrapper can exit through multiple code paths
- Each path returns different JSON structure
- Some paths missing critical fields
- Some paths mix text and JSON
- No consistent error format

EXIT PATHS:
1. Normal completion - returns full JSON with ansible_job_id, results, etc.
2. Timeout - returns partial JSON, missing some fields
3. Fork failure - returns error text, not JSON
4. Directory creation failure - returns different error format
5. Module import failure - yet another format

IMPACT:
- Async task status checking fails
- Can't reliably parse results
- Different error handling per exit path
- Difficult to debug async issues
- Inconsistent behavior across systems

EXPECTED:
- All exit paths return consistent JSON structure
- Always include: ansible_job_id, failed, msg
- Consistent field names and types
- Parseable by async_status module
"""

import json
import logging
import os
import tempfile

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class AsyncWrapper:
    """
    Simulates async_wrapper.py behavior.

    PROBLEM REPRODUCTION (39bd8b99):
    - Different exit paths return different JSON structures
    - Inconsistent field names and presence
    - Some paths return non-JSON text
    """

    def __init__(self, module_name: str, job_id: str):
        self.module_name = module_name
        self.job_id = job_id
        self.async_dir = tempfile.mkdtemp(prefix="ansible_async_")

    def run_normal(self) -> str:
        """
        Normal completion path.

        Returns complete JSON with all fields.
        """
        result = {
            "ansible_job_id": self.job_id,
            "started": 1,
            "finished": 1,
            "changed": True,
            "failed": False,
            "msg": "Task completed successfully",
            "results": {"stdout": "command output", "rc": 0}
        }
        return json.dumps(result)

    def run_timeout(self) -> str:
        """
        Timeout path.

        PROBLEM: Returns incomplete JSON, missing some fields!
        """
        # PROBLEM: Missing 'started', 'results' fields
        result = {
            "ansible_job_id": self.job_id,
            "finished": 0,
            "failed": True,
            "msg": "Task timed out"
            # Missing: started, changed, results
        }
        return json.dumps(result)

    def run_fork_failure(self) -> str:
        """
        Fork failure path.

        PROBLEM: Returns plain text, not JSON!
        """
        # PROBLEM: Not JSON at all!
        return "ERROR: Failed to fork process for async execution"

    def run_directory_failure(self) -> str:
        """
        Directory creation failure path.

        PROBLEM: Returns JSON but with different field names!
        """
        # PROBLEM: Uses 'error' instead of 'msg', no ansible_job_id
        result = {
            "failed": True,
            "error": "Could not create async directory",  # Should be 'msg'!
            # Missing: ansible_job_id
        }
        return json.dumps(result)

    def run_module_not_found(self) -> str:
        """
        Module import failure path.

        PROBLEM: Returns yet another format!
        """
        # PROBLEM: Has ansible_job_id but different structure
        result = {
            "ansible_job_id": self.job_id,
            "failed": True,
            "module_stderr": "ImportError: No module named 'xyz'",
            # Missing: msg, finished, started
        }
        return json.dumps(result)

    def run_json_parse_error(self) -> str:
        """
        JSON serialization error path.

        PROBLEM: Returns partial JSON mixed with error text!
        """
        # PROBLEM: Broken JSON with error text appended
        return '{"ansible_job_id": "' + self.job_id + '", "failed": true\nERROR: Failed to serialize results'


def demonstrate_problem():
    """Demonstrate async_wrapper inconsistent output."""

    logger.info("=" * 80)
    logger.info("PROBLEM 39bd8b99: async_wrapper Inconsistent Output")
    logger.info("=" * 80)
    logger.info("")

    logger.info("BACKGROUND: async_wrapper execution flow")
    logger.info("-" * 80)
    logger.info("")
    logger.info("async_wrapper is used when async: N is specified on a task:")
    logger.info("  1. Fork background process")
    logger.info("  2. Write job file to async directory")
    logger.info("  3. Execute module in background")
    logger.info("  4. Write results to job file")
    logger.info("  5. Return immediately with job_id")
    logger.info("")
    logger.info("async_status module polls job file for completion")
    logger.info("")

    # Create async wrapper
    wrapper = AsyncWrapper(module_name="shell", job_id="123456.12345")

    logger.info("EXIT PATH 1: Normal completion")
    logger.info("-" * 80)
    logger.info("")

    output1 = wrapper.run_normal()
    logger.info("Output:")
    logger.info(output1)
    logger.info("")

    try:
        parsed1 = json.loads(output1)
        logger.info("Parsed JSON fields:")
        for key in sorted(parsed1.keys()):
            logger.info(f"  {key}: {parsed1[key]}")
        logger.info("")
        logger.info("✅ Valid JSON with all expected fields")
    except json.JSONDecodeError as e:
        logger.info(f"❌ JSON parse error: {e}")
    logger.info("")

    logger.info("EXIT PATH 2: Timeout")
    logger.info("-" * 80)
    logger.info("")

    output2 = wrapper.run_timeout()
    logger.info("Output:")
    logger.info(output2)
    logger.info("")

    try:
        parsed2 = json.loads(output2)
        logger.info("Parsed JSON fields:")
        for key in sorted(parsed2.keys()):
            logger.info(f"  {key}: {parsed2[key]}")
        logger.info("")
        logger.info("⚠️  Valid JSON but MISSING fields:")
        logger.info("  Missing: 'started' (needed by async_status)")
        logger.info("  Missing: 'changed' (status unclear)")
        logger.info("  Missing: 'results' (no output available)")
    except json.JSONDecodeError as e:
        logger.info(f"❌ JSON parse error: {e}")
    logger.info("")

    logger.info("EXIT PATH 3: Fork failure")
    logger.info("-" * 80)
    logger.info("")

    output3 = wrapper.run_fork_failure()
    logger.info("Output:")
    logger.info(output3)
    logger.info("")

    try:
        parsed3 = json.loads(output3)
        logger.info("Parsed JSON fields:")
        for key in sorted(parsed3.keys()):
            logger.info(f"  {key}: {parsed3[key]}")
    except json.JSONDecodeError as e:
        logger.info(f"❌ JSON parse error: {e}")
        logger.info("")
        logger.info("❌ PROBLEM: Not JSON at all! Plain text error message")
        logger.info("❌ async_status can't parse this")
        logger.info("❌ Task appears to hang (no job file, no error)")
    logger.info("")

    logger.info("EXIT PATH 4: Directory creation failure")
    logger.info("-" * 80)
    logger.info("")

    output4 = wrapper.run_directory_failure()
    logger.info("Output:")
    logger.info(output4)
    logger.info("")

    try:
        parsed4 = json.loads(output4)
        logger.info("Parsed JSON fields:")
        for key in sorted(parsed4.keys()):
            logger.info(f"  {key}: {parsed4[key]}")
        logger.info("")
        logger.info("⚠️  Valid JSON but INCONSISTENT:")
        logger.info("  Uses 'error' instead of 'msg'")
        logger.info("  Missing: 'ansible_job_id' (can't track job!)")
        logger.info("  Missing: 'finished', 'started'")
    except json.JSONDecodeError as e:
        logger.info(f"❌ JSON parse error: {e}")
    logger.info("")

    logger.info("EXIT PATH 5: Module not found")
    logger.info("-" * 80)
    logger.info("")

    output5 = wrapper.run_module_not_found()
    logger.info("Output:")
    logger.info(output5)
    logger.info("")

    try:
        parsed5 = json.loads(output5)
        logger.info("Parsed JSON fields:")
        for key in sorted(parsed5.keys()):
            logger.info(f"  {key}: {parsed5[key]}")
        logger.info("")
        logger.info("⚠️  Valid JSON but DIFFERENT structure:")
        logger.info("  Has 'module_stderr' (non-standard field)")
        logger.info("  Missing: 'msg' (standard error field)")
        logger.info("  Missing: 'finished', 'started'")
    except json.JSONDecodeError as e:
        logger.info(f"❌ JSON parse error: {e}")
    logger.info("")

    logger.info("EXIT PATH 6: JSON serialization error")
    logger.info("-" * 80)
    logger.info("")

    output6 = wrapper.run_json_parse_error()
    logger.info("Output:")
    logger.info(output6)
    logger.info("")

    try:
        parsed6 = json.loads(output6)
        logger.info("Parsed JSON fields:")
        for key in sorted(parsed6.keys()):
            logger.info(f"  {key}: {parsed6[key]}")
    except json.JSONDecodeError as e:
        logger.info(f"❌ JSON parse error: {e}")
        logger.info("")
        logger.info("❌ PROBLEM: Broken JSON mixed with error text")
        logger.info("❌ Unparseable by async_status")
        logger.info("❌ Job appears stuck")
    logger.info("")

    logger.info("=" * 80)
    logger.info("COMPARISON")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Field presence across exit paths:")
    logger.info("")
    logger.info("Field                 | Normal | Timeout | Fork | Dir Fail | Module | JSON Err")
    logger.info("-" * 80)
    logger.info("ansible_job_id        |   ✓    |    ✓    |  ✗   |    ✗     |   ✓    |    ✓")
    logger.info("started               |   ✓    |    ✗    |  ✗   |    ✗     |   ✗    |    ✗")
    logger.info("finished              |   ✓    |    ✓    |  ✗   |    ✗     |   ✗    |    ✗")
    logger.info("changed               |   ✓    |    ✗    |  ✗   |    ✗     |   ✗    |    ✗")
    logger.info("failed                |   ✓    |    ✓    |  ✗   |    ✓     |   ✓    |    ✓")
    logger.info("msg                   |   ✓    |    ✓    |  ✗   |    ✗     |   ✗    |    ✗")
    logger.info("results               |   ✓    |    ✗    |  ✗   |    ✗     |   ✗    |    ✗")
    logger.info("error (non-standard)  |   ✗    |    ✗    |  ✗   |    ✓     |   ✗    |    ✗")
    logger.info("module_stderr         |   ✗    |    ✗    |  ✗   |    ✗     |   ✓    |    ✗")
    logger.info("Valid JSON            |   ✓    |    ✓    |  ✗   |    ✓     |   ✓    |    ✗")
    logger.info("")

    logger.info("❌ NO consistency across exit paths!")
    logger.info("")

    logger.info("=" * 80)
    logger.info("REAL-WORLD CONSEQUENCES")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Issue #1: async_status can't parse errors")
    logger.info("-" * 80)
    logger.info("  async_status expects JSON with ansible_job_id")
    logger.info("  If fork fails → plain text, no job_id")
    logger.info("  async_status hangs waiting for job file")
    logger.info("  Task never completes, no clear error")
    logger.info("")

    logger.info("Issue #2: Inconsistent error handling")
    logger.info("-" * 80)
    logger.info("  Need different code for each exit path:")
    logger.info("    - Check 'msg' field")
    logger.info("    - Check 'error' field")
    logger.info("    - Check 'module_stderr' field")
    logger.info("    - Handle non-JSON text")
    logger.info("  Complex, error-prone, hard to maintain")
    logger.info("")

    logger.info("Issue #3: Missing critical fields")
    logger.info("-" * 80)
    logger.info("  'started' field needed to know if job began")
    logger.info("  'finished' field needed to know completion")
    logger.info("  'ansible_job_id' needed to track job")
    logger.info("  Missing fields cause async_status to fail")
    logger.info("")

    logger.info("=" * 80)
    logger.info("SOLUTION NEEDED")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Standardize async_wrapper output:")
    logger.info("  ✅ ALL exit paths return valid JSON")
    logger.info("  ✅ ALL paths include these fields:")
    logger.info("      - ansible_job_id (always)")
    logger.info("      - started (0 or 1)")
    logger.info("      - finished (0 or 1)")
    logger.info("      - failed (true or false)")
    logger.info("      - msg (error description)")
    logger.info("  ✅ Use 'msg' consistently (not 'error' or 'module_stderr')")
    logger.info("  ✅ Never return plain text")
    logger.info("  ✅ Validate JSON before returning")
    logger.info("")

    logger.info("Standard error format:")
    logger.info("  {")
    logger.info('    "ansible_job_id": "123456.12345",')
    logger.info('    "started": 0,')
    logger.info('    "finished": 1,')
    logger.info('    "failed": true,')
    logger.info('    "msg": "Fork failed: reason here"')
    logger.info("  }")
    logger.info("")

    logger.info("=" * 80)
    logger.info("Summary: async_wrapper inconsistent output causes:")
    logger.info("  1. Different JSON structures per exit path")
    logger.info("  2. Some paths return non-JSON text")
    logger.info("  3. Missing critical fields (ansible_job_id, started, finished)")
    logger.info("  4. Inconsistent field names (msg vs error vs module_stderr)")
    logger.info("  5. async_status can't reliably parse results")
    logger.info("  6. Tasks hang with unclear errors")
    logger.info("=" * 80)


if __name__ == "__main__":
    demonstrate_problem()
