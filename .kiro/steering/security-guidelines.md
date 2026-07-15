---
inclusion: auto
---

# Security Guidelines

## Secrets Management
- NEVER hardcode API keys, credentials, or tokens in source code
- Use environment variables (HF Space Secrets for Portal, config file for Tracker)
- Service account JSON keys: OS-level file permissions (600, owned by service account)
- Git: add `.env`, `*.json` credential files to `.gitignore`

## Input Validation
- ALL user inputs validated via Pydantic models before processing
- Email: RFC 5322 format
- Duration: integer, 5-480, divisible by 5
- Text comments: 10-500 characters
- Dropdowns: value must be member of defined Enum
- Reject invalid input with field-specific error message

## Command Injection Prevention
- ALWAYS use subprocess with argument arrays: `subprocess.run(["cmd", "arg1"])`
- NEVER use `shell=True`
- NEVER interpolate variables into command strings
- Validate subprocess output against expected patterns
- Discard and default on malformed output

## Prompt Injection Defense (Gemini Tagger)
- Fixed system instruction template (not user-modifiable)
- Employee text sandwiched between XML delimiters
- Strip instruction-like patterns before prompt construction
- Validate response matches EXACTLY one allowed category
- Non-matching response → "Unclassified"
- NEVER include secrets or config in prompts

## Authentication & Sessions
- Magic Links: secrets.token_urlsafe (32 bytes)
- Token expiry: 10 min (employee), 15 min (HR)
- Single-use tokens
- 30-min inactivity timeout
- Single active session per user
- Cookies: HttpOnly, Secure, SameSite=Strict

## Rate Limiting
- Login: 3 per email per 15 min
- Exceptions: 10 per employee per day
- Global: 100 per IP per minute

## Banned Patterns
- No eval(), exec(), pickle.loads(), __import__()
- No shell=True in subprocess
- No string interpolation in SQL/commands
- No os.system()
- No bare except clauses
