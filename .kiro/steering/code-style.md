---
inclusion: auto
---

# Python Code Style Standards

## Enforced By
- **Ruff**: Linting + formatting (replaces Black + isort + flake8)
- **mypy strict**: Type checking
- Both run in CI as merge gates

## Type Hints (Mandatory)
- ALL function parameters: typed
- ALL return values: typed (use `-> None` explicitly)
- ALL class attributes: typed
- Use `Optional[T]` not `T | None` (compatibility)
- Use `list[T]`, `dict[K, V]` (lowercase, Python 3.9+)

## Imports
- Standard library first, then third-party, then local
- Absolute imports only (no relative imports)
- Never `from module import *`
- Group with blank lines between sections

## Naming
| Item | Convention | Example |
|------|-----------|---------|
| Module | snake_case | `clock_service.py` |
| Class | PascalCase | `ClockService` |
| Function/Method | snake_case | `get_open_session` |
| Constant | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| Private | _prefixed | `_validate_input` |
| Protocol/ABC | PascalCase + Port suffix | `ClockStorePort` |
| Enum member | UPPER_SNAKE | `ActivityStatus.ONLINE` |

## Docstrings (Google style, mandatory on public interfaces)

## Code Rules
- Max line length: 100 characters
- No eval/exec/pickle.loads/__import__
- No shell=True in subprocess
- No string interpolation in SQL
- No bare except — always specify type
- No mutable default arguments
- Use dataclass(frozen=True) for value objects
- Use Enum for all fixed-value sets
- Use context managers for resource acquisition
