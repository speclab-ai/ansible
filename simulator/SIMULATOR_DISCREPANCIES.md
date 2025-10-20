# Ansible Simulator Discrepancies

Comprehensive comparison between the Ansible core simulator and the actual Ansible source code in `lib/ansible/`.

**Last Updated:** 2025-10-20

---

## 1. CLI Commands

### Implemented ✓
- `ansible-playbook` - Playbook execution
- `ansible` - Ad-hoc commands
- `ansible-inventory` - Inventory listing
- `ansible-vault` - Encryption (simulated)
- `ansible-galaxy` - Collection/role management (simulated)
- `ansible-config` - Configuration dump (simulated)

### Missing ✗
- **`ansible-console`** (`lib/ansible/cli/console.py`)
  - Interactive REPL for running ad-hoc commands
  - Uses `code.InteractiveConsole`
  - Would require simulating user input/output

- **`ansible-pull`** (`lib/ansible/cli/pull.py`)
  - Pull playbooks from VCS and execute locally
  - Inverts the normal push model
  - Requires simulating git operations

- **`ansible-doc`** (`lib/ansible/cli/doc.py`)
  - Documentation viewer for modules/plugins
  - Not critical for execution simulation

---

## 2. Executor Components

### Implemented ✓
- `PlaybookExecutor` - Orchestrates playbook execution
- `TaskQueueManager` - Worker pool management
- `WorkerProcess` - Forked worker simulation
- `TaskExecutor` - Task execution with loops/conditionals
- `PlayIterator` - State machine for task iteration

### Missing/Incomplete ✗

#### **AggregateStats** (`lib/ansible/executor/stats.py`)
**Current:** Simple `PlayStats` with basic counters
**Real Ansible:**
```python
class AggregateStats:
    processed = {}  # Per-host processed count
    failures = {}
    ok = {}
    dark = {}  # Unreachable
    changed = {}
    skipped = {}
    rescued = {}  # From rescue blocks
    ignored = {}  # ignore_errors
    custom = {}  # User-defined stats
```

**Impact:** Missing per-host granular statistics, rescued/ignored tracking, custom stats

#### **TaskResult Structure** (`lib/ansible/executor/task_result.py`)
**Current:** Simple `TaskResult` pydantic model
**Real Ansible:**
```python
@dataclasses.dataclass(frozen=True)
class _WireTaskResult:
    """Sent over worker queue"""
    host_name: str
    task_uuid: str
    return_data: MutableMapping
    task_fields: Mapping

class _BaseTaskResult:
    """Interpreted result with helper methods"""
    - is_failed()
    - is_skipped()
    - is_unreachable()
    - is_changed()
    - clean_copy()  # For callback display
```

**Impact:** No task UUIDs, missing result interpretation helpers, no clean copy for display

#### **Module Common** (`lib/ansible/executor/module_common.py`)
**Current:** Not implemented
**Real Ansible:**
- Wraps modules with Ansible framework code
- Handles module argument parsing
- JSON output formatting
- Shebang injection

**Impact:** Module execution is simplified, no actual module wrapping

#### **Interpreter Discovery** (`lib/ansible/executor/interpreter_discovery.py`)
**Current:** Not implemented
**Real Ansible:**
- Discovers Python interpreter on remote hosts
- Tries multiple paths: `/usr/bin/python3`, `/usr/bin/python`, etc.
- Caches discovered interpreters

**Impact:** Assumes Python is always available

#### **PowerShell Support** (`lib/ansible/executor/powershell/`)
**Current:** Not implemented
**Real Ansible:**
- Windows module execution via PowerShell
- Module manifest handling
- Different execution model than Unix

**Impact:** No Windows host simulation

---

## 3. Strategy Plugins

### Implemented ✓
- **Linear** - Lockstep execution
- **Free** - Independent host execution

### Missing ✗

#### **Debug Strategy** (`lib/ansible/plugins/strategy/debug.py`)
**Real Ansible:**
```python
class StrategyModule(LinearStrategyModule):
    # Interactive debugger
    # Drops to pdb on task failure
    # Can inspect variables, retry tasks
```

**Impact:** No interactive debugging capability

#### **Host Pinned Strategy** (`lib/ansible/plugins/strategy/host_pinned.py`)
**Real Ansible:**
```python
class StrategyModule(FreeStrategyModule):
    # Pins tasks for same host to same worker
    # Improves connection reuse
    # Based on free strategy
```

**Impact:** No worker pinning optimization

