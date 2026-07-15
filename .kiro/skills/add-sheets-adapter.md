# Skill: Add a Google Sheets Adapter

## Purpose
Create a new adapter for Google Sheets with timeout, retry, and circuit breaker.

## When to Use
- Implementing a port that reads/writes to Google Sheets
- Adding a new sheet to the Central Store

## Steps
1. Define port interface (Protocol) in ports/
2. Create adapter in adapters/sheets_{name}.py
3. Inject circuit breaker for all external calls
4. Set timeouts: 10s read, 15s write, 30s batch
5. Single retry after 5s on timeout
6. Cache worksheet references
7. Limit concurrent calls (max 5)
8. Write integration test + unit test with mocks

## Conventions
- Timestamps: ISO 8601 UTC strings
- Tenant_ID: first column in every sheet
- Batch operations where possible
- Rate limit: 1 write/5s during sync
- Failure: graceful degradation (queue, retry)
- Never expose gspread objects outside adapter
