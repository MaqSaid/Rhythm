# Skill: Mock External APIs for Testing

## Purpose
Standardized pattern for mocking Sheets, Gemini, Email, NTP in tests.

## When to Use
- Unit tests calling service methods with external dependencies
- Testing error scenarios (timeout, rate limit, malformed response)
- Creating test fixtures

## Patterns

### Port-Level Mocking (Unit Tests)
- Use AsyncMock(spec=PortInterface) for all async ports
- Mock at PORT level, never at adapter implementation level
- Set return_value for success, side_effect for errors

### HTTP-Level Mocking (Gemini API)
- Use `responses` library for HTTP-based APIs
- Mock exact URL + method + response body
- Timeout: `body=requests.exceptions.Timeout()`
- Rate limit: status=429
- Malformed: valid JSON but unexpected content

### Time Mocking
- Use freezegun to control datetime.now()
- NTP mock returns fixed datetime via TimeServicePort mock
- Test drift by setting different local vs NTP times

## Conventions
- Always test BOTH success AND failure paths
- Use AsyncMock for injected ports
- Use responses library for raw HTTP mocking
- Use freezegun for time-dependent logic
- Never call real external services in unit tests
- Integration tests use dedicated test accounts (wiped after)