---

## 4. Playbook Components

### Implemented ✓
- `Play` - Basic play structure
- `Task` - Task with action/args
- `Block` - Task blocks (simplified)
- `Role` - Basic role structure
- `Playbook` - Container for plays

### Missing/Incomplete ✗

#### **Base Classes** (`lib/ansible/playbook/base.py`)
**Real Ansible:**
- `Base` - Base class for all playbook objects
- `FieldAttribute` - Descriptor for playbook attributes
- Attribute inheritance and validation
- Automatic templating of string fields

**Impact:** No proper attribute system, no automatic templating

#### **Conditional** (`lib/ansible/playbook/conditional.py`)
**Current:** Simple string evaluation
**Real Ansible:**
```python
class Conditional:
    def __init__(self, loader=None):
        self._when = []

    def evaluate_conditional(self, templar, all_vars):
        # Jinja2 template evaluation
        # Boolean coercion
        # Error handling
```

**Impact:** No proper Jinja2 conditional evaluation

#### **Loop Control** (`lib/ansible/playbook/loop_control.py`)
**Current:** Simple list iteration
**Real Ansible:**
```python
class LoopControl:
    loop_var = 'item'
    index_var = None
    label = None
    pause = 0
    extended = False
```

**Impact:** No custom loop variables, no loop pausing, no extended loop info

#### **Delegatable** (`lib/ansible/playbook/delegatable.py`)
**Current:** Basic `delegate_to` field
**Real Ansible:**
```python
class Delegatable:
    delegate_to = FieldAttribute()
    delegate_facts = FieldAttribute()
```

**Impact:** No delegation of fact gathering

#### **Taggable** (`lib/ansible/playbook/taggable.py`)
**Current:** Simple `tags` list
**Real Ansible:**
```python
class Taggable:
    tags = FieldAttribute()

    def evaluate_tags(self, only_tags, skip_tags, all_vars):
        # Tag matching logic
        # Special tags: always, never, tagged, untagged
```

**Impact:** No tag filtering, no special tags

#### **Handler System** (`lib/ansible/playbook/handler.py`, `handler_task_include.py`)
**Current:** Basic handler list
**Real Ansible:**
- Handler objects with listen functionality
- Handler task includes
- Handler flushing at specific points

**Impact:** No `listen` keyword, simplified handler execution

#### **Includes** (`lib/ansible/playbook/included_file.py`, `task_include.py`, `playbook_include.py`)
**Current:** Not implemented
**Real Ansible:**
- Dynamic task includes: `include_tasks`, `import_tasks`
- Dynamic role includes: `include_role`, `import_role`
- Playbook includes: `import_playbook`
- Static vs dynamic includes

**Impact:** No dynamic playbook composition

#### **Role Metadata** (`lib/ansible/playbook/role/metadata.py`, `requirement.py`)
**Current:** Basic role structure
**Real Ansible:**
```python
class RoleMetadata:
    dependencies = []
    galaxy_info = {}
    allow_duplicates = False
```

**Impact:** No role dependencies, no duplicate prevention

#### **Play Context** (`lib/ansible/playbook/play_context.py`)
**Current:** Simple dict
**Real Ansible:**
```python
class PlayContext:
    # Connection settings
    remote_addr
    remote_user
    port
    password
    private_key_file
    timeout

    # Privilege escalation
    become
    become_method
    become_user
    become_pass
    become_flags

    # Shell/environment
    shell
    executable
    environment
```

**Impact:** Simplified connection context, missing many options

---

## 5. Plugin System

### Implemented ✓
- **Action** - Basic action plugin system
- **Connection** - SSH and Local
- **Strategy** - Linear and Free
- **Modules** - Simulated execution

### Missing ✗

#### **Become Plugins** (`lib/ansible/plugins/become/`)
**Real Ansible:** 17 become methods
- `sudo`, `su`, `pbrun`, `pfexec`, `doas`, `dzdo`, `ksu`, `runas`, `machinectl`, etc.
- Each with specific privilege escalation logic

**Impact:** Only basic become simulation

#### **Cache Plugins** (`lib/ansible/plugins/cache/`)
**Real Ansible:**
- `jsonfile`, `memory`, `pickle`, `redis`, `memcached`, `mongodb`, `yaml`
- Fact caching across playbook runs

**Impact:** No persistent fact caching

