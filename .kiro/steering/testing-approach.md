---
inclusion: auto
---

# Testing Approach Standards

## Test File Naming
- Unit tests: `tests/unit/test_{module_name}.py`
- Property tests: `tests/property/test_{property_group}.py`
- Integration tests: `tests/integration/test_{service_name}.py`
- E2E tests: `tests/e2e/test_{user_flow}.py`
- Security tests: `tests/security/test_{attack_type}.py`
- Architecture tests: `tests/architecture/test_boundaries.py`

## Unit Test Structure (Given-When-Then in docstring)
- Class per service/module: `class TestClockService`
- Method per scenario: `test_clock_in_rejected_when_session_open`
- Docstring: GIVEN...WHEN...THEN format
- Use pytest fixtures for dependency injection (not manual setup)

## Property Test Format
- Tag each test: `# Feature: fraud-proof-hybrid-timesheet, Property {N}: {title}`
- Use Hypothesis strategies for input generation
- Minimum 100 iterations per property
- Assert invariant holds for ALL generated inputs
- Group by domain concern (time logic, data integrity, validation, etc.)

## What to Mock vs What to Test Live
| Dependency | Unit Tests | Integration Tests |
|-----------|:---:|:---:|
| Google Sheets API | Mock (responses library) | Live (test sheet, wiped after) |
| Gemini API | Mock (responses library) | Live (real API) |
| SQLite | In-memory DB (:memory:) | Temp file DB |
| Email | Mock (never send real) | Mailtrap (free) |
| NTP | Mock (fixed response) | Live time.google.com |
| Filesystem | tmpdir fixture | Real paths |
| Time/datetime | freezegun | Real time |

## Test Execution Budgets
- Unit + Property: < 30 seconds total
- Integration: < 120 seconds total
- E2E: < 300 seconds total

## Rules
- All tests MUST be independent (no shared state)
- Use fixtures for setup/teardown
- Each test file runnable in isolation
- Use `pytest.mark.parametrize` for example-based exhaustive coverage
- Never test implementation details — test behavior through ports
