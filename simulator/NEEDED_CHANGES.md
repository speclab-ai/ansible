# Simulator Changes Needed to Reproduce Problem Statements

This document maps each problem statement to the specific simulator changes required to reproduce the issue.

**Last Updated:** 2025-10-21

---

## Summary of Required Changes

| Problem ID | Title | Priority | Simulator Coverage | Effort |
|------------|-------|----------|-------------------|--------|
| 395e5e20 | PlayIterator state representation | HIGH | 60% | Medium |
| 5e369604 | Forked Display.display deadlock | HIGH | 20% | High |
| 1b70260d | Block with tag causes role re-run | MEDIUM | 40% | Medium |
| 9142be2f | Python module shebang not honored | LOW | 10% | Low |
| 42355d18 | Double calculation loops/delegate_to | MEDIUM | 50% | Medium |
| 5640093f | module_defaults not applied via action plugins | MEDIUM | 30% | Medium |
| 5c225dc0 | Public methods for PlayIterator._host_states | HIGH | 80% | Low |
| 811093f0 | Handler execution predictability | HIGH | 40% | High |
| 8127abbc | Isolate worker processes I/O | MEDIUM | 30% | Medium |
| a7d2a4e0 | Display deduplication in forks | MEDIUM | 20% | Medium |
| d6d2251a | Implicit meta/noop tasks performance | HIGH | 50% | High |
| 39bd8b99 | async_wrapper inconsistent output | MEDIUM | 0% | High |
| 4c5ce5a1 | Module respawn & libselinux-python | LOW | 10% | High |
| 164881d8 | UnsafeProxy deprecation inconsistency | LOW | 0% | Medium |
| c616e54a | module_utils collection resolution | LOW | 0% | High |
| cb94c0cc | timeout in ad-hoc/console/task_include | LOW | 40% | Low |

---

## Problem-by-Problem Analysis

### ✅ Problem: 395e5e20 - PlayIterator State Representation

**Summary:** PlayIterator exposes run/failure states as plain integers. Need public, explicit representation.

**Current Simulator Status:** 60% - PlayIterator exists but states are simplified

**Required Changes:**

1. **Create State Enums** (`ansible_simulator/executor/play_iterator_states.py`)
   ```python
   class IteratingState(Enum):
       ITERATING_SETUP = 0
       ITERATING_TASKS = 1
       ITERATING_RESCUE = 2
       ITERATING_ALWAYS = 3
       ITERATING_COMPLETE = 4

   class FailureState(Enum):
       FAILED_NONE = 0
       FAILED_SETUP = 1
       FAILED_TASKS = 2
       FAILED_RESCUE = 4
       FAILED_ALWAYS = 8
   ```

2. **Update HostState class** in `executor.py`
   - Add proper state tracking with enums
   - Implement `__str__` to show readable state names
   - Add deprecation warnings for old integer access

3. **Add backward compatibility layer**
   - Allow access via `PlayIterator.ITERATING_TASKS`
   - Emit deprecation warnings

**Files to Modify:**
- `ansible_simulator/components/executor.py` (PlayIterator, HostState classes)
- Create `ansible_simulator/executor/play_iterator_states.py`

**Priority:** HIGH - Core execution state management

---

### ✅ Problem: 5e369604 - Forked Display.display Deadlock Risk

**Summary:** Display.display called from worker processes writes directly to stdout/stderr, causing deadlock risk during shutdown.

**Current Simulator Status:** 20% - Workers exist but no Display system

**Required Changes:**

1. **Create Display class** (`ansible_simulator/utils/display.py`)
   ```python
   class Display:
       def __init__(self):
           self.lock = threading.Lock()
           self.message_queue = Queue()

       def display(self, msg, color=None, stderr=False):
           # Queue messages from workers instead of direct write
           pass
   ```

2. **Implement worker message proxying**
   - Workers send display messages via queue/pipe
   - Main process handles all actual I/O
   - Avoid direct stdout/stderr writes from workers

