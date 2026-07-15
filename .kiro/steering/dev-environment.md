---
inclusion: auto
---

# Development Environment Governance

## Required Tools (All Free)

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| pip-tools | latest | Dependency management |
| Ruff | latest | Lint + format |
| mypy | latest | Type checking (strict) |
| pytest | 7.x+ | Test runner |
| Hypothesis | latest | Property-based testing |
| Playwright | latest | E2E browser testing |
| import-linter | latest | Architecture boundary tests |
| pre-commit | latest | Git hook management |
| Snyk CLI | latest | Security scanning |

## Setup Steps (New Developer)
1. Clone repo
2. Create virtualenv: `python -m venv .venv` and activate
3. Install: `pip install -r requirements-dev.txt`
4. Install pre-commit hooks: `pre-commit install`
5. Copy env: `cp .env.example .env.local` — fill test credentials
6. Verify: `pytest tests/unit/ -x`
7. Install Playwright: `playwright install chromium`

## Environment Files
- `.env.example` — template (committed, no secrets)
- `.env.local` — developer local config (gitignored)
- `requirements.txt` — production deps (pinned exact versions)
- `requirements-dev.txt` — dev + test deps (pinned exact versions)

## Pre-Commit Hooks (.pre-commit-config.yaml)
1. detect-secrets — blocks commits with API keys
2. ruff — lint check
3. ruff-format — auto-format
4. mypy (incremental) — type check changed files
5. check-merge-conflict — no merge markers
6. trailing-whitespace + end-of-file-fixer

## Version Pinning
- Exact versions only (==) in committed requirements
- Generate: `pip-compile requirements.in -o requirements.txt`
- Update: `pip-compile --upgrade` then full test suite
- NEVER use >= or ~= ranges

## Git Branch Strategy
- main — production (protected, requires PR + review + CI)
- feature/{id}-{desc} — feature branches
- fix/{id}-{desc} — bugfix branches
- Trunk-based: short-lived branches merged quickly
