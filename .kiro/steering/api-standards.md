---
inclusion: auto
---

# Internal API-First Design Standards

## Service Interface Conventions

All business operations MUST be exposed as typed service interfaces, independent of the Gradio UI.

### Port Interface Rules
- Define all ports as `typing.Protocol` (PEP 544) in `ports/` directory
- Each port method MUST have full type annotations (params + return)
- Use `Optional[T]` for nullable returns (never bare `None`)
- Document authorization requirements in docstrings

### Service Class Rules
- All service classes live in `services/` directory
- Constructor injection for ALL dependencies (ports, config, event bus)
- NEVER import concrete adapters in service classes
- Use decorators for cross-cutting concerns (@require_auth, @audit_log, @require_permission)

### Pydantic Model Rules
- ALL service method inputs MUST be Pydantic BaseModel instances
- ALL service method outputs MUST be dataclasses or Pydantic models
- Use `Field()` with constraints (ge, le, min_length, max_length)
- Use `@field_validator` for complex validation (e.g., divisible by 5)
- NEVER accept raw `dict`, `str`, or primitive arguments for complex operations

### Naming Conventions

| Artifact | Pattern | Example |
|----------|---------|---------|
| Port interface | `{Noun}Port` | `ClockStorePort`, `EmailSenderPort` |
| Adapter class | `{Implementation}{Noun}Adapter` | `SheetsClockAdapter`, `GeminiClassifierAdapter` |
| Service class | `{Noun}Service` | `ClockService`, `ReconciliationService` |
| Request model | `{Action}Request` | `ClockInRequest`, `ExceptionSubmitRequest` |
| Response model | `{Action}Response` | `ClockInResponse`, `VarianceResult` |
| Domain entity | Plain noun | `Employee`, `LogEntry`, `Session` |
| Enum | Descriptive noun | `ActivityStatus`, `FlagColor`, `Permission` |

### Gradio View Layer Rules
- Views are THIN adapters — call service methods, render results
- ZERO business logic in view files
- Use service method return values directly for display
- Error handling: catch service exceptions, display user-friendly messages