3. **Add shutdown handling**
   - Demonstrate the deadlock scenario
   - Show workaround with late redirection to /dev/null
   - Add proper cleanup protocol

**Files to Create:**
- `ansible_simulator/utils/display.py`

**Files to Modify:**
- `ansible_simulator/components/executor.py` (WorkerProcess)
- `ansible_simulator/components/control_node.py`

**Priority:** HIGH - Critical for realistic worker process simulation

---

### ✅ Problem: 1b70260d - Block with Tag Causes Role Re-run

**Summary:** When using tags with blocks followed by tasks, dependent roles execute twice.

**Current Simulator Status:** 40% - Blocks exist, tags exist, but no tag filtering or role dependency system

**Required Changes:**

1. **Implement Role Dependencies**
   - Add `meta/main.yml` concept to Role model
   - Add dependency resolution
   - Track which roles have been executed

2. **Implement Tag Filtering**
   - Add tag evaluation logic
   - Filter tasks based on --tags and --skip-tags
   - Handle block tag inheritance

3. **Fix Role Deduplication with Tags**
   - When tags are used, track role execution properly
   - Prevent duplicate role execution when tag filtering creates gaps

**Files to Modify:**
- `ansible_simulator/shared/models.py` (Role, Task, Block)
- `ansible_simulator/components/executor.py` (role execution tracking)
- Create `ansible_simulator/playbook/taggable.py`
- Create `ansible_simulator/playbook/role_metadata.py`

**Priority:** MEDIUM - Important for realistic playbook execution

---

### ✅ Problem: 9142be2f - Python Module Shebang Not Honored

**Summary:** ansible-core rewrites module shebang to `/usr/bin/python`, ignoring explicit interpreter declarations.

**Current Simulator Status:** 10% - Module execution is highly simplified

**Required Changes:**

1. **Create ModuleCommon component** (`ansible_simulator/executor/module_common.py`)
   - Parse module files for shebang
   - Detect `#!/usr/bin/python3.8` etc.
   - Respect shebang unless overridden

2. **Add Interpreter Discovery**
   - Check for `ansible_python_interpreter` variable
   - Fall back to module shebang if present
   - Fall back to `/usr/bin/python` if no shebang

3. **Module Wrapping Logic**
   - Simulate module payload creation
   - Show shebang replacement behavior
   - Allow configuration to honor/ignore shebang

**Files to Create:**
- `ansible_simulator/executor/module_common.py`
- `ansible_simulator/executor/interpreter_discovery.py`

**Files to Modify:**
- `ansible_simulator/components/managed_host.py` (module execution)

**Priority:** LOW - Edge case, doesn't affect core execution flow

---

### ✅ Problem: 42355d18 - Double Calculation of Loops and delegate_to

**Summary:** When task uses both `loop` and `delegate_to`, values are calculated twice.

**Current Simulator Status:** 50% - Loop and delegate_to exist but no double calculation tracking

**Required Changes:**

1. **Add Calculation Tracking**
   - Add instrumentation to track when loop items are evaluated
   - Track when delegate_to is resolved
   - Demonstrate duplicate evaluation

2. **Show the Bug**
   - Create test case where delegate_to uses random selection
   - Show inconsistent results across loop iterations

3. **Implement Fix**
   - Cache loop evaluation result
   - Cache delegate_to resolution
   - Reuse cached values

**Files to Modify:**
- `ansible_simulator/components/executor.py` (TaskExecutor._run_loop)
- Add evaluation tracking/metrics

**Priority:** MEDIUM - Affects correctness of execution

---

### ✅ Problem: 5640093f - module_defaults Not Applied via Action Plugins

**Summary:** gather_facts, package, service action plugins don't respect module_defaults.

**Current Simulator Status:** 30% - Action plugins exist, no module_defaults system

**Required Changes:**

1. **Implement module_defaults** (`ansible_simulator/playbook/module_defaults.py`)
   ```python
   class ModuleDefaults:
       defaults: Dict[str, Dict[str, Any]]

       def get_defaults(self, module_name: str, fqcn: str = None):
           # Return defaults for module
           pass
   ```

