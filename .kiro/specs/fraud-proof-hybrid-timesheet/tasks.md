# Implementation Plan: Fraud-Proof Hybrid Timesheet

## Overview

This plan implements the Fraud-Proof Hybrid Timesheet system as a modular monolith with two deployable units (Tracker + Portal) using Python, hexagonal architecture (ports and adapters), DDD bounded contexts, and constructor injection. The implementation proceeds from shared kernel through Tracker domain to Portal domain, wiring everything together with CI/CD and testing.

## Tasks

- [ ] 1. Project Setup and Shared Kernel
  - [x] 1.1 Initialize Python project structure with pyproject.toml
    - Create directory structure matching the design: `src/tracker/`, `src/portal/`, `src/shared/`, `tests/`, `scripts/`
    - Configure pyproject.toml with dependencies: gradio, gspread, pynput, pydantic, hypothesis, pytest, playwright, ruff, mypy, import-linter, axe-core-python
    - Pin all dependency versions with exact (==) specifiers
    - Create `requirements.txt` via pip-compile for deterministic builds
    - _Requirements: 44.1, 46.1, 49.1_

  - [x] 1.2 Implement shared kernel value objects and enums
    - Create `src/shared/enums.py` with all Python Enums
    - Create `src/shared/value_objects.py` with EmployeeID, TenantID, Timestamp frozen dataclasses
    - Create `src/shared/work_schedule.py` with TimeBlock and WorkSchedulePattern dataclasses
    - Create `src/shared/config.py` with TenantConfig and WhiteLabelConfig Pydantic models including validation ranges
    - Create `src/shared/time_utils.py` with UTC conversion, 5-min boundary alignment, and review period calculation
    - _Requirements: 44.3, 46.2, 46.6, 22.4_

  - [x]* 1.3 Write property tests for clock-aligned boundary and configurable parameters
    - **Property 1: Clock-aligned boundary computation** — verify next boundary is smallest 5-min point >= input
    - **Property 30: Configurable parameter validation** — verify acceptance/rejection against allowed ranges
    - **Validates: Requirements 1.3, 22.4, 22.5**

- [ ] 2. Tracker Domain — Activity Monitoring and Location Detection
  - [x] 2.1 Define Tracker port interfaces
    - Create `src/tracker/ports/input_monitor.py` with ActivityMonitorPort Protocol
    - Create `src/tracker/ports/wifi_detector.py` with WifiDetectionPort Protocol
    - Create `src/tracker/ports/local_storage.py` with LocalStoragePort Protocol
    - Create `src/tracker/ports/remote_store.py` with RemoteStorePort Protocol
    - Create `src/tracker/ports/time_service.py` with TimeServicePort Protocol
    - Create `src/tracker/ports/notification.py` with ToastNotificationPort and FocusModePort Protocols
    - Create `src/tracker/ports/logger.py` with StructuredLoggerPort Protocol
    - _Requirements: 44.2, 44.5, 46.3, 47.3_

  - [x] 2.2 Implement Tracker domain models
    - Create `src/tracker/domain/models.py` with LogEntry, WifiInfo, SyncBatch, QuickException frozen dataclasses
    - Create `src/tracker/domain/enums.py` importing shared enums and adding Tracker-specific types
    - All entities use frozen=True for immutability; all fields fully typed
    - _Requirements: 46.2, 44.3_

  - [x] 2.3 Implement Activity Monitor domain logic
    - Create `src/tracker/domain/activity.py` with ActivityMonitor class
    - Implement 5-minute clock-aligned interval detection with boundary computation
    - Implement idle threshold logic: configurable continuous minutes with no signals sets Idle
    - Implement resume detection: activity after Idle period sets back to Online
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7_

  - [x]* 2.4 Write property tests for activity status determination
    - **Property 2: Activity-based status determination** — verify Idle iff no signals >= idle threshold
    - **Validates: Requirements 1.4, 1.5**

  - [x] 2.5 Implement Location Detector domain logic
    - Create `src/tracker/domain/location.py` with LocationDetector class
    - Implement SSID+BSSID matching against office network list
    - Handle edge cases: no WiFi, empty office list, detection failure, timeout — all default to "home"
    - Validate output format: SSID alphanumeric, BSSID hex MAC format
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 25.1, 25.2, 25.3, 25.4_

  - [x]* 2.6 Write property tests for location detection and output validation
    - **Property 4: Location detection correctness** — "office" iff both SSID+BSSID match; "home" otherwise
    - **Property 31: SSID/BSSID output format validation** — accept valid patterns, reject malformed
    - **Validates: Requirements 2.1-2.7, 25.3, 25.4**

  - [x] 2.7 Implement platform-specific WiFi adapters (Strategy Pattern)
    - Create `src/tracker/adapters/windows_wifi.py` using netsh with subprocess arg array
    - Create `src/tracker/adapters/macos_wifi.py` using system_profiler with subprocess arg array
    - Implement 5-second timeout; factory function selects adapter by platform
    - _Requirements: 2.5, 25.1, 25.2, 44.6_

