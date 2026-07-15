---
inclusion: auto
---

# Agent Coordination & Efficiency Standards

## Token Efficiency Rules

### Minimize Context Loading
- Only read files directly relevant to the current task
- Use `read_code` with selectors for large files instead of reading entire files
- Use `grep_search` to find specific patterns instead of reading multiple files
- Never re-read a file that was already read in the same session unless it was modified

### Minimize Output
- Keep explanations concise — developers reading this are experienced
- Don't repeat code that wasn't changed
- Use `str_replace` for targeted edits instead of rewriting entire files
- Group related small changes into a single tool call where possible

### Prefer Targeted Operations
- Use `grep_search` over reading entire directories
- Use `file_search` to locate files instead of `list_directory` recursion
- Use `read_file` with line ranges for known sections of large files
- Use `str_replace` over `fs_write` for modifications to existing files

## Parallel Execution Guidelines

### Independent Tasks Run in Parallel
When multiple tasks have no dependencies (different modules, different files), they should be dispatched to sub-agents simultaneously. Examples:
- Tracker domain logic and Portal domain logic (separate bounded contexts)
- Unit tests for module A and unit tests for module B
- Multiple adapter implementations that share no code

### Sequential Only When Required
Tasks must run sequentially only when:
- Task B reads or imports from output of Task A
- Task B modifies the same file as Task A
- Task B's tests depend on fixtures created by Task A

### Task Decomposition for Parallelism
Break large tasks into smaller units that can execute in parallel:
- Instead of "Implement the Portal" → break into "Employee auth module", "Clock-in module", "Exception module", "HR dashboard module"
- Instead of "Write all tests" → break into "Tests for domain layer", "Tests for adapters", "Tests for ports"

## Sub-Agent Coordination Pattern

### Manager Agent Role
The orchestrating agent (task executor) acts as manager:
1. Reads the task and its sub-tasks
2. Identifies which sub-tasks are independent (can parallelize)
3. Dispatches independent sub-tasks to sub-agents simultaneously
4. Waits for completion
5. If a sub-agent fails: reads the error, determines fix approach, retries
6. If fix requires changes in another sub-agent's output: runs sequentially

### Error Resolution Strategy
When a sub-agent encounters an error:
1. **First attempt**: Sub-agent tries to self-fix (compile error, missing import, typo)
2. **Second attempt**: Sub-agent tries a different approach
3. **Escalation**: If still failing, return error to orchestrator with diagnosis
4. **Orchestrator fix**: Orchestrator reads the error context, identifies root cause, and either:
   - Provides additional context and retries the sub-agent
   - Fixes a dependency in another file and retries
   - Merges the task with the blocking task and runs sequentially

### Communication Between Agents
- Sub-agents communicate ONLY through files (source code, test results, build output)
- No "state" is passed verbally between agents — everything is in the codebase
- Each sub-agent should verify prerequisites before starting (check that expected files/interfaces exist)

## Project-Specific Bounded Contexts (Parallelizable)

These domains are independent and can be developed in parallel:

| Domain | Files | Dependencies |
|--------|-------|-------------|
| Tracker: Activity Monitor | src/tracker/domain/activity.py, adapters/input_monitor.py | None |
| Tracker: Location Detector | src/tracker/domain/location.py, adapters/wifi_detector.py | None |
| Tracker: Sync Engine | src/tracker/domain/sync.py, adapters/sheets_sync.py | Depends on Activity + Location (interfaces only) |
| Portal: Authentication | src/portal/domain/auth.py, adapters/email_sender.py | None |
| Portal: Clock In/Out | src/portal/domain/clock.py, adapters/sheets_clock.py | Depends on Auth (interface only) |
| Portal: Exception Form | src/portal/domain/exception.py, adapters/gemini_tagger.py | Depends on Auth (interface only) |
| Portal: HR Dashboard | src/portal/domain/reconciliation.py, views/hr_dashboard.py | Depends on Clock + Exception (read interfaces) |
| Portal: Reports | src/portal/domain/reports.py, views/report_views.py | Depends on Reconciliation (read interface) |
| Portal: RBAC | src/portal/domain/rbac.py | None |

## Hooks Integration
- Pre-write hook (architecture-guard) ensures agents don't create files in wrong locations
- Post-task hook (post-task-test) catches integration issues between parallel work
- Lint-on-save ensures consistent formatting regardless of which agent wrote the code