2. **Update Action Plugins**
   - `gather_facts` - should apply `setup` module defaults
   - `package` - should apply `apt`/`dnf`/`yum` defaults based on target
   - `service` - should apply `systemd`/`sysvinit` defaults

3. **Add FQCN Resolution**
   - Support `ansible.builtin.setup` vs `setup` vs `ansible.legacy.setup`
   - Resolve to actual executed module
   - Apply correct defaults

**Files to Create:**
- `ansible_simulator/playbook/module_defaults.py`

**Files to Modify:**
- `ansible_simulator/shared/models.py` (Play model - add module_defaults field)
- `ansible_simulator/components/plugins.py` (action plugins)

**Priority:** MEDIUM - Important for realistic playbook behavior

---

### ✅ Problem: 5c225dc0 - Public Methods for PlayIterator._host_states

**Summary:** Need public methods to access/modify PlayIterator._host_states in controlled manner.

**Current Simulator Status:** 80% - PlayIterator exists with _host_states, just need public API

**Required Changes:**

1. **Add Public Methods to PlayIterator**
   ```python
   def set_state_for_host(self, host: Host, state: HostState) -> None:
       """Set complete state for a host with validation."""
       pass

   def set_run_state_for_host(self, host: Host, run_state: IteratingState) -> None:
       """Set run state for a host."""
       pass

   def set_fail_state_for_host(self, host: Host, fail_state: FailureState) -> None:
       """Set fail state for a host."""
       pass

   def get_state_for_host(self, host: Host) -> HostState:
       """Get state for a host."""
       pass
   ```

2. **Add Type Validation**
   - Validate HostState type
   - Validate state transitions
   - Add logging for state changes

**Files to Modify:**
- `ansible_simulator/components/executor.py` (PlayIterator class)

**Priority:** HIGH - Easy to implement, improves encapsulation

---

### ✅ Problem: 811093f0 - Handler Execution Predictability

**Summary:** Handler execution is inconsistent across hosts, doesn't honor any_errors_fatal, meta: flush_handlers can't be conditioned, meta tasks can't be handlers.

**Current Simulator Status:** 40% - Basic handler notification exists, but execution is simplified

**Required Changes:**

1. **Implement Dedicated Handler Phase**
   - Run handlers through PlayIterator with strategy
   - Execute in correct order per host
   - Support serial execution

2. **Add any_errors_fatal Support for Handlers**
   - Check any_errors_fatal during handler execution
   - Stop all hosts if any handler fails (when enabled)

3. **Implement meta: flush_handlers**
   - Add meta task support
   - Allow conditional `when:` on meta tasks
   - Flush handlers at explicit points

4. **Support Meta Tasks as Handlers**
   - Allow meta tasks (except flush_handlers) as handlers
   - Prevent flush_handlers from being a handler

5. **Fix Handler Execution After always Sections**
   - Don't run handlers on failed hosts after `always`
   - Proper host state tracking

**Files to Modify:**
- `ansible_simulator/components/executor.py` (handler execution logic)
- `ansible_simulator/components/strategy.py` (strategy handler support)
- `ansible_simulator/shared/models.py` (add meta task support)

**Priority:** HIGH - Critical for correct playbook execution

---

### ✅ Problem: 8127abbc - Isolate Worker Processes I/O

**Summary:** Worker processes inherit parent's stdin/stdout/stderr, causing unintended terminal interaction.

**Current Simulator Status:** 30% - Workers exist but no I/O isolation

**Required Changes:**

1. **Simulate Process Group Isolation**
   - Track process groups in WorkerProcess
   - Simulate detachment from terminal
   - Document inherited vs isolated file descriptors

2. **Redirect Standard I/O**
   - Demonstrate workers inheriting terminal FDs
   - Show redirecting to /dev/null or pipes
   - Implement proper isolation

3. **Add Logging Channels**
   - Workers communicate via structured messages
   - No direct terminal output from workers