- [ ] 3. Tracker Domain — Hash Chain Integrity and Local Storage
  - [x] 3.1 Implement Hash Chain Manager
    - Create `src/tracker/domain/integrity.py` with HashChainManager class
    - SHA-256 computation chaining each entry with the previous hash
    - Full chain verification at startup and before sync
    - Tamper detection: flag entries from last valid to mismatch as "Integrity Violation"
    - Recovery after crash: discard incomplete entry, start new chain, no false flag
    - _Requirements: 4.4, 4.5, 4.6, 51.13_

  - [x]* 3.2 Write property tests for hash chain integrity
    - **Property 5: SHA-256 hash chain integrity computation**
    - **Property 6: Hash chain tamper detection**
    - **Property 7: Hash chain recovery after incomplete write**
    - **Validates: Requirements 4.4, 4.5, 4.6, 51.13**

  - [x] 3.3 Implement SQLite Local Storage adapter
    - Create `src/tracker/adapters/sqlite_storage.py` implementing LocalStoragePort
    - Configure WAL mode and busy_timeout; create schema with indexes
    - Implement write retry: retain in memory, retry next cycle, max 3 attempts
    - Use context managers for all DB connections
    - _Requirements: 1.8, 4.1, 51.12, 46.4_

  - [x]* 3.4 Write property test for write retry bounds
    - **Property 3: Write retry bounded at 3 attempts**
    - **Validates: Requirements 1.8**

- [ ] 4. Tracker Domain — Sync Engine and NTP Validation
  - [ ] 4.1 Implement NTP Validator
    - Create `src/tracker/domain/sync.py` with NTPValidator class
    - Query time.google.com with 5-second timeout; compare local UTC vs NTP time
    - Flag "Clock Drift Detected" if drift > 2 minutes; apply offset to timestamps
    - Mark "NTP Unavailable" if server unreachable; proceed with local time
    - _Requirements: 3.6, 3.7, 3.9, 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 4.2 Write property test for NTP drift detection
    - **Property 19: NTP drift detection and timestamp correction**
    - **Validates: Requirements 3.7, 14.2, 14.3, 14.4, 14.5**

  - [ ] 4.3 Implement Sync Engine service
    - Create `src/tracker/services/sync_service.py` with SyncService class
    - Midnight batch sync: aggregate previous 24h, push within 60s of midnight
    - Offline queue: retain up to 90 days; push chronologically at 1 entry/5s
    - Heartbeat every 30 minutes; silent retry on failure
    - Failed sync returns entry to front of queue; retry next cycle
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.8, 3.10, 15.1_

  - [ ]* 4.4 Write property test for sync queue ordering
    - **Property 20: Sync queue chronological ordering invariant**
    - **Validates: Requirements 3.3, 3.8**

  - [ ] 4.5 Implement NTP adapter
    - Create `src/tracker/adapters/ntp_time.py` implementing TimeServicePort
    - UDP query with 5-second timeout; return datetime or None
    - _Requirements: 14.1, 46.4_

  - [ ] 4.6 Implement Google Sheets remote store adapter for Tracker
    - Create `src/tracker/adapters/sheets_remote.py` implementing RemoteStorePort
    - Use gspread with service account; 30-second timeout for batch push
    - Retry once after 5s on timeout; circuit breaker integration
    - _Requirements: 28.3, 28.4, 28.5, 45.3_

- [ ] 5. Tracker Domain — Notifications, Focus Mode, and Logging
  - [ ] 5.1 Implement Notification domain logic and auto-exempt threshold
    - Create `src/tracker/domain/notification.py` with NotificationService
    - Auto-exempt: idle <= threshold → no notification, normal work
    - Idle > threshold AND Focus Mode inactive → toast with 4 category buttons
    - Idle > threshold AND Focus Mode active → "Unmarked Idle" automatically
    - Toast auto-dismiss 5 min → "Unmarked Idle"; quick exception records to Local_DB
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 56.7_

  - [ ]* 5.2 Write property test for auto-exempt idle threshold
    - **Property 34: Auto-exempt idle threshold decision**
    - **Validates: Requirements 7.1, 7.3**

  - [ ] 5.3 Implement Focus Mode domain logic
    - Create `src/tracker/domain/focus_mode.py` with FocusMode class
    - Duration presets 1-4h; suppresses toasts; tracking unchanged; private
    - _Requirements: 56.1, 56.2, 56.3, 56.4, 56.5, 56.7, 56.8, 56.9_

  - [ ]* 5.4 Write property test for focus mode recording invariant
    - **Property 40: Focus mode recording invariant**
    - **Validates: Requirements 56.4, 56.7, 56.9**

  - [ ] 5.5 Implement Toast Notification and System Tray adapters
    - Create `src/tracker/adapters/toast_notification.py` and `system_tray.py`
    - OS-native toast with 4 buttons; system tray right-click menu with Focus Mode
    - _Requirements: 7.1, 56.1, 56.6_

  - [ ] 5.6 Implement Structured JSON Logger adapter
    - Create `src/tracker/adapters/json_logger.py` implementing StructuredLoggerPort
    - Fields: timestamp, level, component, event_type, employee_id, message, details
    - Rotation at 5 MB; max 5 files
    - _Requirements: 18.1, 18.4, 18.5, 18.6_

  - [ ]* 5.7 Write property tests for logging
    - **Property 24: Structured JSON log entry completeness**
    - **Property 25: Log file rotation**
    - **Validates: Requirements 18.1, 18.4, 18.5, 18.6**