#### **Callback Plugins** (`lib/ansible/plugins/callback/`)
**Current:** Not implemented
**Real Ansible:** 20+ callback plugins
- `default`, `json`, `minimal`, `oneline`, `junit`, `log_plays`, `mail`, `slack`, `tree`, etc.
- Event hooks for all execution stages
- Output formatting

**Impact:** No output customization, no event notifications

#### **Filter Plugins** (`lib/ansible/plugins/filter/`)
**Current:** Not implemented
**Real Ansible:** 40+ built-in filters
- `to_json`, `from_json`, `to_yaml`, `from_yaml`
- `b64encode`, `b64decode`, `hash`, `password_hash`
- `regex_search`, `regex_replace`, `regex_findall`
- `ipaddr`, `ipv4`, `ipv6`, `cidr_merge`
- Many more...

**Impact:** No template filters available

#### **Lookup Plugins** (`lib/ansible/plugins/lookup/`)
**Current:** Not implemented
**Real Ansible:** 35+ lookup plugins
- `file`, `pipe`, `env`, `password`, `template`, `url`, `csvfile`, `ini`, `dict`, `list`
- `first_found`, `random_choice`, `subelements`
- `aws_ssm`, `hashi_vault`, `etcd`, `redis_kv`

**Impact:** No external data lookups

#### **Test Plugins** (`lib/ansible/plugins/test/`)
**Current:** Not implemented
**Real Ansible:**
- Jinja2 tests: `is failed`, `is changed`, `is succeeded`, `is skipped`, `is unreachable`
- Custom tests for various checks

**Impact:** No test functions in conditionals

#### **Vars Plugins** (`lib/ansible/plugins/vars/`)
**Current:** Not implemented
**Real Ansible:**
- `host_vars`, `group_vars`, `config`, `noop`
- Auto-load variables from directories

**Impact:** No automatic variable loading

#### **Shell Plugins** (`lib/ansible/plugins/shell/`)
**Current:** Not implemented
**Real Ansible:**
- `sh`, `csh`, `fish`, `powershell`
- Shell-specific command formatting

**Impact:** Assumes sh-compatible shell

#### **Network Plugins** (cliconf, httpapi, netconf, terminal)
**Current:** Not implemented
**Real Ansible:**
- Network device communication
- CLI configuration
- NETCONF/HTTP API access

**Impact:** No network device simulation

---

## 6. Inventory System

### Implemented ✓
- Basic `Inventory`, `Host`, `Group` models
- Pattern matching for host selection
- Host/group variables

### Missing ✗

#### **Dynamic Inventory** (`lib/ansible/inventory/`)
**Current:** Static only
**Real Ansible:**
```python
class InventoryManager:
    def parse_sources(sources):
        # Parse multiple sources
        # Executable scripts
        # Plugins

    def reconcile_inventory():
        # Merge from multiple sources
        # Resolve conflicts
```

**Impact:** No dynamic inventory sources, no inventory plugins

#### **Inventory Plugins** (`lib/ansible/plugins/inventory/`)
**Real Ansible:** 20+ inventory plugins
- `yaml`, `ini`, `script`, `advanced_host_list`
- `constructed` - Generate inventory from other inventory
- Cloud providers: `aws_ec2`, `azure_rm`, `gcp_compute`, `vmware_vm_inventory`
- `docker_containers`, `kubernetes`, `openstack`

**Impact:** No cloud inventory, no container discovery

#### **Host Variables**
**Current:** Simple dict
**Real Ansible:**
```python
class Host:
    vars = AnsibleMapping()  # Special dict with precedence

    # Precedence order (low to high):
    # 1. role defaults
    # 2. inventory file/script group vars
    # 3. inventory group_vars/all
    # 4. playbook group_vars/all
    # 5. inventory group_vars/*
    # 6. playbook group_vars/*
    # 7. inventory file/script host vars
    # 8. inventory host_vars/*
    # 9. playbook host_vars/*
    # 10. host facts
    # 11. play vars
    # 12. play vars_prompt
    # 13. play vars_files
    # 14. role vars
    # 15. block vars
    # 16. task vars
    # 17. include_vars
    # 18. set_facts
    # 19. role params
    # 20. include params
    # 21. extra vars (-e)
```

**Impact:** No variable precedence system

---

## 7. Variable Management

### Implemented ✓
- Basic task variables
- Play variables
- Extra variables

### Missing ✗