**Files to Modify:**
- `ansible_simulator/components/executor.py` (WorkerProcess)
- Add process isolation tracking

**Priority:** MEDIUM - Important for realistic worker behavior

---

### ✅ Problem: a7d2a4e0 - Display Deduplication in Forks

**Summary:** Warnings/deprecations from worker processes are not deduplicated globally, appear multiple times.

**Current Simulator Status:** 20% - No Display system

**Required Changes:**

1. **Implement Display with Deduplication**
   - Global deduplication cache (hash of messages)
   - Per-process deduplication (current behavior - shows the bug)

2. **Proxy Display Calls to Main Process**
   - Workers send display/warning/deprecated calls via queue
   - Main process deduplicates and displays
   - Demonstrate before/after behavior

3. **Add warning() and deprecated() Methods**
   ```python
   def warning(self, msg):
       # Should deduplicate globally
       pass

   def deprecated(self, msg, version):
       # Should deduplicate globally
       pass
   ```

**Files to Create:**
- `ansible_simulator/utils/display.py`

**Files to Modify:**
- `ansible_simulator/components/executor.py` (WorkerProcess)

**Priority:** MEDIUM - Important for realistic output behavior

---

### ✅ Problem: d6d2251a - Implicit meta/noop Tasks Performance

**Summary:** Ansible generates implicit "meta: flush_handlers" for all hosts even when no handlers notified, and "meta: noop" to keep idle hosts in lockstep.

**Current Simulator Status:** 50% - No meta tasks, simplified handler flushing

**Required Changes:**

1. **Implement Implicit meta: flush_handlers**
   - PlayIterator generates implicit flush_handlers for each host
   - Even when no handlers are notified
   - Track these separately from explicit meta tasks

2. **Add Optimization: Skip Implicit Flush When No Handlers**
   - Check if host has pending handlers
   - Skip implicit flush_handlers if none pending
   - Explicit meta: flush_handlers always runs

3. **Implement meta: noop for Linear Strategy**
   - Generate noop tasks for idle hosts
   - Demonstrate overhead in large inventories
   - Show optimization by returning empty results when no work

4. **Fix Rescued Host State**
   - Host rescued in block should not remain marked as failed
   - Proper state management

**Files to Modify:**
- `ansible_simulator/components/executor.py` (PlayIterator)
- `ansible_simulator/components/strategy.py` (LinearStrategy)
- `ansible_simulator/shared/models.py` (add Meta task type)

**Priority:** HIGH - Significant performance impact at scale

---

### ✅ Problem: 39bd8b99 - async_wrapper Inconsistent Output

**Summary:** async_wrapper returns inconsistent/incomplete JSON across different exit paths (normal, timeout, fork failure, etc.).

**Current Simulator Status:** 0% - No async execution support

**Required Changes:**

1. **Implement Async Execution** (`ansible_simulator/modules/async_wrapper.py`)
   - Create async job directory
   - Fork/spawn background process
   - Return job ID immediately

2. **Implement Multiple Exit Paths**
   - Normal completion
   - Timeout
   - Fork failure
   - Directory creation failure

3. **Show Inconsistent Output Bug**
   - Different JSON structures per exit path
   - Missing fields (ansible_job_id, msg, failed)
   - Non-JSON text mixed in

4. **Implement async_status Module**
   - Poll for job completion
   - Read result from job file

**Files to Create:**
- `ansible_simulator/modules/async_wrapper.py`
- `ansible_simulator/modules/async_status.py`

**Files to Modify:**
- `ansible_simulator/shared/models.py` (Task - add async/poll fields)
- `ansible_simulator/components/managed_host.py` (async job management)

**Priority:** MEDIUM - Important feature but complex

---

### ✅ Problem: 4c5ce5a1 - Module Respawn & libselinux-python

**Summary:** Modules need to respawn under compatible system interpreter when required bindings (libselinux-python, python-apt, etc.) are not available.

**Current Simulator Status:** 10% - No interpreter discovery or module respawning

