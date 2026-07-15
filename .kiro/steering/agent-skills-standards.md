---
inclusion: auto
---

# Agent Skills Standards

## When to Create Skills

Create a reusable skill file (in `.kiro/skills/`) when any of these conditions are met:

1. **Repeated patterns** — A task involves the same sequence of steps across multiple files or features (e.g., "add a new Gradio form with validation", "create a new report view")
2. **Complex domain knowledge** — A task requires specific knowledge about the project's architecture, conventions, or external APIs that isn't obvious from the code alone
3. **Multi-step workflows** — A task involves coordinating actions across multiple components (e.g., "add field to tracker → update sync → update Sheets schema → update dashboard view")
4. **Code generation templates** — A pattern that produces boilerplate code following project standards (e.g., new hexagonal port/adapter pair, new test file structure)
5. **Integration patterns** — Interacting with external services following specific retry, timeout, and error handling conventions

## Skill File Structure

Each skill should include:
- **Purpose**: One-line description of what the skill does
- **When to use**: Conditions that trigger using this skill
- **Steps**: Ordered sequence of actions
- **Conventions**: Project-specific rules to follow (naming, file locations, patterns)
- **Validation**: How to verify the skill was applied correctly

## Skills to Create for This Project

- `gradio-form-creation` — Standard pattern for adding new forms with validation, accessibility, and Sheets integration
- `google-sheets-integration` — How to read/write to Sheets with proper timeout, retry, and error handling
- `tracker-component-addition` — Adding new monitoring capabilities to the tracker with proper hash chain integration
- `report-creation` — Standard pattern for adding new reports with RBAC, export, and audit logging
- `test-creation` — How to write unit, integration, and property-based tests following project conventions
- `hexagonal-port-adapter` — Creating new ports and adapters following the hexagonal architecture
- `security-validation` — Input validation patterns following OWASP standards

## Naming Convention

- File location: `.kiro/skills/{skill-name}.md`
- Naming: kebab-case, descriptive of the action (e.g., `add-gradio-form.md`, not `forms.md`)
- Keep each skill focused on ONE task pattern