- [ ] 6. Tracker — Main Orchestrator, Service Registration, and Build
  - [ ] 6.1 Implement Tracker main orchestrator service
    - Create `src/tracker/services/tracker_service.py` with TrackerLoop
    - 5-min timer cycle: activity check, status, location, hash, write
    - Heartbeat scheduling and midnight sync trigger
    - _Requirements: 1.2, 1.3, 3.1, 3.4, 4.4_

  - [ ] 6.2 Implement Startup and Service Registration
    - Create `src/tracker/services/startup_service.py`
    - Verify service registration; retry 3x at 10s intervals
    - Hash chain verification on startup; log startup with version
    - _Requirements: 4.3, 13.3, 13.5, 13.6, 43.5_

  - [ ] 6.3 Implement Tracker entry point with DI wiring
    - Create `src/tracker/main.py` as composition root
    - Constructor injection for all services; load config from protected JSON
    - Validate config at startup; fail fast on invalid values
    - _Requirements: 46.7, 49.4, 49.5, 13.2_

  - [ ] 6.4 Implement pynput Activity Monitor adapter
    - Create `src/tracker/adapters/pynput_monitor.py` implementing ActivityMonitorPort
    - Detect keyboard, mouse, scroll, active window change events
    - _Requirements: 1.1, 46.4_

  - [ ] 6.5 Configure PyInstaller build
    - PyInstaller spec for Windows .exe and macOS .app (single-file)
    - Windows Service registration; macOS LaunchDaemon plist
    - Employee_ID embedding during installation
    - _Requirements: 13.1, 13.2, 4.1, 4.2_

- [ ] 7. Checkpoint — Tracker Domain Complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Portal Domain — Authentication and Session Management
  - [ ] 8.1 Define Portal port interfaces
    - Create Protocol interfaces in `src/portal/ports/` for all stores, AI classifier, email, notification, config, cache
    - Each port typed with docstrings specifying inputs, outputs, exceptions
    - _Requirements: 44.2, 46.3, 47.3, 47.4_

  - [ ] 8.2 Implement Portal domain models (Pydantic)
    - Create `src/portal/domain/models.py` with all Pydantic models
    - Create `src/portal/domain/enums.py` with Portal-specific enums
    - Implement field validators (duration % 5, email format, allowed values)
    - _Requirements: 46.2, 47.6_

  - [ ] 8.3 Implement Authentication domain logic
    - Create `src/portal/domain/auth.py` with AuthService
    - Magic Link: single-use token, 10/15 min expiry, rate limit check
    - Session: single-session enforcement, 30 min inactivity timeout
    - Reject unregistered emails without sending email
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 11.1, 11.2, 11.5, 11.6_

  - [ ]* 8.4 Write property tests for authentication
    - **Property 8: Magic Link validity determination**
    - **Property 9: Session expiry after inactivity**
    - **Property 10: Single active session per user invariant**
    - **Validates: Requirements 5.2, 5.3, 5.5, 5.6, 5.7, 11.1, 11.2, 11.5, 11.6**

- [ ] 9. Portal Domain — Clock-In/Out and Exception Reporting
  - [ ] 9.1 Implement Clock-In/Out domain logic
    - Create `src/portal/domain/clock.py` with ClockService
    - Clock-in/out with session state validation; auto-close at 23:00
    - Optimistic accept on store unavailable; idempotency keys
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 51.1, 51.9_

  - [ ]* 9.2 Write property tests for clock session logic
    - **Property 11: Clock session state machine**
    - **Property 12: Clock session duration calculation**
    - **Property 13: Auto-clock-out trigger**
    - **Property 29: Idempotency key deduplication**
    - **Validates: Requirements 6.3, 6.4, 6.5, 6.6, 6.7, 51.9**

  - [ ] 9.3 Implement Exception Reporting domain logic
    - Create `src/portal/domain/exception.py` with ExceptionService
    - Quick toast exceptions and detailed form validation
    - Approval workflow (Pending/Approved/Rejected); HR self-approval prohibition
    - _Requirements: 7.6, 7.7, 34.1-34.8, 35.5, 35.8_

  - [ ]* 9.4 Write property tests for validation and HR self-approval
    - **Property 14: Input validation correctness**
    - **Property 35: HR self-approval prohibition**
    - **Validates: Requirements 7.6, 7.7, 16.1, 35.5, 35.8**

- [ ] 10. Portal Domain — AI Tagging, RBAC, and Rate Limiting
  - [ ] 10.1 Implement Gemini Tagger domain logic
    - Skip conditions: comment < 3 chars, rate exceeded, API unavailable
    - Validate response against allowed categories; prompt injection defense
    - Async fire-and-forget classification; reclassify when available
    - _Requirements: 8.1, 8.2, 8.4-8.9, 39.1-39.7, 15.6_

  - [ ]* 10.2 Write property tests for Gemini Tagger
    - **Property 15: Gemini Tagger skip conditions**
    - **Property 16: Gemini response validation**
    - **Validates: Requirements 8.4, 8.6, 8.7, 39.3, 39.4**

  - [ ] 10.3 Implement RBAC domain logic
    - Create `src/portal/domain/rbac.py` — 6 default roles, custom roles, permission enforcement
    - _Requirements: 36.1-36.8, 11.3, 11.4_

  - [ ]* 10.4 Write property test for RBAC enforcement
    - **Property 22: RBAC permission enforcement**
    - **Validates: Requirements 11.3, 11.4, 36.3-36.5, 44.5**

  - [ ] 10.5 Implement Rate Limiter with sliding window
    - Create `src/portal/middleware/rate_limiter.py`
    - Magic Link 3/15min, exceptions 10/day, global 100/min per IP
    - _Requirements: 23.1-23.7_

  - [ ]* 10.6 Write property test for rate limiter
    - **Property 23: Rate limiter enforcement**
    - **Validates: Requirements 23.1-23.6**