**Required Changes:**

1. **Implement Interpreter Discovery**
   - Detect available Python interpreters on target
   - Check for required bindings (libselinux-python, etc.)
   - Cache discovery results

2. **Implement Module Respawn Mechanism**
   - Module detects missing required binding
   - Returns special "respawn needed" result
   - Controller reruns module with compatible interpreter

3. **Add SELinux Compatibility Layer**
   - Basic SELinux operations without libselinux-python
   - Fallback implementation
   - Demonstrate when respawn is needed

4. **Update Package Modules**
   - dnf, yum - need rpm/dnf bindings
   - apt - needs python-apt
   - Show respawn behavior

**Files to Create:**
- `ansible_simulator/executor/interpreter_discovery.py`
- `ansible_simulator/module_utils/selinux.py`

**Files to Modify:**
- `ansible_simulator/components/managed_host.py` (module execution)
- Module implementations (dnf, yum, apt)

**Priority:** LOW - Complex feature, limited impact on core execution

---

### ✅ Problem: 164881d8 - UnsafeProxy Deprecation Inconsistency

**Summary:** UnsafeProxy still used in many places despite new wrap_var and AnsibleUnsafe classes. Inconsistent variable wrapping.

**Current Simulator Status:** 0% - No unsafe variable handling

**Required Changes:**

1. **Implement Unsafe Variable System** (`ansible_simulator/vars/unsafe.py`)
   ```python
   class AnsibleUnsafeText(str):
       """Unsafe string that should not be templated."""
       pass

   class AnsibleUnsafeBytes(bytes):
       """Unsafe bytes."""
       pass

   def wrap_var(var):
       """Wrap variable as unsafe."""
       pass

   class UnsafeProxy:  # Deprecated
       """Legacy unsafe wrapper - emit deprecation warning."""
       pass
   ```

2. **Show Inconsistent Usage**
   - Some code paths use UnsafeProxy
   - Others use wrap_var
   - Same data wrapped differently

3. **Implement Deprecation Path**
   - Emit warnings when UnsafeProxy is used
   - Provide migration guide

**Files to Create:**
- `ansible_simulator/vars/unsafe.py`

**Files to Modify:**
- `ansible_simulator/components/executor.py` (variable handling)
- Template/loop variable handling

**Priority:** LOW - Internal implementation detail

---

### ✅ Problem: c616e54a - module_utils Collection Resolution

**Summary:** module_common fails to resolve module_utils from collections (redirects, relative imports, missing __init__.py).

**Current Simulator Status:** 0% - No collection support, no module_utils system

**Required Changes:**

1. **Implement Collections System** (`ansible_simulator/collections/`)
   - Collection namespace
   - Collection metadata (meta/runtime.yml)
   - Plugin routing (module_utils redirects)

2. **Implement module_utils Resolution**
   - Parse module imports
   - Resolve collection module_utils paths
   - Handle redirects from meta/runtime.yml
   - Support relative imports from __init__.py

3. **Show Resolution Failures**
   - Missing files in payload
   - Incorrect relative import resolution
   - Cross-collection redirects failing

**Files to Create:**
- `ansible_simulator/collections/loader.py`
- `ansible_simulator/executor/module_common.py`

**Priority:** LOW - Advanced feature, requires full collection support

---

### ✅ Problem: cb94c0cc - Timeout in ad-hoc/console/task_include

**Summary:** timeout keyword not available in ad-hoc, console CLI; not recognized in task_include; console lacks extra-vars option.

**Current Simulator Status:** 40% - Ad-hoc exists, no timeout support, no console CLI

**Required Changes:**

1. **Add timeout to Task Model**
   - Already exists in Task, ensure it's used

2. **Implement timeout in Ad-hoc CLI**
   - Add timeout parameter to ansible() method
   - Apply to task execution
   - Terminate task after timeout

3. **Create Console CLI** (`ansible_simulator/cli/console.py`)
   - Interactive REPL
   - Support timeout option
   - Support extra-vars option

