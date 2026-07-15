# Skill: Add a Gradio Form

## Purpose
Create a new user-facing form in the Portal with proper validation, accessibility, and service integration.

## When to Use
- Adding a new form (e.g., employee management, settings, new exception type)
- Adding fields to an existing form

## Steps
1. Define Pydantic request model in `src/portal/domain/models.py` with Field constraints
2. Define response model (dataclass or Pydantic) for service return
3. Add service method in appropriate `src/portal/services/{service}.py` with decorators
4. Create or update Gradio view in `src/portal/views/{view}.py`
5. Wire submit button to service method via async handler
6. Add validation error display (field-specific messages)
7. Write unit test for service method (mock store)
8. Write property test if validation has numeric ranges

## Conventions
- Form in views/ calls service in services/ — NEVER contains business logic
- All inputs validated by Pydantic BEFORE reaching service
- Error messages: plain language, field-specific
- Success feedback: confirmation with timestamp within 2 seconds
- Accessibility: visible labels, focus indicators, ARIA error linking