- [ ] 11. Portal Domain — Reconciliation Engine and Work Schedules
  - [ ] 11.1 Implement Work Schedule domain logic
    - Create `src/portal/domain/work_schedule.py` — Standard/Split/Flexible/Custom patterns
    - Changes take effect next calendar day; default pattern per tenant
    - _Requirements: 55.1, 55.3, 55.4, 55.6, 55.7_

  - [ ] 11.2 Implement Reconciliation Engine
    - Create `src/portal/domain/reconciliation.py` with ReconciliationService
    - Variance: Manual - (Tracked + Approved Exceptions + Auto-Exempt), work-schedule-aware
    - Flags by threshold; drill-down daily breakdown; data incomplete indicator
    - _Requirements: 10.1-10.10, 34.6, 55.2, 55.3, 55.5_

  - [ ]* 11.3 Write property tests for reconciliation
    - **Property 18: Variance calculation and flag assignment**
    - **Property 39: Work-schedule-aware variance counting**
    - **Property 42: Drill-down daily breakdown aggregation consistency**
    - **Validates: Requirements 10.1-10.4, 10.9, 10.10, 34.6, 55.2, 55.3**

  - [ ] 11.4 Implement Location Mismatch detection
    - Flag if >50% entries conflict with declared location
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 11.5 Write property test for location mismatch
    - **Property 17: Location mismatch detection**
    - **Validates: Requirements 9.1, 9.2**

  - [ ] 11.6 Implement filtering, sorting, and pagination
    - Filter by name, period, flag color; sort by recent; paginate
    - _Requirements: 10.7_

  - [ ]* 11.7 Write property test for reconciliation filtering
    - **Property 21: Reconciliation report filtering and sorting**
    - **Validates: Requirements 10.7**

- [ ] 12. Portal Domain — Employee Wellness, Presence, and Transparency
  - [ ] 12.1 Implement Employee Wellness domain logic
    - Create `src/portal/domain/wellness.py` — self-correction notification at 75%, badge after N clean periods
    - Max one notification per period; private to employee; badge visible only to self
    - _Requirements: 53.1-53.7, 54.1-54.5_

  - [ ]* 12.2 Write property tests for wellness
    - **Property 37: Self-correction notification trigger and idempotency**
    - **Property 38: Positive reinforcement badge state**
    - **Validates: Requirements 53.1, 53.4, 53.7, 54.1-54.3**

  - [ ] 12.3 Implement Presence indicator logic
    - Create `src/portal/domain/presence.py` — Online if heartbeat within 10 min; ephemeral only
    - _Requirements: 52.1-52.5_

  - [ ]* 12.4 Write property test for presence indicator
    - **Property 36: Presence indicator computation**
    - **Validates: Requirements 52.1, 52.2**

  - [ ] 12.5 Implement Transparency Report generation
    - Create `src/portal/domain/transparency.py` — end-of-period report, 24h before HR review
    - _Requirements: 57.1-57.6_

  - [ ]* 12.6 Write property test for transparency report timing
    - **Property 41: Transparency report delivery timing**
    - **Validates: Requirements 57.1, 57.2**

- [ ] 13. Portal Domain — Reports, Audit, Incidents, and Lifecycle
  - [ ] 13.1 Implement Report generation (Template Method pattern)
    - Create `src/portal/domain/reports.py` with BaseReportGenerator ABC and concrete generators
    - Pipeline: authenticate, verify permission, query, filter, format, log
    - Daily/Weekly/Monthly reports; CSV streaming export
    - _Requirements: 37.1-37.6, 44.10_

  - [ ] 13.2 Implement Audit Log domain logic
    - Create `src/portal/domain/audit.py` — append-only, 365-day retention, searchable
    - _Requirements: 26.1-26.5_

  - [ ]* 13.3 Write property test for audit log
    - **Property 33: Audit log entry completeness**
    - **Validates: Requirements 26.1, 26.2, 26.3**

  - [ ] 13.4 Implement Incident Response domain logic
    - Create `src/portal/domain/incident.py` — auto-detect, classify severity, HR notification
    - _Requirements: 30.1-30.7_

  - [ ] 13.5 Implement Employee Lifecycle management
    - Create `src/portal/domain/employee.py` — add/edit/deactivate, installer generation
    - _Requirements: 32.1-32.10_

  - [ ] 13.6 Implement Configurable Parameters service
    - Create `src/portal/services/config_service.py` — CRUD with range validation, history
    - _Requirements: 22.1-22.7_