4. **Support timeout in task_include**
   - Add timeout to allowed include keywords
   - Pass through to included tasks

**Files to Modify:**
- `ansible_simulator/components/control_node.py` (ansible method)
- `ansible_simulator/components/executor.py` (timeout enforcement)

**Files to Create:**
- `ansible_simulator/cli/console.py`

**Priority:** LOW - Feature enhancement, not core execution

---

## Priority Breakdown

### Critical (Must Have)
These are essential for core execution flow simulation:

1. **PlayIterator State Representation** (395e5e20) - Core state management
2. **Public Methods for PlayIterator** (5c225dc0) - Easy win, better encapsulation
3. **Handler Execution Predictability** (811093f0) - Critical for correct execution
4. **Implicit meta/noop Performance** (d6d2251a) - Major performance implications

### High Priority (Should Have)
Important for realistic simulation:

5. **Forked Display.display Deadlock** (5e369604) - Realistic worker behavior
6. **Block with Tag Role Re-run** (1b70260d) - Common playbook pattern
7. **Double Calculation loops/delegate_to** (42355d18) - Correctness issue
8. **module_defaults via Action Plugins** (5640093f) - Common playbook feature

### Medium Priority (Nice to Have)
Enhance realism but not critical:

9. **Isolate Worker I/O** (8127abbc) - Worker process realism
10. **Display Deduplication** (a7d2a4e0) - Output correctness
11. **async_wrapper Output** (39bd8b99) - Important feature but complex

### Low Priority (Future Work)
Advanced features or edge cases:

12. **Python Module Shebang** (9142be2f) - Edge case
13. **Module Respawn** (4c5ce5a1) - Complex, limited impact
14. **UnsafeProxy Deprecation** (164881d8) - Internal detail
15. **module_utils Resolution** (c616e54a) - Requires full collections
16. **Timeout in ad-hoc/console** (cb94c0cc) - Feature enhancement

---

## Implementation Roadmap

### Phase 1: Core Execution (Weeks 1-2)
- PlayIterator state enums and public methods
- Handler execution improvements
- Implicit meta task optimization
- Block/rescue/always support

### Phase 2: Worker Process Realism (Weeks 3-4)
- Display system with message queue
- Worker I/O isolation
- Global deduplication
- Forked process shutdown handling

### Phase 3: Playbook Features (Weeks 5-6)
- Tag filtering system
- Role dependencies and metadata
- module_defaults support
- Loop/delegate_to optimization

### Phase 4: Advanced Features (Weeks 7-8)
- Async execution (async_wrapper, async_status)
- Module respawn mechanism
- Interpreter discovery
- Console CLI

### Phase 5: Collections & Edge Cases (Future)
- Collections system
- module_utils resolution
- UnsafeProxy migration
- Module shebang handling

---

## Testing Strategy

For each problem, create test cases that:

1. **Demonstrate the Bug** - Show the current broken behavior
2. **Verify the Fix** - Show correct behavior after implementation
3. **Prevent Regression** - Automated tests

Example test structure:
```python
def test_problem_395e5e20_state_representation():
    """Test PlayIterator uses explicit state enums."""
    iterator = PlayIterator(...)

    # Should use enum, not integer
    assert isinstance(iterator.get_state(host).run_state, IteratingState)

    # Should have readable string representation
    assert "ITERATING_TASKS" in str(iterator.get_state(host))

    # Backward compatibility with deprecation warning
    with pytest.warns(DeprecationWarning):
        state_value = PlayIterator.ITERATING_TASKS
```

---

## Metrics for Success

Track these metrics for each problem:

1. **Reproducibility** - Can we demonstrate the bug?
2. **Accuracy** - Does simulation match real Ansible behavior?
3. **Test Coverage** - Do we have automated tests?
4. **Documentation** - Is the behavior documented?

---

## Next Steps

1. Review this document with team
2. Prioritize based on project goals
3. Start with Phase 1 implementation
4. Create detailed technical specs for each change
5. Implement incrementally with tests