#### **Variable Manager** (`lib/ansible/vars/`)
**Current:** Simple dict merging
**Real Ansible:**
```python
class VariableManager:
    def get_vars(host, task, play):
        # Merge variables from all sources
        # Apply precedence rules
        # Handle special variables

    _extra_vars  # -e command line
    _host_vars_files
    _group_vars_files
```

**Impact:** No proper variable precedence

#### **Facts**
**Current:** Simple dict in host
**Real Ansible:**
- Fact gathering modules
- Fact caching
- Fact namespacing (`ansible_facts.*)
- Custom facts from `/etc/ansible/facts.d/`

**Impact:** Basic facts only, no custom facts

#### **Magic Variables**
**Current:** Not implemented
**Real Ansible:**
- `hostvars` - Access other host variables
- `groups` - All inventory groups
- `group_names` - Groups current host belongs to
- `inventory_hostname` - Name from inventory
- `play_hosts` - All hosts in current play
- `ansible_play_hosts` - Hosts not yet failed
- `ansible_play_batch` - Current batch in serial execution
- `inventory_dir`, `playbook_dir`
- `role_path`, `role_name`
- And many more...

**Impact:** No cross-host variable access

---

## 8. Template System

### Implemented ✓
- Basic template action plugin

### Missing ✗

#### **Jinja2 Environment** (`lib/ansible/template/`)
**Current:** Not implemented
**Real Ansible:**
```python
class Templar:
    def template(variable, fail_on_undefined=True):
        # Jinja2 template rendering
        # Variable resolution
        # Filter/test application
        # Safe evaluation

    # Custom Jinja2 extensions
    # Custom filters
    # Custom tests
```

**Impact:** No actual template rendering, filters, or tests

---

## 9. Module System

### Implemented ✓
Simulated modules (13 total):
- setup, ping, command, shell, copy, file, apt, yum, service, systemd, user, template, git

### Missing ✗

**Real Ansible:** 70+ core modules in `lib/ansible/modules/`

#### **Missing Module Categories:**

**System:**
- `add_host`, `group_by`, `pause`, `wait_for`, `wait_for_connection`
- `meta`, `import_playbook`, `import_tasks`, `include_tasks`, `include_role`
- `set_fact`, `set_stats`

**Files:**
- `assemble`, `blockinfile`, `fetch`, `find`, `lineinfile`, `replace`
- `stat`, `tempfile`, `unarchive`

**Packaging:**
- `dnf`, `package`, `pip`, `rpm_key`, `yum_repository`
- `dpkg_selections`, `apt_repository`, `apt_key`

**Utilities:**
- `assert`, `debug`, `fail`, `include_vars`, `pause`
- `uri`, `get_url`, `slurp`, `reboot`

**Impact:** Limited module coverage for realistic simulations

---

## 10. Error Handling & Execution Control

### Implemented ✓
- Basic `ignore_errors`
- Task failure detection

### Missing ✗

#### **Blocks with Rescue/Always**
**Current:** Block class exists but not fully integrated
**Real Ansible:**
```python
- block:
    - task1
    - task2
  rescue:
    - rescue_task
  always:
    - cleanup_task
```

**Impact:** No error recovery blocks

#### **Error Control Keywords**
**Current:** Basic implementation
**Real Ansible:**
- `failed_when` - Custom failure conditions
- `changed_when` - Custom change detection
- `any_errors_fatal` - Stop all hosts on any failure
- `max_fail_percentage` - Threshold for play failure
- `until` / `retries` / `delay` - Task retry logic

**Impact:** No retry logic, no custom failure conditions

#### **Meta Tasks**
**Current:** Not implemented
**Real Ansible:**
```python
- meta: flush_handlers  # Run all notified handlers now
- meta: refresh_inventory  # Reload inventory
- meta: noop  # Do nothing
- meta: clear_facts
- meta: clear_host_errors
- meta: end_play
- meta: end_host
- meta: reset_connection
```

**Impact:** No meta task control flow

---

## 11. Collections

### Implemented ✓
- None

### Missing ✗

**Real Ansible:**
- Collections namespace (`ansible.builtin`, `community.general`, etc.)
- Collection loading and searching
- Collection dependencies
- FQCN (Fully Qualified Collection Names)

**Impact:** No collection support

---

## 12. Configuration

### Implemented ✓
- `ansible-config dump` (simulated)
- Basic forks setting

### Missing ✗

**Real Ansible:** (`lib/ansible/config/`)
- Configuration file parsing (`ansible.cfg`)
- Environment variable overrides
- 100+ configuration options
- Configuration precedence: ENV > ansible.cfg > defaults

**Impact:** No configuration file support

---

## 13. Parsing & Data Loading

### Implemented ✓
- Basic pydantic models for plays/tasks

### Missing ✗

**Real Ansible:** (`lib/ansible/parsing/`)
- YAML parsing with position tracking
- Vault encrypted content
- DataLoader with include/import support
- Syntax error reporting with line numbers

**Impact:** No vault decryption, no detailed error messages

---

## 14. Connection & Remote Execution

### Implemented ✓
- SSH connection simulation
- Local connection
- Basic module execution

### Missing ✗

#### **Connection Methods**
**Real Ansible:** 15+ connection plugins
- `ssh`, `paramiko_ssh`, `local`, `docker`, `kubectl`, `podman`
- `psrp`, `winrm`, `httpapi`, `netconf`, `network_cli`
- `buildah`, `chroot`, `jail`, `lxc`, `zone`

**Impact:** No container/Windows connections

#### **SSH Features**
**Current:** Basic connection
**Real Ansible:**
- ControlPersist connection multiplexing
- ProxyJump/ProxyCommand
- SSH agent forwarding
- Known hosts checking
- Custom SSH arguments

**Impact:** No SSH optimizations

#### **SFTP/SCP**
**Current:** Simulated file transfer
**Real Ansible:**
- Smart file copying (checksums)
- Partial file transfer
- Permission preservation

**Impact:** Simplified file transfer

---

## 15. Async & Polling

### Implemented ✓
- None

### Missing ✗

**Real Ansible:**
```yaml
- command: long_running_task
  async: 3600  # Max time
  poll: 10     # Check every 10s

- async_status:
    jid: "{{ job.ansible_job_id }}"
  register: job_result
  until: job_result.finished
  retries: 30
```

**Impact:** No background task execution

---

## 16. Serial Batching

### Implemented ✓
- Basic serial concept in Play model

### Missing ✗

**Real Ansible:**
```yaml
- hosts: webservers
  serial:
    - 1      # First host
    - 5      # Next 5
    - 10%    # Then 10% at a time
    - 100%   # Rest all at once
```

**Impact:** No complex serial patterns

---

## 17. Throttle

### Implemented ✓
- Fork limit

### Missing ✗

**Real Ansible:**
```yaml
- hosts: all
  throttle: 5  # Max 5 hosts at once (even if forks=10)
```

**Impact:** No per-play throttling

---

## 18. Run Once

### Implemented ✓
- `run_once` field in Task

### Missing ✗
- Actual implementation of run_once execution logic

**Impact:** run_once tasks will run on all hosts

---

## Summary Statistics

| Category | Implemented | Missing | Coverage |
|----------|-------------|---------|----------|
| CLI Commands | 6 | 3 | 67% |
| Executor Components | 5 | 5 | 50% |
| Strategy Plugins | 2 | 2 | 50% |
| Playbook Components | 5 | 10+ | 33% |
| Plugin Types | 4 | 13 | 24% |
| Core Modules | 13 | 57+ | 19% |
| Variables | 3 | 5+ | 38% |
| Templates | 1 | 5+ | 17% |
| Inventory | 3 | 5+ | 38% |
| Connection Types | 2 | 13+ | 13% |

**Overall Simulator Coverage: ~35-40% of Ansible Core functionality**

---

## Priority Recommendations

### High Priority (Critical for Realism)

1. **AggregateStats** - Proper per-host statistics tracking
2. **TaskResult Wire Format** - Use dataclass pattern with task UUIDs
3. **Callback System** - Event hooks for output/notifications
4. **Block Rescue/Always** - Error recovery
5. **Variable Precedence** - Proper variable merging
6. **Handler Flushing** - Correct handler execution timing
7. **Tag Filtering** - Run/skip based on tags

### Medium Priority (Enhanced Functionality)

8. **Debug Strategy** - Interactive debugging
9. **Loop Control** - Extended loop features
10. **Include/Import** - Dynamic playbook composition
11. **Filter Plugins** - Template filters
12. **Lookup Plugins** - External data sources
13. **Fact Caching** - Persistent facts
14. **Meta Tasks** - Execution control

### Low Priority (Nice to Have)

15. **Additional Modules** - More core modules
16. **Collections** - Namespace support
17. **Inventory Plugins** - Cloud inventory
18. **Additional Connection Types** - Windows, containers
19. **Async Execution** - Background tasks
20. **Configuration Files** - ansible.cfg parsing