- [ ] 14. Portal — Cross-Cutting Concerns and Middleware
  - [ ] 14.1 Implement Circuit Breaker pattern
    - Create `src/portal/adapters/circuit_breaker.py`
    - Closed to Open (3 failures/60s) to Half-Open (30s); apply to all external services
    - _Requirements: 45.3, 45.4_

  - [ ]* 14.2 Write property tests for circuit breaker and retry
    - **Property 27: Circuit breaker state transitions**
    - **Property 28: Exponential backoff retry delays**
    - **Validates: Requirements 44.3, 44.7**

  - [ ] 14.3 Implement Decorator pattern for cross-cutting concerns
    - Create `src/portal/middleware/decorators.py` — auth, permission, audit, sanitize
    - _Requirements: 44.9, 45.5, 45.6_

  - [ ] 14.4 Implement Global Error Boundary and error categorization
    - Create `src/portal/middleware/error_handler.py` — catch all, log, friendly error page
    - _Requirements: 51.14, 51.15, 45.2_

  - [ ] 14.5 Implement In-Memory Cache adapter
    - Create `src/portal/adapters/memory_cache.py` — TTL-based, invalidate on writes
    - _Requirements: 24.1-24.5_

  - [ ] 14.6 Implement Emergency Kill Switch
    - Reject logins, terminate sessions, disable operations; reversible; env var support
    - _Requirements: 50.1-50.7_

- [ ] 15. Checkpoint — Portal Domain Logic Complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. Portal — Google Sheets Adapters and External Integrations
  - [ ] 16.1 Implement Google Sheets adapters for Portal
    - Create adapters in `src/portal/adapters/` for employee, clock, exception, activity, audit stores
    - 10s read / 15s write timeouts; retry once after 5s; max 5 concurrent
    - Cache worksheet references; reuse gspread client
    - _Requirements: 28.1, 28.2, 28.4, 28.5, 28.6, 48.1_

  - [ ] 16.2 Implement Gemini API adapter
    - Create `src/portal/adapters/gemini_classifier.py` — fixed prompt, input sandwiching, 5s timeout
    - _Requirements: 8.1, 39.1-39.7, 45.3_

  - [ ] 16.3 Implement Email adapter
    - Create `src/portal/adapters/smtp_email.py` — Magic Link, incidents, wellness, transparency
    - _Requirements: 5.1, 15.4, 30.2, 53.3, 57.5_

- [ ] 17. Portal — Domain Event Bus
  - [ ] 17.1 Implement internal domain event bus
    - Create event bus with publish/subscribe; define all domain events
    - Register handlers: AuditLogger, CacheInvalidator, IncidentNotifier, GeminiReclassifier
    - _Requirements: 44.3, 15.6_

- [ ] 18. Portal — Rhythm Visual Design System
  - [ ] 18.1 Create RhythmTheme class for Gradio
    - Create `src/portal/theme/rhythm_theme.py` with custom Gradio Theme subclass
    - Primary color: sage green (#5B8C5A), secondary: warm amber (#E8A838)
    - Background: soft off-white (#FAFAF7), text: charcoal (#2D3436), accent: coral (#E17055)
    - Set border-radius to 8px globally; configure Inter/Nunito font stack
    - Ensure all color combinations meet WCAG 2.0 AA contrast ratios
    - _Requirements: 59.1, 59.2, 59.3, 59.4, 59.5_

  - [ ] 18.2 Create rhythm.css with design tokens and micro-animations
    - Create `src/portal/static/rhythm.css` with CSS custom properties on 8px grid
    - Define border-radius (8px), spacing scale (8/16/24/32/40/48px)
    - Implement micro-animations: fade-in, slide-up, pulse (max 300ms duration each)
    - Add `prefers-reduced-motion: reduce` override disabling all animations
    - Add `prefers-contrast: more` high-contrast overrides (bolder borders, no gradients)
    - Implement focus indicators: 2px solid outline with 3:1 contrast ratio minimum
    - Set touch targets to minimum 44x44px on mobile viewports
    - _Requirements: 59.6, 59.7, 59.8, 59.9, 59.10, 62.3_

  - [ ] 18.3 Design and implement Rhythm logo assets
    - Create abstract pulse/wave SVG mark that renders cleanly at 24px and 48px
    - Export as SVG with viewBox for scalability; place in `src/portal/static/`
    - Integrate logo into Portal header and loading screen
    - _Requirements: 59.11, 59.12_

  - [ ] 18.4 Implement personalized greetings and branded loading screen
    - Add personalized greeting display: "Welcome back, {first_name}" on employee portal
    - Create branded loading screen for HF Spaces cold start (logo + subtle animation)
    - Ensure loading screen respects prefers-reduced-motion
    - _Requirements: 59.13, 59.14, 60.1_

- [ ] 19. Portal — Copywriting Architecture
  - [ ] 19.1 Create CopyManager class and copy directory structure
    - Create `src/portal/copy/__init__.py` with CopyManager class (loads YAML, renders templates with context)
    - Support string interpolation for dynamic values (name, dates, counts)
    - Implement fallback to key name if copy key not found
    - _Requirements: 60.2, 60.3, 60.4_

  - [ ] 19.2 Create en.copy.yaml with all message templates
    - Create `src/portal/copy/en.copy.yaml` with categories: greetings, errors, warnings, empty_states, notifications, privacy, hr_neutral
    - All messages use warm, HR-neutral tone (supportive, not surveillance)
    - Include placeholder tokens for dynamic content
    - _Requirements: 60.5, 60.6, 60.7_

  - [ ] 19.3 Create tone_guidelines.md documentation
    - Create `src/portal/copy/tone_guidelines.md` with editorial voice rules
    - Document: supportive not punitive, wellness not surveillance, plain language, inclusive
    - _Requirements: 60.8_

  - [ ] 19.4 Refactor all view files to use CopyManager
    - Update `employee_portal.py`, `hr_dashboard.py`, `report_views.py`, `admin_settings.py`
    - Replace all hardcoded user-facing strings with CopyManager lookups
    - Verify no hardcoded strings remain in view layer (excluding technical labels)
    - _Requirements: 60.9, 60.10_

  - [ ]* 19.5 Write property tests for design system and copy architecture
    - **Property 43: Personalized greeting rendering** — verify greeting contains first_name for any non-empty name
    - **Property 44: Animation duration bounds** — verify all CSS animations <= 300ms
    - **Property 45: Externalized copy completeness** — verify every copy key in views resolves to non-empty string
    - **Validates: Requirements 59.13, 59.8, 60.9, 60.10**

- [ ] 20. Portal — Gradio UI Views
  - [ ] 20.1 Implement Employee Portal Gradio UI
    - Create `src/portal/views/employee_portal.py` — thin adapter calling domain services
    - Login, Clock-In/Out, My Timesheet, Exception_Form, work schedule, badge display
    - Apply RhythmTheme; use CopyManager for all user-facing strings
    - _Requirements: 6.1, 33.1-33.8, 7.6, 7.9, 8.8, 54.1, 54.4, 55.4, 59.1, 60.9_

  - [ ] 20.2 Implement HR Dashboard Gradio UI
    - Create `src/portal/views/hr_dashboard.py` — reconciliation, presence dots, approvals, employee management, incidents, audit viewer, config
    - Apply RhythmTheme; use CopyManager for all user-facing strings
    - _Requirements: 4.7, 9.3, 10.2-10.9, 14.6, 18.3, 30.3, 30.7, 32.1-32.9, 34.2-34.5, 52.1, 59.1, 60.9_

  - [ ] 20.3 Implement Report Views and Admin Settings
    - Create `src/portal/views/report_views.py` and `admin_settings.py`
    - CSV export; kill switch; RBAC config; surveillance notices; policy templates
    - Apply RhythmTheme; use CopyManager for all user-facing strings
    - _Requirements: 37.1-37.6, 22.2, 36.2, 29.4, 31.4, 50.1, 59.1, 60.9_

  - [ ] 20.4 Implement Portal entry point with DI wiring
    - Create `src/portal/main.py` — composition root, Gradio app config, env var loading
    - Wire RhythmTheme and rhythm.css into Gradio app initialization
    - _Requirements: 46.7, 47.2, 49.3, 49.5, 59.1_

- [ ] 21. Portal — Accessibility, i18n, White-Label, and Privacy
  - [ ] 21.1 Implement WCAG 2.0 AA accessibility
    - ARIA roles/names/states; keyboard nav; contrast ratios; responsive layout; error linking
    - _Requirements: 12.1-12.5_

  - [ ] 21.2 Implement Multi-Language support
    - Locale resource files (8 languages); browser detection; RTL for Arabic
    - _Requirements: 20.1-20.8_

  - [ ] 21.3 Implement White-Label branding
    - Tenant branding config (logo, name, colors); default fallback to Rhythm theme
    - _Requirements: 19.1-19.7_

  - [ ] 21.4 Implement Privacy and Surveillance compliance
    - Privacy notice, surveillance notice (14-day period), "My Data" page, data retention
    - _Requirements: 27.1-27.6, 29.1-29.8_

  - [ ] 21.5 Implement Multi-Timezone support
    - UTC storage; display in configured timezone; auto-close on employee TZ
    - _Requirements: 21.1-21.7_

  - [ ]* 21.6 Write property test for timezone conversion
    - **Property 32: Timezone display conversion**
    - **Validates: Requirements 21.1, 21.2, 21.4, 21.5**

- [ ] 22. Portal — Enhanced Accessibility Verification
  - [ ] 22.1 Integrate axe-core in Playwright E2E suite
    - Install axe-core-python and configure as Playwright fixture
    - Create CI gate: critical and serious axe violations block merge
    - Add axe scan to every E2E test page load
    - _Requirements: 62.1, 62.2_

  - [ ] 22.2 Implement ARIA live regions for dynamic content
    - Add `aria-live="polite"` for non-urgent updates (status changes, data loading)
    - Add `aria-live="assertive"` for critical alerts (errors, session expiry warnings)
    - Ensure all Gradio dynamic content updates announce via live regions
    - _Requirements: 62.3, 62.4_

  - [ ] 22.3 Implement high-contrast mode and focus management
    - Detect `prefers-contrast: more` and apply high-contrast CSS overrides
    - Implement skip-nav link as first focusable element on every page
    - Implement focus trap for modal dialogs (tab cycles within modal)
    - _Requirements: 62.5, 62.6, 62.7_

  - [ ] 22.4 Ensure color independence for all coded elements
    - Add secondary indicators (icons + text labels) alongside all color-coded elements
    - Variance flags: RED + warning icon + "Potential padding" text
    - GREEN + checkmark icon + "Within threshold" text
    - AMBER + alert icon + "Unclaimed hours" text
    - Presence dots: green dot + "Online" text, grey dot + "Offline" text
    - _Requirements: 62.8, 62.9_

  - [ ] 22.5 Create ACCESSIBILITY.md documentation
    - Create `docs/ACCESSIBILITY.md` with WCAG 2.0 AA conformance statement
    - Document: testing methodology, known limitations, assistive tech tested
    - List all ARIA patterns used, keyboard shortcuts, and focus management
    - _Requirements: 62.10_

  - [ ]* 22.6 Write property tests for accessibility invariants
    - **Property 48: ARIA live regions** — verify every dynamic content update has a corresponding aria-live region
    - **Property 49: Color independence** — verify every color-coded element has a non-color secondary indicator
    - **Validates: Requirements 62.3, 62.4, 62.8, 62.9**

- [ ] 23. Portal — UX, Error Handling, and Optimistic UI
  - [ ] 23.1 Implement UX standards
    - 3-click clock-in; plain language errors; visual confirmation; contextual help
    - _Requirements: 41.1-41.8_

  - [ ] 23.2 Implement Optimistic UI and offline resilience
    - Queue on failure; sync indicators; offline detection; form preservation on session expiry
    - _Requirements: 51.1-51.11_

  - [ ] 23.3 Implement HR Administrator self-logging
    - Same controls as employees; subject to variance; cannot self-approve
    - _Requirements: 35.1-35.8_

  - [ ] 23.4 Implement Heartbeat offline detection
    - "Tracker Offline" if last heartbeat > 60 minutes
    - _Requirements: 18.3_

  - [ ]* 23.5 Write property test for heartbeat offline
    - **Property 26: Heartbeat offline detection threshold**
    - **Validates: Requirements 18.3**

- [ ] 24. Checkpoint — Portal UI and Features Complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 25. Test Data Seeding Infrastructure
  - [ ] 25.1 Create seed_data.py CLI entry point
    - Create `scripts/seed_data.py` with argparse CLI accepting --tenant-id, --fixtures-only, --seed params
    - Implement deterministic random via --seed for reproducible test data
    - Wire persona generation, activity/clock/exception/audit generators
    - _Requirements: 61.1, 61.2, 61.3_

  - [ ] 25.2 Implement persona definitions
    - Create `scripts/seed/personas.py` with 10 employee persona definitions
    - Each persona: name, role, work pattern, typical behavior profile (punctual, variable, remote-heavy, etc.)
    - Include at least 1 HR admin, 1 manager, and 8 employees with varying patterns
    - _Requirements: 61.4, 61.5_

  - [ ] 25.3 Implement activity and clock generators
    - Create `scripts/seed/activity_generator.py` — generate 4 weeks of 5-min activity entries per persona
    - Create `scripts/seed/clock_generator.py` — generate matching clock-in/out entries aligned to persona work patterns
    - Introduce realistic variance: occasional late starts, early finishes, idle periods
    - _Requirements: 61.6, 61.7_

  - [ ] 25.4 Implement exception and audit generators
    - Create `scripts/seed/exception_generator.py` — generate exceptions matching idle gaps in activity data
    - Create `scripts/seed/audit_generator.py` — generate realistic admin actions (approvals, config changes, employee additions)
    - Ensure exceptions reference valid time ranges within generated activity data
    - _Requirements: 61.8, 61.9_

  - [ ] 25.5 Implement fixture exporter
    - Create `scripts/seed/fixture_exporter.py` — export generated data as JSON to `tests/fixtures/`
    - One JSON file per data type: activities.json, clocks.json, exceptions.json, audit.json, employees.json
    - Ensure fixtures are loadable by test harness without external dependencies
    - _Requirements: 61.10, 61.11_

  - [ ]* 25.6 Write property tests for seed data integrity
    - **Property 46: Seed data idempotency** — verify same seed produces identical output across runs
    - **Property 47: Temporal coverage** — verify generated data covers all working days in 4-week span with no gaps
    - **Validates: Requirements 61.2, 61.6, 61.7**

- [ ] 26. Security, Architecture Tests, and Documentation
  - [ ] 26.1 Implement security test suite
    - Prompt injection, command injection, RBAC bypass, rate limiting, audit immutability tests
    - _Requirements: 39.8, 25.1-25.4, 16.1-16.6, 23.1-23.7, 26.3_

  - [ ] 26.2 Implement architecture boundary tests (import-linter)
    - Domain cannot import adapters; tracker/portal isolated; shared independent
    - _Requirements: 44.7_

  - [ ] 26.3 Create STRIDE threat model document
    - All 6 threat categories with mitigations mapped to requirements
    - _Requirements: 44.8_

  - [ ] 26.4 Create policy template documents
    - InfoSec Policy, Acceptable Use Policy, Data Retention Policy
    - _Requirements: 31.1-31.5_

  - [ ] 26.5 Create configuration reference document
    - Every configurable value documented with name, type, default, range
    - _Requirements: 49.6_

- [ ] 27. CI/CD Pipeline and Build Configuration
  - [ ] 27.1 Configure GitHub Actions CI pipeline
    - Lint, type check, unit/property tests, architecture tests, Snyk scans
    - Include axe-core accessibility gate in E2E test stage
    - _Requirements: 17.1-17.7, 42.5, 43.6, 46.8, 62.1_

  - [ ] 27.2 Configure OWASP ZAP DAST scanning
    - Baseline scan on staging; block HIGH/CRITICAL; rules file in repo
    - _Requirements: 42.1-42.6_

  - [ ] 27.3 Configure PyInstaller build artifacts in CI
    - Windows .exe and macOS .app; GitHub Release with changelog; signing
    - _Requirements: 13.1, 43.1-43.6_

  - [ ] 27.4 Configure Hugging Face Spaces deployment
    - Docker deploy to HF Spaces; staging for E2E before production
    - _Requirements: 43.3_

- [ ] 28. Integration and E2E Tests
  - [ ]* 28.1 Write integration tests for external services
    - Google Sheets, Gemini, Email, NTP, SQLite scenarios
    - _Requirements: 28.1-28.6, 8.1-8.7, 5.1, 14.1_

  - [ ]* 28.2 Write Playwright E2E tests
    - Full user flows: login, clock, exceptions, reconciliation, lifecycle, wellness, transparency
    - _Requirements: 6.1-6.8, 32.1-32.10, 33.1-33.8, 35.1-35.8, 55.4, 53.1, 54.1, 57.1, 52.1, 56.1_

  - [ ]* 28.3 Write E2E accessibility test flows
    - Keyboard-only navigation flow (complete clock-in/out without mouse)
    - Screen reader announcement verification (ARIA live regions)
    - axe-core full scan on all primary views (employee portal, HR dashboard, reports)
    - Tab order verification across all forms
    - Focus trap verification for all modal dialogs
    - High-contrast mode visual regression
    - Skip-nav link functionality verification
    - _Requirements: 62.1, 62.3, 62.5, 62.6, 62.7, 12.1, 12.2_

- [ ] 29. Final Checkpoint — Full System Integration
  - Ensure all tests pass, ask the user if questions arise.


## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at Tracker, Portal, and system level
- Property tests validate 49 correctness properties from the design document
- The system uses Python with pytest, Hypothesis, Pydantic, asyncio, PyInstaller
- Hexagonal architecture enforced by import-linter; domain has zero external deps
- All services use constructor injection for testability
- Google Sheets as Central Store with architecture supporting future PostgreSQL swap
- Rhythm Visual Design System (Task 18) establishes branding before UI views are built
- Copywriting Architecture (Task 19) externalizes all user-facing strings for consistency and i18n
- Test Data Seeding (Task 25) provides reproducible fixtures for offline testing
- Enhanced Accessibility (Task 22) integrates axe-core into CI with blocking gates

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "8.1"] },
    { "id": 4, "tasks": ["2.3", "2.5", "3.1", "8.2"] },
    { "id": 5, "tasks": ["2.4", "2.6", "2.7", "3.2", "3.3", "8.3"] },
    { "id": 6, "tasks": ["3.4", "4.1", "4.5", "8.4", "9.1", "10.3"] },
    { "id": 7, "tasks": ["4.2", "4.3", "4.6", "9.2", "9.3", "10.5"] },
    { "id": 8, "tasks": ["4.4", "5.1", "5.3", "9.4", "10.1", "10.4", "10.6"] },
    { "id": 9, "tasks": ["5.2", "5.4", "5.5", "5.6", "10.2", "11.1"] },
    { "id": 10, "tasks": ["5.7", "6.1", "6.4", "11.2", "11.4"] },
    { "id": 11, "tasks": ["6.2", "6.3", "11.3", "11.5", "11.6"] },
    { "id": 12, "tasks": ["6.5", "11.7", "12.1", "12.3", "12.5"] },
    { "id": 13, "tasks": ["12.2", "12.4", "12.6", "13.1", "13.2", "13.4", "13.5"] },
    { "id": 14, "tasks": ["13.3", "13.6", "14.1", "14.3", "14.4", "14.5"] },
    { "id": 15, "tasks": ["14.2", "14.6", "16.1", "16.2", "16.3"] },
    { "id": 16, "tasks": ["17.1", "18.1", "18.2"] },
    { "id": 17, "tasks": ["18.3", "18.4", "19.1"] },
    { "id": 18, "tasks": ["19.2", "19.3", "20.1", "20.2"] },
    { "id": 19, "tasks": ["19.4", "19.5", "20.3", "20.4"] },
    { "id": 20, "tasks": ["21.1", "21.2", "21.3", "22.1", "22.2"] },
    { "id": 21, "tasks": ["21.4", "21.5", "22.3", "22.4"] },
    { "id": 22, "tasks": ["21.6", "22.5", "22.6", "23.1", "23.2"] },
    { "id": 23, "tasks": ["23.3", "23.4", "23.5", "25.1"] },
    { "id": 24, "tasks": ["25.2", "25.3"] },
    { "id": 25, "tasks": ["25.4", "25.5"] },
    { "id": 26, "tasks": ["25.6", "26.1", "26.2", "26.3", "26.4", "26.5"] },
    { "id": 27, "tasks": ["27.1", "27.2", "27.3", "27.4"] },
    { "id": 28, "tasks": ["28.1", "28.2", "28.3"] }
  ]
}
```
