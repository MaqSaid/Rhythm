# Design Document: Fraud-Proof Hybrid Timesheet

## Overview

The Fraud-Proof Hybrid Timesheet system is a modular monolith architecture comprising two independently deployable units — a silent desktop **Tracker** and a web **Portal** — connected through a shared **Central Store** (Google Sheets). The system compares manual employee time claims against automatically captured hardware-level activity data to surface discrepancies for HR review on a configurable periodic basis (weekly/fortnightly/monthly).

The system is designed with an employee-first philosophy: idle gaps under 30 minutes are auto-exempt (no notification), exception reporting is a one-click desktop toast (not a form), employees receive their own transparency report 24 hours before HR reviews go live, self-correction notifications allow fixing variances before flags appear, and a "Great Standing" badge rewards consistent timekeeping. Focus Mode lets employees suppress notifications during deep work without affecting tracking. Only binary active/idle status is stored — no app names, window titles, or URLs are ever recorded or exposed to HR.

HR administrators use the same clock-in/out system as employees (with self-approval restrictions), can see a simple online/offline presence indicator (ephemeral, not stored), and review variance data aggregated per configurable review period — single bad days never trigger flags on their own.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Modular Monolith** (NOT microservices) | Simplicity for a small team; two deployable units sufficient |
| **Hexagonal Architecture** (Ports & Adapters) | Decouples domain from infrastructure; testability |
| **DDD Bounded Contexts** | Clear ownership; parallel development; no coupling |
| **Offline-first Tracker** with SQLite + nightly sync | No data loss without internet |
| **SHA-256 Hash Chain** | Cryptographic tamper proof without external services |
| **Passwordless Magic Links** | No password management; leverages corporate email |
| **AI tagging** (Gemini 2.0 Flash) | Faster HR review; graceful fallback |
| **Google Sheets as Central Store** | Free tier; familiar to HR; initial scale |
| **Repository Pattern** | Enables backend swap without domain changes |
| **Strategy Pattern** for OS operations | Isolates Windows vs macOS specifics |
| **Circuit Breaker** for external calls | Prevents cascade failures |
| **Decorator Pattern** for cross-cutting concerns | Consistent auth/audit/logging |
| **Template Method** for reports | Enforced security pipeline per report |
| **Toast Notification** (not form) for exception reporting | One-click workflow; zero friction for short breaks |
| **Auto-Exempt Threshold** (≤30 min idle) | Prevents notification fatigue for short breaks |
| **Periodic Variance** (review period, not daily) | Prevents micro-management; catches sustained patterns only |
| **Ephemeral Presence Indicator** (not stored) | Communication utility without surveillance creep |
| **Employee Transparency Report** (24h before HR) | No surprises; builds trust; allows self-correction |
| **Focus Mode** (private, not reported) | Respects deep work; notifications are productivity-aware |
| **Work Schedule Patterns** (Standard/Split/Flexible/Custom) | Supports diverse work arrangements without false flags |
| **Positive Reinforcement** (badge, not leaderboard) | Encourages without creating competition or pressure |

### High-Level System Diagram

```mermaid
graph TD
    subgraph "Employee Laptop (Tracker)"
        AM[Activity Monitor]
        LD[Location Detector]
        HC[Hash Chain Manager]
        LDB[(SQLite Local_DB<br/>WAL mode)]
        SE[Sync Engine]
        NTP[NTP Validator]
        SL[Structured Logger]
        TN[Toast Notification<br/>Idle Return + Categories]
        FM[Focus Mode<br/>System Tray Toggle]
        AM --> LDB
        LD --> LDB
        HC --> LDB
        SE --> LDB
        NTP --> SE
        SL --> LDB
        AM -->|idle return| TN
        FM -->|suppresses| TN
        TN -->|quick exception| LDB
    end

    subgraph "Hugging Face Spaces (Portal)"
        AUTH[Auth Module<br/>Magic Links]
        EP[Employee Portal<br/>Clock/Exception/Wellness]
        HD[HR Dashboard<br/>Reconciliation + Presence]
        RE[Reconciliation Engine<br/>Per Review Period]
        GT[Gemini Tagger]
        RBAC[RBAC Engine]
        IV[Input Validator]
        CB[Circuit Breaker]
        WS[Work Schedule]
        WE[Wellness Engine<br/>Self-Correction + Badge]
        TR[Transparency Reports]
        EP --> RE
        HD --> RE
        EP --> GT
        AUTH --> RBAC
        EP --> IV
        HD --> IV
        CB --> GT
        CB --> AUTH
        RE --> WS
        WE --> RE
        TR --> RE
    end

    subgraph "External Services"
        CS[(Google Sheets<br/>Central Store)]
        GEM[Gemini 2.0 Flash API]
        SMTP[Email Service]
        NTPS[time.google.com]
    end

    SE -->|"Nightly Sync + Heartbeat"| CS
    NTP -->|"NTP Query (UDP 123)"| NTPS
    EP -->|"Read/Write"| CS
    HD -->|"Read"| CS
    GT -->|"Classify"| GEM
    AUTH -->|"Send Magic Link"| SMTP
    WE -->|"Self-Correction Notification"| SMTP
    TR -->|"Transparency Report"| SMTP
```
## Architecture

### Hexagonal Architecture (Ports and Adapters)

Each deployable unit follows hexagonal architecture with three layers:

```mermaid
graph LR
    subgraph "Domain Layer (Pure Logic)"
        D1[Entities and Value Objects]
        D2[Domain Services]
        D3[Port Interfaces]
    end
    subgraph "Application Layer"
        A1[Use Cases / Service Classes]
        A2[Orchestration]
    end
    subgraph "Adapter Layer (Infrastructure)"
        I1[Google Sheets Adapter]
        I2[SQLite Adapter]
        I3[Gemini API Adapter]
        I4[Email Adapter]
        I5[WiFi Detection Adapter]
        I6[NTP Adapter]
        I7[Gradio UI Adapter]
    end
    I7 --> A1
    A1 --> D2
    D2 --> D3
    D3 -.->|implements| I1
    D3 -.->|implements| I2
    D3 -.->|implements| I3
    D3 -.->|implements| I4
    D3 -.->|implements| I5
    D3 -.->|implements| I6
```

**Layer Rules (enforced by import-linter):**
- Domain layer: ZERO imports from adapter or application layers
- Application layer: imports from domain only (ports/interfaces)
- Adapter layer: imports from domain ports; implements interfaces
- No circular dependencies between bounded contexts

### DDD Bounded Context Map

```mermaid
graph TD
    subgraph "Tracker Domain"
        TA[Activity Context]
        TL[Location Context]
        TS[Sync Context]
        TI[Integrity Context]
        TN[Notification Context<br/>Toast + Focus Mode]
    end
    subgraph "Portal Domain"
        PA[Authentication Context]
        PC[Clock Context]
        PE[Exception Context]
        PR[Reconciliation Context]
        PP[Reports Context]
        PB[RBAC Context]
        PL[Employee Lifecycle Context]
        PS[Presence Context]
        PW[Work Schedule Context]
        PX[Employee Wellness Context]
    end
    subgraph "Shared Kernel"
        SK1[Employee Value Object]
        SK2[Tenant Config]
        SK3[Timestamp Utilities]
        SK4[Enums - Status, Location, Flags]
        SK5[Work Schedule Definitions]
    end
    TS -->|reads| TA
    TS -->|reads| TL
    TI -->|verifies| TA
    TN -->|triggered by| TA
    PR -->|reads| PC
    PR -->|reads| PE
    PR -->|reads| PW
    PP -->|reads| PR
    PX -->|reads| PR
    PS -->|reads heartbeats| TS
    PA --> PB
    PC --> PA
    PE --> PA
    PL --> PA
    TA -.-> SK1
    TL -.-> SK1
    PA -.-> SK1
    PC -.-> SK1
    PR -.-> SK3
    TS -.-> SK3
    PW -.-> SK5
    PR -.-> SK5
```

**Bounded Context Responsibilities:**

| Context | Owner | Responsibility |
|---------|-------|---------------|
| Activity | Tracker | Monitor input events, determine Online/Idle status |
| Location | Tracker | Detect WiFi, match against office networks |
| Sync | Tracker | Queue management, nightly push, heartbeat |
| Integrity | Tracker | Hash chain computation and verification |
| Notification | Tracker | Toast notifications for idle return (> Auto_Exempt_Threshold), focus mode suppression |
| Authentication | Portal | Magic Links, sessions, token validation |
| Clock | Portal | Clock-in/out, auto-close, session state |
| Exception | Portal | Quick toast exceptions + detailed Exception_Form, AI tagging, approval workflow |
| Reconciliation | Portal | Periodic variance calculation (per configurable review period), location mismatch detection |
| Reports | Portal | Template Method report generation, CSV export, Employee Transparency Reports |
| RBAC | Portal | Roles, permissions, access enforcement |
| Employee Lifecycle | Portal | Add/edit/deactivate employees, installer generation |
| Presence | Portal | Real-time online/offline indicator for HR (ephemeral, not stored/logged) |
| Work Schedule | Portal | Flexible work pattern management (Standard/Split/Flexible/Custom) |
| Employee Wellness | Portal | Self-correction notifications, positive reinforcement badges |


### Design Patterns Applied

#### Strategy Pattern (OS-Specific Operations)

```python
# Port interface
class WifiDetectionPort(Protocol):
    def get_current_network(self) -> Optional[WifiInfo]: ...

# Windows adapter
class WindowsWifiDetector:
    """Uses 'netsh wlan show interfaces' via subprocess with arg array."""
    def get_current_network(self) -> Optional[WifiInfo]: ...

# macOS adapter
class MacOSWifiDetector:
    """Uses system_profiler SPAirPortDataType or CoreWLAN via objc bridge."""
    def get_current_network(self) -> Optional[WifiInfo]: ...

# Factory selects strategy at startup
def create_wifi_detector() -> WifiDetectionPort:
    if platform.system() == "Windows":
        return WindowsWifiDetector()
    elif platform.system() == "Darwin":
        return MacOSWifiDetector()
```

#### Circuit Breaker Pattern (External Service Calls)

```python
class CircuitBreaker:
    """States: Closed -> Open (after 3 failures in 60s) -> Half-Open (after 30s)."""
    
    def __init__(self, service_name: str, failure_threshold: int = 3,
                 recovery_timeout: int = 30, window: int = 60):
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: Optional[datetime] = None
    
    def call(self, operation: Callable[..., T], *args) -> T:
        """Execute operation through circuit breaker logic."""
    
    def _on_failure(self) -> None:
        """Increment failure count; open circuit if threshold reached."""
    
    def _on_success(self) -> None:
        """Reset failure count; close circuit if half-open."""
```

Applied to: Google Sheets API, Gemini API, NTP service, Email service.

#### Decorator Pattern (Cross-Cutting Concerns)

```python
# Authentication decorator
def require_auth(func):
    """Verify session is valid before executing service method."""

# Authorization decorator  
def require_permission(permission: Permission):
    """Verify user role has required permission."""

# Audit logging decorator
def audit_log(action_type: str):
    """Record action in append-only audit log after execution."""

# Input sanitization decorator
def sanitize_inputs(func):
    """Validate and sanitize all Pydantic model inputs."""
```

#### Template Method Pattern (Reports)

```python
class BaseReportGenerator(ABC):
    """Common pipeline for all reports."""
    
    def generate(self, request: ReportRequest) -> ReportResult:
        self._authenticate(request.session)      # Step 1
        self._verify_permission(request.role)     # Step 2
        data = self._query_data(request.filters)  # Step 3 (abstract)
        filtered = self._apply_filters(data)      # Step 4
        output = self._format_output(filtered)    # Step 5 (abstract)
        self._log_access(request)                 # Step 6
        return output
    
    @abstractmethod
    def _query_data(self, filters: ReportFilters) -> list: ...
    
    @abstractmethod
    def _format_output(self, data: list) -> ReportResult: ...
```


### Deployment Topology

```mermaid
graph TD
    subgraph "Employee Devices"
        W1[Windows Laptop<br/>Tracker.exe<br/>Windows Service]
        M1[macOS Laptop<br/>Tracker.app<br/>LaunchDaemon]
    end
    subgraph "Cloud - Hugging Face Spaces"
        HF[Gradio Portal<br/>Docker Container<br/>Free Tier]
    end
    subgraph "Google Cloud"
        GS[(Google Sheets API<br/>Central Store)]
        GM[Gemini 2.0 Flash API]
    end
    subgraph "Email Provider"
        EM[SMTP Service]
    end
    subgraph "CI/CD - GitHub"
        GA[GitHub Actions]
        GR[GitHub Releases<br/>.exe + .app artifacts]
    end
    W1 -->|gspread HTTPS| GS
    M1 -->|gspread HTTPS| GS
    HF -->|gspread HTTPS| GS
    HF -->|REST HTTPS| GM
    HF -->|SMTP/API| EM
    GA -->|Deploy| HF
    GA -->|Build artifacts| GR
```

### macOS-Specific Design Considerations

| Concern | Solution |
|---------|----------|
| Accessibility permission (pynput) | Installer prompts for Input Monitoring permission via tccutil or MDM profile |
| `airport` command deprecated | Use `system_profiler SPAirPortDataType` as primary; fallback to CoreWLAN via pyobjc bridge |
| Code signing + notarization | PyInstaller output signed with Developer ID; `codesign` + `notarytool` in CI |
| LaunchDaemon .plist | Installed to `/Library/LaunchDaemons/com.rhythm.tracker.plist` with `RunAtLoad=true` |
| Protected config path | `/Library/Application Support/Tracker/config.json` (root-owned, 600 permissions) |
| Sleep/wake resilience | LaunchDaemon persists across sleep; `IOPMNotification` to detect wake events |

**LaunchDaemon plist structure:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rhythm.tracker</string>
    <key>ProgramArguments</key>
    <array><string>/Library/Application Support/Tracker/tracker</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key>
    <string>/Library/Logs/Tracker/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Library/Logs/Tracker/stderr.log</string>
</dict>
</plist>
```


### Project Directory Structure

```
src/
├── tracker/
│   ├── domain/
│   │   ├── activity.py          # ActivityMonitor domain logic
│   │   ├── location.py          # Location determination logic
│   │   ├── sync.py              # Sync queue management
│   │   ├── integrity.py         # Hash chain computation/verification
│   │   ├── notification.py      # Toast notification logic + auto-exempt threshold
│   │   ├── focus_mode.py        # Focus mode timer and suppression logic
│   │   ├── models.py            # LogEntry, WifiInfo, SyncBatch, QuickException dataclasses
│   │   └── enums.py             # Status, Location enums
│   ├── ports/
│   │   ├── input_monitor.py     # ActivityMonitorPort (Protocol)
│   │   ├── wifi_detector.py     # WifiDetectionPort (Protocol)
│   │   ├── local_storage.py     # LocalStoragePort (Protocol)
│   │   ├── remote_store.py      # RemoteStorePort (Protocol)
│   │   ├── time_service.py      # TimeServicePort (Protocol)
│   │   ├── notification.py      # ToastNotificationPort (Protocol)
│   │   └── logger.py            # StructuredLoggerPort (Protocol)
│   ├── adapters/
│   │   ├── pynput_monitor.py    # pynput-based activity detection
│   │   ├── windows_wifi.py      # netsh wlan adapter
│   │   ├── macos_wifi.py        # system_profiler / CoreWLAN adapter
│   │   ├── sqlite_storage.py    # SQLite WAL mode adapter
│   │   ├── sheets_remote.py     # gspread Google Sheets adapter
│   │   ├── ntp_time.py          # NTP UDP query adapter
│   │   ├── toast_notification.py # OS-native toast notification adapter
│   │   ├── system_tray.py       # System tray icon + Focus Mode toggle adapter
│   │   └── json_logger.py       # Structured JSON file logger
│   ├── services/
│   │   ├── tracker_service.py   # Main orchestrator (5-min loop)
│   │   ├── sync_service.py      # Nightly sync + heartbeat
│   │   ├── notification_service.py # Idle return toast + auto-exempt logic
│   │   ├── focus_mode_service.py   # Focus mode timer management
│   │   └── startup_service.py   # Service registration, chain verify
│   └── main.py                  # Entry point, DI wiring
├── portal/
│   ├── domain/
│   │   ├── auth.py              # Session, MagicLink logic
│   │   ├── clock.py             # Clock-in/out, auto-close logic
│   │   ├── exception.py         # Exception submission (quick + detailed), approval
│   │   ├── reconciliation.py    # Periodic variance calc (per review period), location mismatch
│   │   ├── reports.py           # Report generators (Template Method)
│   │   ├── transparency.py      # Employee Transparency Report generation
│   │   ├── rbac.py              # Roles, permissions, enforcement
│   │   ├── employee.py          # Employee lifecycle (add/edit/deactivate)
│   │   ├── work_schedule.py     # Flexible work pattern definitions + validation
│   │   ├── presence.py          # Ephemeral online/offline presence logic
│   │   ├── wellness.py          # Self-correction notifications + positive reinforcement
│   │   ├── incident.py          # Security incident management
│   │   ├── models.py            # All Pydantic models
│   │   └── enums.py             # Roles, Permissions, FlagColor, WorkPatternType enums
│   ├── ports/
│   │   ├── employee_store.py    # EmployeeStorePort (Protocol)
│   │   ├── clock_store.py       # ClockStorePort (Protocol)
│   │   ├── exception_store.py   # ExceptionStorePort (Protocol)
│   │   ├── activity_store.py    # ActivityStorePort (read tracker data)
│   │   ├── audit_store.py       # AuditStorePort (Protocol)
│   │   ├── ai_classifier.py     # AIClassifierPort (Protocol)
│   │   ├── email_sender.py      # EmailSenderPort (Protocol)
│   │   ├── notification.py      # EmployeeNotificationPort (Protocol)
│   │   ├── config_store.py      # ConfigStorePort (Protocol)
│   │   └── cache.py             # CachePort (Protocol)
│   ├── adapters/
│   │   ├── sheets_employee.py   # Google Sheets employee adapter
│   │   ├── sheets_clock.py      # Google Sheets clock adapter
│   │   ├── sheets_exception.py  # Google Sheets exception adapter
│   │   ├── sheets_activity.py   # Google Sheets activity read adapter
│   │   ├── sheets_audit.py      # Google Sheets audit log adapter
│   │   ├── gemini_classifier.py # Gemini 2.0 Flash adapter
│   │   ├── smtp_email.py        # Email delivery adapter
│   │   ├── memory_cache.py      # In-memory TTL cache adapter
│   │   └── circuit_breaker.py   # Circuit breaker wrapper
│   ├── services/
│   │   ├── auth_service.py      # Login, session management
│   │   ├── clock_service.py     # Clock-in/out orchestration
│   │   ├── exception_service.py # Exception submission + tagging
│   │   ├── reconciliation_service.py  # Periodic variance calculation
│   │   ├── report_service.py    # Report generation orchestration
│   │   ├── transparency_service.py   # Employee Transparency Report delivery
│   │   ├── employee_service.py  # Employee CRUD
│   │   ├── rbac_service.py      # Permission checks
│   │   ├── presence_service.py  # Ephemeral presence indicator computation
│   │   ├── work_schedule_service.py  # Work schedule CRUD + validation
│   │   ├── wellness_service.py  # Self-correction + positive reinforcement
│   │   ├── incident_service.py  # Incident detection + notification
│   │   └── config_service.py    # Tenant parameter management
│   ├── views/
│   │   ├── employee_portal.py   # Gradio UI - employee views + My Timesheet
│   │   ├── hr_dashboard.py      # Gradio UI - HR views + presence indicators
│   │   ├── report_views.py      # Gradio UI - report views
│   │   └── admin_settings.py    # Gradio UI - config/settings
│   ├── copy/
│   │   ├── __init__.py          # CopyManager: loads and renders templates
│   │   ├── en.copy.yaml         # English copy resource (tone + messaging)
│   │   ├── tone_guidelines.md   # Editorial voice documentation
│   │   └── templates/           # Category-specific copy templates
│   ├── static/
│   │   └── rhythm.css           # Custom CSS: animations, reduced-motion, high-contrast
│   ├── middleware/
│   │   ├── decorators.py        # Auth, audit, sanitize decorators
│   │   ├── rate_limiter.py      # Rate limiting logic
│   │   └── error_handler.py     # Global error boundary
│   └── main.py                  # Entry point, DI wiring, Gradio app
├── shared/
│   ├── value_objects.py         # EmployeeID, TenantID, Timestamp
│   ├── config.py                # Externalized configuration loader
│   ├── enums.py                 # Shared enums across contexts
│   ├── work_schedule.py         # Work schedule pattern definitions
│   └── time_utils.py            # UTC conversion, boundary alignment, review period calculation
├── scripts/
│   ├── seed_data.py             # CLI entry point for data seeding
│   └── seed/
│       ├── __init__.py
│       ├── personas.py          # 10 employee persona definitions
│       ├── activity_generator.py # 4-week activity log generation
│       ├── clock_generator.py   # Clock-in/out entry generation
│       ├── exception_generator.py # Exception record generation
│       ├── audit_generator.py   # Realistic audit log generation
│       └── fixture_exporter.py  # JSON fixture export
└── tests/
    ├── unit/                    # pytest unit tests
    ├── property/                # Hypothesis property tests
    ├── integration/             # External service tests
    ├── e2e/                     # Playwright end-to-end tests (+ axe-core accessibility)
    ├── fixtures/                # JSON fixtures from seed data for offline testing
    ├── architecture/            # import-linter boundary tests
    └── security/                # Security-specific tests
```




### Performance Optimization Strategy

#### Identified Bottlenecks and Mitigations

| Bottleneck | Impact | Mitigation |
|-----------|--------|-----------|
| **Google Sheets API latency** (200-800ms per call) | Portal feels slow on every user action | In-memory cache (TTL: 5min HR data, 30min employee list); batch reads; concurrent request limit (5 max) |
| **Hugging Face Spaces cold start** (30-60s on free tier) | First user sees blank page | Branded loading screen; keep-alive pings from external monitoring (if cron available) |
| **Gemini API latency** (1-3s per classification) | Exception form submission feels slow | Async fire-and-forget: submit form immediately, classify in background, update record when done |
| **SQLite writes on Tracker** (single writer) | WAL helps but can still block on large sync queue | Batch inserts within transactions; WAL mode (concurrent reads while writing); connection pooling unnecessary (single process) |
| **Hash chain verification at startup** | Linear O(n) scan of all entries | Lazy verification: verify last 288 entries (24h) at startup; full chain verify only before sync |
| **Reconciliation calculation** (reads clock + activity + exceptions) | HR dashboard slow on first load | Pre-compute variance nightly after sync; cache results with 5-min TTL; paginate (max 50 records per page) |
| **Report generation** (large date ranges) | Monthly reports query 30+ days of data | Pagination; streaming CSV export (don't load all into memory); pre-aggregate daily summaries |
| **Rate limiter storage** | In-memory counters lost on restart | Acceptable for Portal (stateless design); use sliding window algorithm (sorted set of timestamps) |
| **Multiple Google Sheets tabs** (13 sheets) | gspread opens worksheet by name each time | Cache worksheet references; reuse gspread client across requests within a session |

#### Async Architecture (Portal)

```python
# All external I/O uses async/await to prevent blocking Gradio event loop
async def submit_exception(self, request: ExceptionRequest) -> ExceptionResponse:
    # 1. Validate inputs (sync - fast)
    validated = self.validator.validate(request)
    
    # 2. Write to Central Store (async - may be slow)
    record_id = await self.exception_store.create(validated)
    
    # 3. Classify with Gemini (async fire-and-forget - don't block user)
    asyncio.create_task(self._classify_background(record_id, validated.comment))
    
    # 4. Return immediately to user
    return ExceptionResponse(id=record_id, status="submitted", ai_tag="Pending")
```

#### Tracker Performance Budget

| Operation | Budget | Actual Target |
|-----------|--------|---------------|
| Activity check (pynput callback) | < 1ms | Event-driven; no polling cost |
| WiFi detection (subprocess) | < 5s timeout | Typically 200-500ms |
| SQLite write (single entry) | < 10ms | WAL mode, single writer |
| Hash computation (SHA-256) | < 1ms | Pure computation |
| NTP query | < 5s timeout | Typically 50-200ms |
| Full 5-min cycle | < 6s total | Leaves 294s idle between cycles |
| Memory footprint | < 50MB | Compiled PyInstaller binary |

#### Connection Pooling and Resource Management

```python
# Google Sheets adapter: reuse authorized client
class SheetsAdapter:
    def __init__(self, credentials_path: str):
        self._client: Optional[gspread.Client] = None
        self._worksheets: dict[str, Worksheet] = {}  # Cache worksheet references
    
    async def _get_client(self) -> gspread.Client:
        if self._client is None:
            self._client = gspread.service_account(filename=credentials_path)
        return self._client
    
    async def _get_worksheet(self, name: str) -> Worksheet:
        if name not in self._worksheets:
            client = await self._get_client()
            spreadsheet = client.open_by_key(self._sheet_id)
            self._worksheets[name] = spreadsheet.worksheet(name)
        return self._worksheets[name]
```


### DevSecOps and Shift-Left Security Strategy

The system implements a comprehensive shift-left approach where security is integrated at every stage of development — not bolted on at the end.

#### Shift-Left Security Layers

```mermaid
graph LR
    subgraph "Developer Workstation (Earliest)"
        IDE[Snyk IDE Plugin<br/>Real-time feedback]
        PRE[Pre-commit Hooks<br/>Secrets detection]
        TYPE[mypy strict<br/>Type safety]
    end
    subgraph "Pull Request (CI)"
        LINT[Ruff Linter]
        SAST[Snyk Code SAST]
        DEP[Snyk Dependency Scan]
        ARCH[import-linter<br/>Architecture boundaries]
        PROP[Hypothesis<br/>Property-based fuzzing]
        SEC[Security unit tests<br/>Injection prevention]
    end
    subgraph "Staging (Pre-Production)"
        DAST[OWASP ZAP<br/>Dynamic scanning]
        E2E[Playwright<br/>Auth flow tests]
        PEN[Prompt injection tests]
    end
    subgraph "Production (Runtime)"
        RATE[Rate limiter]
        CB2[Circuit breakers]
        AUDIT[Audit trail]
        INCIDENT[Incident detection]
        KILL[Kill switch]
    end
    IDE --> PRE --> LINT --> SAST --> DAST --> RATE
```

#### Security at Each Development Phase

| Phase | Tool/Practice | What It Catches | Shift-Left Benefit |
|-------|-------------|-----------------|-------------------|
| **Coding** | Snyk IDE plugin | Vulnerable deps, insecure patterns | Fix before commit (cheapest to fix) |
| **Coding** | mypy strict mode | Type confusion, None-safety violations | Prevents runtime type errors |
| **Coding** | Type hints + Protocols | Interface violations | Compile-time contract enforcement |
| **Pre-commit** | detect-secrets hook | API keys, tokens in code | Prevents secret leakage |
| **PR** | Snyk dependency scan | Known CVEs in packages | Block vulnerable deps before merge |
| **PR** | Snyk code (SAST) | SQL injection, XSS, hardcoded secrets | Catch code-level vulns statically |
| **PR** | import-linter | Architecture violations | Prevent domain→adapter coupling |
| **PR** | Hypothesis property tests | Input validation bypasses, logic errors | Fuzz-like coverage in unit test time |
| **PR** | Security unit tests | Command injection, RBAC bypass | Verify security controls work |
| **PR** | Ruff + bandit rules | Insecure function usage (eval, exec) | Static ban on dangerous patterns |
| **Staging** | OWASP ZAP baseline | XSS, CSRF, missing headers, info disclosure | Runtime vuln detection pre-prod |
| **Staging** | Prompt injection test suite | AI prompt manipulation | Verify AI guardrails hold |
| **Production** | Rate limiting | DDoS, brute force | Runtime protection |
| **Production** | Circuit breaker | Cascade failures | Runtime resilience |
| **Production** | Audit trail + incidents | Unauthorized access, tampering | Detection + forensics |
| **Production** | Kill switch | Active breach containment | Immediate response capability |

#### Secure-by-Default Configuration

```python
# All security features ON by default — no manual hardening needed
@dataclass(frozen=True)
class SecurityDefaults:
    https_enforced: bool = True
    rate_limiting_active: bool = True
    session_timeout_active: bool = True
    input_validation_active: bool = True
    audit_logging_enabled: bool = True
    debug_mode: bool = False          # Explicitly OFF in production
    verbose_errors: bool = False       # Never show stack traces to users
    csrf_protection: bool = True
    secure_cookies: bool = True        # HttpOnly, Secure, SameSite=Strict
```

#### Supply Chain Security

| Measure | Implementation |
|---------|---------------|
| Dependency pinning | All deps in `requirements.txt` with exact versions (==) |
| Dependency scanning | Snyk monitors for new CVEs post-merge |
| Lock file | `pip-compile` generates deterministic `requirements.txt` |
| Minimal dependencies | Only well-known, actively maintained packages |
| No arbitrary code execution | No `eval()`, `exec()`, `pickle.loads()` in codebase |
| Subprocess safety | Arg arrays only, no `shell=True`, no string interpolation |

#### Threat Modeling (STRIDE)

Per Requirement 44.8, the system includes a STRIDE threat model:

| Threat | Example | Mitigation | Requirement |
|--------|---------|------------|-------------|
| **Spoofing** | Fake tracker data, auth bypass | Magic Links + hash chain integrity | R4, R5, R14 |
| **Tampering** | SQLite modification, clock manipulation | SHA-256 hash chain, NTP validation | R4, R14 |
| **Repudiation** | Deny clock-in/out actions | Immutable audit log, all actions logged | R26 |
| **Information Disclosure** | Data leakage, prompt extraction | RBAC at service layer, input sandwiching for AI | R35, R39 |
| **Denial of Service** | Rate limit abuse, API exhaustion | Rate limiter, circuit breaker, kill switch | R23, R44, R49 |
| **Elevation of Privilege** | RBAC bypass, admin impersonation | Permission checks at service layer (not just UI), audit all role changes | R35, R44.5 |

#### Continuous Security Monitoring

```yaml
# .github/workflows/security.yml (runs on schedule + PR)
on:
  schedule:
    - cron: '0 6 * * 1'   # Weekly Monday 6 AM
  pull_request:
    branches: [main]

jobs:
  snyk-deps:
    steps:
      - uses: snyk/actions/python@master
        with:
          args: --severity-threshold=high
  
  snyk-code:
    steps:
      - uses: snyk/actions/python@master
        with:
          command: code test
          args: --severity-threshold=high
  
  owasp-zap:
    if: github.event_name == 'schedule'
    steps:
      - uses: zaproxy/action-baseline@v0.7.0
        with:
          target: ${{ secrets.STAGING_URL }}
          rules_file_name: '.zap/rules.tsv'
```


### GRC (Governance, Risk, Compliance) and ISO 27001 Alignment

The requirements explicitly address GRC through a layered compliance framework:

#### Governance Controls

| Control | Implementation | Requirement |
|---------|---------------|-------------|
| **Access governance** | Configurable RBAC with 6 default roles + custom roles; permission enforcement at UI and service layer | R35 |
| **Change governance** | All parameter changes logged with who/what/when; config history maintained | R22.6 |
| **Policy governance** | Template policy documents (InfoSec, Acceptable Use, Data Retention); acknowledgement tracking | R31 |
| **Surveillance governance** | Notice period enforcement (14 days); versioned notices; employee acknowledgement | R29 |
| **Incident governance** | Structured incident workflow (Open → Investigating → Resolved); severity classification; HR notification | R30 |

#### Risk Management (STRIDE + Controls)

| Risk Category | Risk | Control | Evidence |
|--------------|------|---------|----------|
| **Data integrity** | Employee tampers with SQLite | SHA-256 hash chain detects any modification | Hash verification at startup + before sync |
| **Time fraud** | Employee adjusts system clock | NTP validation flags drift > 2 min; NTP time used as authoritative | Drift flag visible to HR |
| **Authentication bypass** | Unauthorized portal access | Magic Links (time-limited, single-use); session timeout; single-session enforcement | Audit log of all auth events |
| **Privilege escalation** | Employee accesses HR data | Service-layer RBAC checks (not just UI); unauthorized access logged as incident | Audit trail + incident detection |
| **Data loss** | Network outage loses tracking data | Offline-first SQLite; 90-day queue; WAL mode prevents corruption | Heartbeat monitoring detects missing data |
| **Supply chain** | Vulnerable dependency introduced | Snyk scanning blocks HIGH/CRITICAL; pinned versions; weekly re-scan | CI gate + alerting |

#### Compliance Framework

| Regulation/Standard | Coverage | Requirements |
|-------------------|----------|--------------|
| **ISO 27001** | Template policy documents; access control; audit trail; incident management; risk assessment (STRIDE) | R31, R26, R30, R44.8 |
| **GDPR** | Privacy notice; consent; data retention policy; right to deletion (30 days); "My Data" transparency page; no biometric/content collection | R27 |
| **NSW Workplace Surveillance Act 2005** | 14-day notice period; written notice (what/how/when/who); device scope limitation; acknowledgement; compliance report export | R29 |
| **WCAG 2.0 AA** | ARIA compliance; keyboard navigation; contrast ratios; responsive layout; programmatic error linking | R12 |
| **OWASP Top 10** | Input validation; HTTPS; rate limiting; CSRF protection; XSS prevention; ZAP scanning | R16, R23, R41 |

#### Audit Trail as Compliance Evidence

The append-only Audit_Log (Requirement 26) provides forensic evidence for:
- **Who** did what (actor_id, session_id)
- **What** action was taken (action_type, target_resource, old_value, new_value)
- **When** it happened (UTC timestamp)
- **Where** it came from (source_ip)
- **365-day retention** minimum for regulatory inquiries
- **Searchable/filterable** viewer for compliance officers

#### AI Governance

| Concern | Control | Requirement |
|---------|---------|-------------|
| **Transparency** | Disclosure notice on form: "Your text will be processed by AI (Gemini)" | R8.8 |
| **No autonomy** | AI only suggests categories — never generates verdicts or recommendations | R8.5, R10.6 |
| **Human override** | HR can override any AI tag with one click | R8.3 |
| **Labeling** | AI-assigned tags display "AI-suggested" label to distinguish from manual | R8.9 |
| **Prompt safety** | Fixed system template; user text sandwiched in delimiters; response validation; instruction stripping | R39.1-39.7 |
| **Graceful degradation** | API failure → "Unclassified" (never blocks user) | R8.4, R15.2 |
| **Data minimization** | Only category classification; no storage by AI service; text not used for training | R8.8 disclosure |
| **Rate limiting** | 15 req/min, 1500 req/day (Gemini free tier limits) | R8.7 |

#### Coding Standards and Best Practices

| Standard | Enforcement | Tool |
|----------|------------|------|
| Type safety (PEP 484) | All functions typed; strict mode | mypy (CI gate) |
| Code style (PEP 8) | Consistent formatting | Ruff linter (CI gate) |
| Import hygiene | No domain→adapter imports | import-linter (CI gate) |
| Security patterns | No eval/exec/pickle; subprocess arg arrays; parameterized queries | Ruff + bandit rules + Snyk SAST |
| Documentation | Docstrings on all public interfaces | CI check (optional) |
| Test coverage | 90% line coverage on domain modules | pytest-cov (CI gate) |
| Dependency management | Pinned versions; Snyk monitoring | pip-compile + Snyk |
| Error handling | Structured categories (Transient/Permanent/Fatal); no raw tracebacks | Global error boundary |
| Immutability | Domain entities use frozen=True where appropriate | Code review + type checker |
| SOLID principles | Single responsibility, interface segregation, dependency inversion | Architecture tests + code review |


### Essential Eight (ASD) Alignment

The [Australian Signals Directorate Essential Eight](https://www.cyber.gov.au/resources-business-and-government/essential-cyber-security/essential-eight) framework defines eight mitigation strategies to protect against cyber threats. Below is the system's alignment, targeting **Maturity Level 2** where applicable.

| # | Strategy | System Coverage | Maturity Level |
|---|----------|----------------|----------------|
| 1 | **Application Control** | Tracker is a signed, notarized single-file executable; no user-installable plugins; PyInstaller --onefile prevents DLL sideloading; LaunchDaemon/Service runs only the approved binary | ML2 |
| 2 | **Patch Applications** | Snyk dependency scanning detects known CVEs; CI blocks HIGH/CRITICAL vulns; semantic versioning enables controlled updates; weekly Snyk re-scan for new disclosures | ML2 |
| 3 | **Configure MS Office Macros** | N/A (no Office integration); Google Sheets API access is service-account only (no macro execution surface) | N/A |
| 4 | **User Application Hardening** | Portal runs on Gradio (Python server-side rendering); no Flash/Java/ActiveX; CSP headers restrict script sources; Gradio sanitizes rendered HTML | ML1 |
| 5 | **Restrict Administrative Privileges** | RBAC with least-privilege defaults; Employee role has VIEW_OWN_DATA only; admin operations require explicit role assignment; service-layer enforcement prevents UI bypass; all privilege changes audited | ML2 |
| 6 | **Patch Operating Systems** | Tracker compiled with latest Python runtime; GitHub Actions uses latest runner images; HF Spaces base images auto-updated; documented recommendation for endpoint patching (out of system scope — employee laptops managed by IT) | ML1 |
| 7 | **Multi-Factor Authentication** | Magic Links provide passwordless authentication via email (possession factor); session timeout enforces re-authentication; single-session enforcement prevents session sharing | ML1* |
| 8 | **Regular Backups** | SQLite Local_DB retains all data locally (offline backup); Central Store (Google Sheets) has Google's built-in version history; 90-day sync queue ensures no data loss; WAL mode prevents corruption | ML2 |

*Note on MFA (Strategy 7): Magic Links are single-factor (email possession). For ML2+ compliance, a recommendation is included below.

#### Essential Eight Recommendations for Enhancement

**Strategy 7 (MFA) Enhancement Path:**
The current Magic Link design is single-factor (something you have — access to email). For organizations requiring Essential Eight Maturity Level 2+ on MFA:

```python
# Future enhancement: Optional TOTP second factor for HR administrators
class EnhancedAuthService:
    async def verify_magic_link(self, token: str, totp_code: Optional[str] = None) -> Session:
        """If tenant config requires MFA for admin roles, verify TOTP after magic link."""
        session = await self._verify_token(token)
        if self._requires_mfa(session.role_ids):
            if not totp_code or not self._verify_totp(session.employee_id, totp_code):
                raise MFARequired("TOTP verification required for admin access")
        return session
```

- Add optional TOTP (Time-based One-Time Password) as a configurable second factor
- Required for HR Administrator, IT Administrator, and Tenant Administrator roles
- Employee role remains Magic Link only (low-risk access)
- Configuration: `mfa_required_roles` in TenantConfig

**Strategy 1 (Application Control) Enhancement:**
- Tracker binary hash published with each release for IT teams to verify
- Recommend organizations configure application allow-listing (AppLocker on Windows, XProtect on macOS) to only permit the signed Tracker binary
- Document in deployment guide

**Strategy 5 (Admin Privileges) Enhancement:**
- Tracker runs as a dedicated service account (not LocalSystem/root)
- Principle of least privilege: service account has ONLY write access to its own data directory and SQLite DB
- No network listener (Tracker doesn't accept inbound connections)

#### Essential Eight Controls Already Implemented

The following controls are already designed into the system without additional work:

1. **No arbitrary code execution** — No eval(), exec(), pickle, or dynamic imports in codebase
2. **Subprocess argument arrays** — All shell commands use list form (no shell=True)
3. **Input validation** — All user input validated before processing (Pydantic + custom validators)
4. **Least privilege data access** — Employees see only their own data; RBAC enforces at service layer
5. **Audit trail** — All security-relevant actions logged; 365-day retention
6. **Signed binaries** — Code signing (Windows) and notarization (macOS) in CI/CD pipeline
7. **Encrypted transport** — HTTPS enforced for all Portal communication; gspread uses HTTPS
8. **Data at rest** — SQLite on protected filesystem paths (admin-only access)
9. **Backup resilience** — 90-day offline queue; Google Sheets version history; WAL mode
10. **Incident response** — Automated detection, severity classification, HR notification

### Internal Event-Driven Patterns

While the system is primarily request/response and scheduled (not a distributed event-driven architecture), it uses an **internal domain event bus** within the Portal monolith to decouple side effects from primary operations.

#### Why Not Full Event-Driven Architecture?

| Concern | Decision |
|---------|----------|
| Two deployable units (not many services) | Event bus between Tracker and Portal is overkill — they communicate via shared store |
| Google Sheets has no pub/sub | No push notifications from Central Store; polling is used |
| Free tier constraints | No message broker (Kafka, RabbitMQ) available |
| Simplicity | In-process events sufficient for monolith side effects |

#### Internal Domain Event Bus (Portal)

The Portal uses a lightweight in-process event bus (publish/subscribe within a single process) to decouple primary actions from side effects:

```python
from typing import Protocol, Callable, Any
from dataclasses import dataclass
from datetime import datetime

class DomainEvent(Protocol):
    """Base protocol for all domain events."""
    timestamp: datetime
    tenant_id: str

@dataclass(frozen=True)
class ClockInEvent:
    timestamp: datetime
    tenant_id: str
    employee_id: str
    declared_location: str

@dataclass(frozen=True)
class ExceptionSubmittedEvent:
    timestamp: datetime
    tenant_id: str
    employee_id: str
    exception_id: str
    comment: str

@dataclass(frozen=True)
class IntegrityViolationReceivedEvent:
    timestamp: datetime
    tenant_id: str
    employee_id: str
    violation_start_entry_id: str

@dataclass(frozen=True)
class KillSwitchActivatedEvent:
    timestamp: datetime
    tenant_id: str
    activated_by: str
    reason: str

@dataclass(frozen=True)
class GeminiAvailableEvent:
    timestamp: datetime
    tenant_id: str

class EventBus:
    """Simple in-process publish/subscribe for domain events."""
    
    def __init__(self):
        self._handlers: dict[type, list[Callable]] = {}
    
    def subscribe(self, event_type: type, handler: Callable) -> None:
        """Register a handler for an event type."""
    
    def publish(self, event: DomainEvent) -> None:
        """Dispatch event to all registered handlers synchronously."""
    
    async def publish_async(self, event: DomainEvent) -> None:
        """Dispatch event to all registered handlers asynchronously."""
```

#### Event Flow Diagram

```mermaid
graph LR
    subgraph "Publishers (Primary Actions)"
        CS[Clock Service]
        ES[Exception Service]
        SS[Sync Receiver]
        KS[Kill Switch]
    end
    subgraph "Event Bus"
        EB((Domain Event Bus))
    end
    subgraph "Subscribers (Side Effects)"
        AL[Audit Logger]
        CI[Cache Invalidator]
        IN[Incident Notifier]
        GT[Gemini Reclassifier]
        SM[Session Manager]
    end
    CS -->|ClockInEvent| EB
    ES -->|ExceptionSubmittedEvent| EB
    SS -->|IntegrityViolationReceivedEvent| EB
    KS -->|KillSwitchActivatedEvent| EB
    EB --> AL
    EB --> CI
    EB --> IN
    EB --> GT
    EB --> SM
```

#### Event-to-Handler Mapping

| Event | Subscribers | Action |
|-------|------------|--------|
| `ClockInEvent` | AuditLogger, CacheInvalidator | Log audit entry; invalidate reconciliation cache |
| `ClockOutEvent` | AuditLogger, CacheInvalidator | Log audit entry; invalidate reconciliation cache |
| `ExceptionSubmittedEvent` | AuditLogger, GeminiTagger | Log audit entry; trigger AI classification (detailed form only) |
| `QuickExceptionRecordedEvent` | AuditLogger, CacheInvalidator | Log toast-based exception; invalidate variance cache |
| `ExceptionApprovedEvent` | AuditLogger, CacheInvalidator | Log audit entry; invalidate variance cache |
| `IntegrityViolationReceivedEvent` | IncidentNotifier, AuditLogger | Create incident; notify HR admins via email |
| `ClockDriftReceivedEvent` | IncidentNotifier, AuditLogger | Create incident (High severity) |
| `TrackerOfflineEvent` | IncidentNotifier | Create incident if offline > 24h |
| `KillSwitchActivatedEvent` | SessionManager, AuditLogger | Terminate all sessions; log event |
| `GeminiAvailableEvent` | GeminiReclassifier | Reclassify "Unclassified" exception records |
| `ParameterChangedEvent` | AuditLogger, CacheInvalidator | Log change with old/new values; invalidate config cache |
| `RolAssignmentChangedEvent` | AuditLogger | Log role change |
| `LoginFailedEvent` | IncidentDetector | Check if > 5 failures from same IP in 1h -> create incident |
| `RateLimitViolationEvent` | IncidentDetector, AuditLogger | Check if > 3 violations from same IP in 1h -> create incident |
| `ReviewPeriodCompletedEvent` | TransparencyReportGenerator, WellnessService | Generate Transparency Report; update consecutive clean count; check badge |
| `ReviewPeriod75PercentEvent` | SelfCorrectionNotifier | Check running variance; send notification if threshold exceeded |
| `WorkScheduleChangedEvent` | AuditLogger, CacheInvalidator | Log change; invalidate reconciliation cache |

#### Tracker: Timer-Based (Not Event-Driven)

The Tracker uses a **timer-based loop** (not event-driven) because:
- Activity detection aggregates over 5-minute windows (not real-time events)
- Sync is scheduled (midnight + heartbeat interval)
- No external consumers subscribe to Tracker events
- Simplicity: a single polling loop is easier to reason about on a background service

```python
class TrackerLoop:
    """Main timer-based execution loop."""
    
    async def run(self):
        while self._running:
            next_boundary = self.get_next_boundary(datetime.utcnow())
            await asyncio.sleep_until(next_boundary)
            await self.run_cycle()  # Log activity, detect location, compute hash
            
            if self._is_heartbeat_due():
                await self.send_heartbeat()
            
            if self._is_midnight():
                await self.perform_nightly_sync()
```


### Python Backend Engineering Features

The system leverages these Python language features and patterns (per Requirement 45):

#### Type Safety Layer

```python
# PEP 484 type hints on all signatures (enforced by mypy strict)
from typing import Protocol, Optional, Any
from datetime import datetime, timedelta

# PEP 544 Protocols for structural subtyping (duck typing with type safety)
class ClockStorePort(Protocol):
    def create_entry(self, entry: ClockEntry) -> str: ...
    def close_entry(self, entry_id: str, clock_out: datetime) -> None: ...
    def get_open_session(self, employee_id: str) -> Optional[ClockEntry]: ...

# Pydantic models for runtime validation + serialization
from pydantic import BaseModel, Field, EmailStr, field_validator

class ExceptionSubmission(BaseModel):
    category: ExceptionCategory
    duration_minutes: int = Field(ge=5, le=480)
    comment: str = Field(min_length=10, max_length=500)
    
    @field_validator('duration_minutes')
    @classmethod
    def must_be_multiple_of_5(cls, v: int) -> int:
        if v % 5 != 0:
            raise ValueError('Duration must be in 5-minute increments')
        return v

# Frozen dataclasses for immutable domain entities
@dataclass(frozen=True)
class LogEntry:
    id: str
    timestamp: datetime
    employee_id: str
    status: ActivityStatus
    location: LocationType
    hash: str
    previous_hash: str
```

#### Async/Await Architecture (Portal)

```python
import asyncio
from contextlib import asynccontextmanager

# All external I/O is async to prevent blocking Gradio event loop
class ClockService:
    async def clock_in(self, request: ClockInRequest) -> ClockInResponse:
        # Validate (sync - fast)
        validated = self.validator.validate_clock_in(request)
        
        # Check no open session (async - reads from store)
        existing = await self.clock_store.get_open_session(request.employee_id)
        if existing:
            raise ClockSessionConflict("Open session exists")
        
        # Write to store (async - may be slow)
        entry_id = await self.clock_store.create_entry(validated)
        
        # Publish event (async - fire and forget for side effects)
        await self.event_bus.publish_async(ClockInEvent(...))
        
        return ClockInResponse(entry_id=entry_id, timestamp=validated.clock_in_time)

# Context managers for resource cleanup
@asynccontextmanager
async def sheets_connection(credentials_path: str):
    client = await asyncio.to_thread(gspread.service_account, filename=credentials_path)
    try:
        yield client
    finally:
        # gspread doesn't need explicit close, but pattern is ready for DB migration
        pass
```

#### Dependency Injection (Constructor Injection)

```python
# All service classes accept dependencies via constructor
class ReconciliationService:
    def __init__(
        self,
        clock_store: ClockStorePort,          # Interface, not concrete class
        activity_store: ActivityStorePort,
        exception_store: ExceptionStorePort,
        cache: CachePort,
        config: TenantConfig,
    ):
        self._clock_store = clock_store
        self._activity_store = activity_store
        self._exception_store = exception_store
        self._cache = cache
        self._config = config

# Wiring happens once at application startup (composition root)
def create_reconciliation_service(config: AppConfig) -> ReconciliationService:
    sheets_client = create_sheets_client(config.credentials_path)
    return ReconciliationService(
        clock_store=SheetsClockAdapter(sheets_client),
        activity_store=SheetsActivityAdapter(sheets_client),
        exception_store=SheetsExceptionAdapter(sheets_client),
        cache=InMemoryCache(),
        config=config.tenant,
    )
```

#### Enums for Type-Safe Domain Values

```python
from enum import Enum, auto

class ActivityStatus(str, Enum):
    ONLINE = "Online"
    IDLE = "Idle"

class LocationType(str, Enum):
    OFFICE = "office"
    HOME = "home"

class FlagColor(str, Enum):
    RED = "red"
    AMBER = "amber"
    GREEN = "green"

class Permission(str, Enum):
    VIEW_OWN_DATA = "view_own_data"
    VIEW_ALL_EMPLOYEE_DATA = "view_all_employee_data"
    MANAGE_EMPLOYEES = "manage_employees"
    APPROVE_EXCEPTIONS = "approve_exceptions"
    # ... all permissions as enum values

class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()

class ErrorCategory(Enum):
    TRANSIENT = auto()   # Retry automatically
    PERMANENT = auto()   # Alert user
    FATAL = auto()       # Alert admin, continue other subsystems
```

#### Python Standard Library Usage

| Feature | Usage | Benefit |
|---------|-------|---------|
| `logging` module | Structured JSON logs (custom Formatter) | Standard, configurable, rotatable |
| `asyncio` | All Portal I/O operations | Non-blocking Gradio; concurrent API calls |
| `dataclasses` | Domain entities (frozen=True for immutability) | Clean models, auto __eq__, __hash__ |
| `typing.Protocol` | Port interfaces (PEP 544) | Structural subtyping; no inheritance required |
| `abc.ABC` | Template Method base classes | Enforced abstract methods |
| `enum.Enum` | All domain value sets | Type-safe; IDE autocomplete; no typos |
| `contextlib` | Context managers for resources | Guaranteed cleanup (DB, files, network) |
| `hashlib` | SHA-256 hash chain | Standard crypto; no external deps |
| `secrets` | Magic Link token generation | Cryptographically secure randomness |
| `subprocess` | WiFi detection (arg arrays) | Secure command execution |
| `sqlite3` | Local_DB adapter (WAL mode) | Zero-config embedded database |
| `json` | Structured log formatting | Standard serialization |
| `datetime` + `zoneinfo` | UTC storage, timezone display | PEP 615 timezone support (Python 3.9+) |
| `functools.wraps` | Decorator pattern implementation | Preserves function metadata |
| `collections.deque` | Rate limiter sliding window | O(1) append/pop from both ends |

## Components and Interfaces

### Tracker Domain Ports (Interfaces)

```python
from typing import Protocol, Optional
from datetime import datetime, timedelta, date

class ActivityMonitorPort(Protocol):
    """Port for detecting user activity signals."""
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def has_activity_since(self, since: datetime) -> bool: ...
    def get_idle_duration(self) -> timedelta: ...

class WifiDetectionPort(Protocol):
    """Port for OS-specific WiFi network detection."""
    def get_current_network(self) -> Optional[WifiInfo]: ...

class ToastNotificationPort(Protocol):
    """Port for displaying OS-native toast notifications on idle return."""
    def show_idle_return_toast(
        self, idle_duration: timedelta, categories: list[str]
    ) -> Optional[str]: ...
    """Shows toast with idle duration and category buttons.
    Returns selected category or None if dismissed/timed out."""
    def is_suppressed(self) -> bool: ...
    """Returns True if Focus Mode is active (notifications suppressed)."""

class FocusModePort(Protocol):
    """Port for Focus Mode system tray toggle."""
    def activate(self, duration_hours: int) -> None: ...
    def deactivate(self) -> None: ...
    def is_active(self) -> bool: ...
    def remaining_minutes(self) -> int: ...

class LocalStoragePort(Protocol):
    """Port for local data persistence (SQLite)."""
    def insert_log_entry(self, entry: LogEntry) -> bool: ...
    def insert_quick_exception(self, exception: QuickException) -> bool: ...
    def get_entries_for_date(self, target_date: date) -> list[LogEntry]: ...
    def get_sync_queue(self) -> list[LogEntry]: ...
    def get_exception_sync_queue(self) -> list[QuickException]: ...
    def mark_synced(self, entry_ids: list[str]) -> None: ...
    def get_queue_oldest_date(self) -> Optional[date]: ...
    def get_last_valid_hash(self) -> Optional[str]: ...

class RemoteStorePort(Protocol):
    """Port for Central Store communication."""
    def push_sync_batch(self, entries: list[LogEntry]) -> bool: ...
    def push_exceptions(self, exceptions: list[QuickException]) -> bool: ...
    def send_heartbeat(self, employee_id: str, timestamp: datetime) -> bool: ...

class TimeServicePort(Protocol):
    """Port for NTP time validation."""
    def get_authoritative_time(self) -> Optional[datetime]: ...
```

### Portal Domain Ports (Interfaces)

```python
class EmployeeStorePort(Protocol):
    """Repository for employee records."""
    def get_by_id(self, employee_id: str) -> Optional[Employee]: ...
    def get_by_email(self, email: str) -> Optional[Employee]: ...
    def get_all(self, tenant_id: str) -> list[Employee]: ...
    def create(self, employee: Employee) -> str: ...
    def update(self, employee: Employee) -> None: ...
    def deactivate(self, employee_id: str) -> None: ...

class ClockStorePort(Protocol):
    """Repository for clock-in/out entries."""
    def create_entry(self, entry: ClockEntry) -> str: ...
    def close_entry(self, entry_id: str, clock_out: datetime) -> None: ...
    def get_open_session(self, employee_id: str) -> Optional[ClockEntry]: ...
    def get_entries_for_date(self, employee_id: str, d: date) -> list[ClockEntry]: ...

class ExceptionStorePort(Protocol):
    """Repository for exception records."""
    def create(self, record: ExceptionRecord) -> str: ...
    def get_pending(self, tenant_id: str) -> list[ExceptionRecord]: ...
    def update_status(self, record_id: str, status: str, reason: Optional[str]) -> None: ...
    def update_tag(self, record_id: str, tag: str) -> None: ...
    def get_approved_for_period(self, employee_id: str, start: date, end: date) -> list[ExceptionRecord]: ...
    def get_by_submitter(self, employee_id: str) -> list[ExceptionRecord]: ...

class AIClassifierPort(Protocol):
    """Port for AI-powered text classification."""
    def classify(self, text: str) -> str: ...

class EmailSenderPort(Protocol):
    """Port for email delivery."""
    def send_magic_link(self, email: str, token: str, expiry_minutes: int) -> bool: ...
    def send_incident_notification(self, emails: list[str], incident: Incident) -> bool: ...
    def send_self_correction_notification(self, email: str, message: str) -> bool: ...
    def send_transparency_report(self, email: str, report: TransparencyReport) -> bool: ...

class EmployeeNotificationPort(Protocol):
    """Port for in-app employee notifications (Portal inbox)."""
    def send(self, employee_id: str, message: str, link: Optional[str] = None) -> None: ...
    def get_unread(self, employee_id: str) -> list[Notification]: ...

class WorkScheduleStorePort(Protocol):
    """Repository for work schedule patterns."""
    def get_schedule(self, employee_id: str, effective_date: date) -> WorkSchedulePattern: ...
    def update_schedule(self, employee_id: str, pattern: WorkSchedulePattern) -> None: ...
    def get_default(self, tenant_id: str) -> WorkSchedulePattern: ...

class PresencePort(Protocol):
    """Port for ephemeral presence calculation (NOT stored)."""
    def get_presence(self, employee_id: str) -> bool: ...
    """Returns True if last heartbeat/activity within 10 min. Ephemeral only."""

class WellnessStorePort(Protocol):
    """Repository for employee wellness state (badges, notification tracking)."""
    def get_consecutive_clean_periods(self, employee_id: str) -> int: ...
    def increment_clean_periods(self, employee_id: str) -> None: ...
    def reset_clean_periods(self, employee_id: str) -> None: ...
    def has_sent_self_correction(self, employee_id: str, period_start: date) -> bool: ...
    def mark_self_correction_sent(self, employee_id: str, period_start: date) -> None: ...

class AuditStorePort(Protocol):
    """Port for append-only audit log."""
    def append(self, entry: AuditEntry) -> None: ...
    def query(self, filters: AuditFilters) -> list[AuditEntry]: ...

class CachePort(Protocol):
    """Port for in-memory caching with TTL."""
    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def invalidate(self, key: str) -> None: ...
```


### Key Service Classes

#### TrackerService (Main Loop)

```python
class TrackerService:
    """Orchestrates the 5-minute logging cycle with notification and focus mode support."""
    
    def __init__(
        self,
        activity_monitor: ActivityMonitorPort,
        location_detector: WifiDetectionPort,
        local_storage: LocalStoragePort,
        hash_chain: HashChainManager,
        toast_notification: ToastNotificationPort,
        focus_mode: FocusModePort,
        logger: StructuredLoggerPort,
        config: TrackerConfig,
    ): ...
    
    def run_cycle(self) -> None:
        """Execute one 5-minute logging cycle:
        1. Check activity since last boundary
        2. Determine status (Online/Idle based on idle_threshold)
        3. If resuming from idle:
           a. Calculate idle duration
           b. If idle_duration <= auto_exempt_threshold: treat as normal (no notification)
           c. If idle_duration > auto_exempt_threshold AND focus_mode inactive: show toast
           d. If idle_duration > auto_exempt_threshold AND focus_mode active: record Unmarked Idle
        4. Detect location
        5. Compute hash (chain with previous)
        6. Write to Local_DB (retry up to 3x on failure)
        """
    
    def get_next_boundary(self, now: datetime) -> datetime:
        """Compute next clock-aligned 5-min boundary."""
```

#### ReconciliationService

```python
class ReconciliationService:
    """Calculates variance per configurable review period and detects location mismatches."""
    
    def __init__(
        self,
        clock_store: ClockStorePort,
        activity_store: ActivityStorePort,
        exception_store: ExceptionStorePort,
        work_schedule_store: WorkScheduleStorePort,
        cache: CachePort,
        config: TenantConfig,
    ): ...
    
    @require_auth
    @require_permission(Permission.VIEW_ALL_EMPLOYEE_DATA)
    @audit_log("view_reconciliation")
    def calculate_period_variance(self, employee_id: str, review_period: ReviewPeriod) -> PeriodVarianceResult:
        """Variance per review period = Manual Claimed - (Tracked Active + Approved Exceptions + Auto-Exempt Idle).
        Only counts idle within declared work schedule blocks.
        Returns flag: RED (< -threshold), AMBER (> +threshold), GREEN (in range).
        Threshold defaults to 3.0h/week, scaled proportionally for other periods.
        Single bad days do NOT trigger flags — only sustained patterns across the full period."""
    
    @require_auth
    @require_permission(Permission.VIEW_ALL_EMPLOYEE_DATA)
    def get_daily_breakdown(self, employee_id: str, review_period: ReviewPeriod) -> list[DailyVarianceDetail]:
        """Drill-down view: per-day detail within a review period."""
    
    @require_auth
    @require_permission(Permission.VIEW_ALL_EMPLOYEE_DATA)
    def check_location_mismatch(self, employee_id: str, target_date: date) -> LocationCheckResult:
        """Flag if >50% of tracker entries conflict with declared location."""
```

#### AuthService

```python
class AuthService:
    """Magic Link authentication with single-session enforcement."""
    
    def __init__(
        self,
        employee_store: EmployeeStorePort,
        email_sender: EmailSenderPort,
        audit_store: AuditStorePort,
        rate_limiter: RateLimiter,
        config: AuthConfig,
    ): ...
    
    def request_login(self, email: str) -> LoginResult:
        """Generate Magic Link, enforce rate limit (3/15min), send email."""
    
    def verify_token(self, token: str) -> Optional[Session]:
        """Validate token (not expired, not used); create session; invalidate
        any existing session for same user (single-session invariant)."""
    
    def check_session(self, session_id: str) -> Optional[Session]:
        """Return session if active and not timed out (30min inactivity)."""
```

### Communication Patterns

| From | To | Protocol | Frequency | Circuit Breaker |
|------|------|----------|-----------|-----------------|
| Tracker -> Central Store | HTTPS (gspread) | Nightly sync + 30-min heartbeat | Yes |
| Portal -> Central Store | HTTPS (gspread) | On user action | Yes |
| Portal -> Gemini API | HTTPS REST | On exception submission | Yes |
| Portal -> Email Service | SMTP/API | On login request | Yes |
| NTP Validator -> time.google.com | NTP (UDP 123) | Before each sync | Yes |


## Data Models

### Core Domain Entities

#### LogEntry (Tracker Domain)
```python
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
from enum import Enum

class ActivityStatus(str, Enum):
    ONLINE = "Online"
    IDLE = "Idle"

class LocationType(str, Enum):
    OFFICE = "office"
    HOME = "home"

@dataclass(frozen=True)
class LogEntry:
    id: str                           # UUID4
    timestamp: datetime               # UTC, clock-aligned to 5-min boundary
    employee_id: str                  # Set at installation
    status: ActivityStatus            # Online | Idle
    location: LocationType            # office | home
    hash: str                         # SHA-256 chained hash
    previous_hash: str                # Hash of previous entry
    synced: bool = False              # Whether pushed to Central Store
    integrity_flag: Optional[str] = None    # "Integrity Violation"
    time_drift_flag: Optional[str] = None   # "Clock Drift Detected" | "NTP Unavailable"
    detection_error: Optional[str] = None   # Location detection failure reason
```

#### Employee (Shared Kernel)
```python
class WorkSchedule(str, Enum):
    OFFICE = "office"
    HYBRID = "hybrid"
    REMOTE = "remote"

class WorkPatternType(str, Enum):
    STANDARD = "standard"       # Single continuous block (e.g., 09:00-17:00)
    SPLIT = "split"             # Two blocks (e.g., 06:00-12:00 and 18:00-21:00)
    FLEXIBLE = "flexible"       # No fixed hours — any activity within the day counts
    CUSTOM = "custom"           # Up to 3 configurable time blocks per day

class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass(frozen=True)
class TimeBlock:
    start: time                       # e.g., time(9, 0) for 09:00
    end: time                         # e.g., time(17, 0) for 17:00

@dataclass
class WorkSchedulePattern:
    pattern_type: WorkPatternType
    blocks: list[TimeBlock]           # 1 block for Standard, 2 for Split, up to 3 for Custom
    effective_from: date              # Changes take effect from this date

@dataclass
class Employee:
    id: str                           # Unique Employee_ID
    tenant_id: str                    # Tenant partition key
    full_name: str
    email: str                        # Company email (RFC 5322)
    role_ids: list[str]               # Assigned role IDs
    timezone: str                     # IANA identifier (e.g., "Australia/Sydney")
    work_schedule: WorkSchedule       # office/hybrid/remote
    work_pattern: WorkSchedulePattern # Declares working hours pattern
    status: EmployeeStatus
    locale: str = "en"                # Preferred locale
    created_at: datetime = None
    deactivated_at: Optional[datetime] = None
    consecutive_clean_periods: int = 0  # Count for "Great Standing" badge
```

#### ClockEntry (Portal Domain)
```python
@dataclass
class ClockEntry:
    id: str                           # UUID4
    tenant_id: str
    employee_id: str
    clock_in_time: datetime           # UTC
    clock_out_time: Optional[datetime] = None  # UTC, None if open
    declared_location: LocationType
    auto_closed: bool = False         # True if closed by Auto_Clock_Out
    sync_status: str = "synced"       # "synced" | "pending"
    idempotency_key: str = ""         # Prevents duplicate submissions
```

#### ExceptionRecord (Portal Domain)
```python
class ExceptionCategory(str, Enum):
    MEDICAL_BREAK = "Medical Break"
    CLIENT_MEETING = "Client Meeting"
    HARDWARE_ISSUE = "Hardware Issue"
    PERSONAL_LEAVE = "Personal Leave"

class ExceptionSource(str, Enum):
    TOAST_QUICK = "toast_quick"       # One-click from desktop toast notification
    DETAILED_FORM = "detailed_form"   # Full Exception_Form in Portal

class ApprovalStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

@dataclass
class ExceptionRecord:
    id: str                           # UUID4
    tenant_id: str
    employee_id: str
    date: date
    category: ExceptionCategory       # User-selected (from toast or form)
    source: ExceptionSource           # How the exception was submitted
    ai_tag: str                       # Gemini-classified or "Unclassified" (only for detailed form)
    duration_minutes: int             # Auto-calculated from idle period (toast) or 5-480 (form)
    comment: str                      # Empty for toast; 10-500 characters for detailed form
    submitted_at: datetime            # UTC
    status: ApprovalStatus = ApprovalStatus.PENDING
    hr_override_tag: Optional[str] = None
    rejection_reason: Optional[str] = None
    approved_by: Optional[str] = None
    idempotency_key: str = ""
```


#### Session and Auth Models (Portal Domain)
```python
@dataclass
class Session:
    id: str                           # UUID4 token
    tenant_id: str
    employee_id: str
    email: str
    role_ids: list[str]
    created_at: datetime
    last_activity: datetime
    is_active: bool = True

@dataclass(frozen=True)
class MagicLink:
    token: str                        # Cryptographically random (secrets.token_urlsafe)
    email: str
    created_at: datetime
    expires_at: datetime              # created_at + 10min (employee) or 15min (HR)
    used: bool = False
```

#### Reconciliation Models
```python
class FlagColor(str, Enum):
    RED = "red"           # Variance < -threshold per review period
    AMBER = "amber"       # Variance > +threshold per review period
    GREEN = "green"       # Within threshold range per review period

class ReviewPeriodType(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"

@dataclass(frozen=True)
class ReviewPeriod:
    period_type: ReviewPeriodType
    start_date: date
    end_date: date
    tenant_id: str

@dataclass(frozen=True)
class PeriodVarianceResult:
    employee_id: str
    review_period: ReviewPeriod
    manual_hours: float              # From clock entries across the period
    tracked_hours: float             # From activity log (Online entries * 5min) within work schedule
    exception_hours: float           # From approved exceptions only
    auto_exempt_hours: float         # Idle periods <= Auto_Exempt_Threshold (not counted against employee)
    unmarked_idle_hours: float       # Idle > threshold, no exception marked
    variance: float                  # round(manual - (tracked + exception + auto_exempt), 1)
    flag: FlagColor
    flag_label: Optional[str]        # "Potential timesheet padding" | "Unclaimed hours detected"
    data_complete: bool              # False if data missing for >50% of expected working days
    threshold_used: float            # The variance flag threshold that was applied

@dataclass(frozen=True)
class DailyVarianceDetail:
    """Drill-down detail for a single day within a review period."""
    date: date
    manual_hours: float
    tracked_hours: float
    exception_hours: float
    auto_exempt_hours: float
    variance: float
    # No flag per day — flags are period-level only

@dataclass(frozen=True)
class LocationCheckResult:
    employee_id: str
    date: date
    declared_location: LocationType
    mismatch_percentage: float       # 0.0 to 100.0
    is_mismatch: bool                # True if > 50%
    tracker_data_available: bool
    total_entries: int
    conflicting_entries: int
```

#### RBAC Models
```python
class Permission(str, Enum):
    VIEW_OWN_DATA = "view_own_data"
    VIEW_ALL_EMPLOYEE_DATA = "view_all_employee_data"
    VIEW_REPORTS = "view_reports"
    MANAGE_EMPLOYEES = "manage_employees"
    APPROVE_EXCEPTIONS = "approve_exceptions"
    MANAGE_CONFIGURATION = "manage_configuration"
    VIEW_AUDIT_LOG = "view_audit_log"
    VIEW_INCIDENTS = "view_incidents"
    EXPORT_DATA = "export_data"

@dataclass
class Role:
    id: str
    tenant_id: str
    name: str                        # e.g., "HR Administrator"
    permissions: set[Permission]
    is_default: bool = False         # System-defined role
    report_types: list[str] = None   # Specific reports this role can view
```

#### Audit and Incident Models
```python
@dataclass(frozen=True)
class AuditEntry:
    id: str
    tenant_id: str
    timestamp: datetime              # UTC
    actor_id: str                    # Employee or admin ID
    action_type: str                 # login, clock_in, exception_submit, etc.
    target_resource: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    source_ip: str = ""
    session_id: str = ""

class IncidentSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class IncidentStatus(str, Enum):
    OPEN = "Open"
    INVESTIGATING = "Investigating"
    RESOLVED = "Resolved"

@dataclass
class Incident:
    id: str
    tenant_id: str
    timestamp: datetime
    severity: IncidentSeverity
    event_type: str                  # "integrity_violation", "clock_drift", etc.
    affected_employee_id: Optional[str]
    description: str
    status: IncidentStatus = IncidentStatus.OPEN
    investigation_notes: list[str] = None
```


#### Configuration Models
```python
@dataclass
class TenantConfig:
    tenant_id: str
    idle_threshold_minutes: int = 10          # Range: 5-60
    auto_exempt_threshold_minutes: int = 30   # Range: 15-120 (idle <= this is auto-exempt, no notification)
    review_period: str = "weekly"             # "weekly" | "fortnightly" | "monthly"
    variance_flag_threshold: float = 3.0      # Range: 1.0-10.0 hours per review period (per week)
    auto_clock_out_time: str = "23:00"        # Range: 20:00-23:59
    heartbeat_interval_minutes: int = 30      # Range: 15-120
    magic_link_expiry_minutes: int = 10       # Range: 5-30
    session_timeout_minutes: int = 30         # Range: 15-120
    data_retention_days: int = 180
    surveillance_notice_period_days: int = 14
    self_correction_notification_enabled: bool = True   # R53: notify employee at 75% through period
    transparency_report_enabled: bool = True            # R57: end-of-period report to employee
    transparency_report_lead_hours: int = 24            # Hours before HR review goes live
    default_work_pattern: str = "standard"              # Default for new employees
    positive_reinforcement_threshold: int = 3           # Consecutive clean periods for badge

@dataclass
class WhiteLabelConfig:
    tenant_id: str
    logo_url: Optional[str] = None
    company_name: str = "Hybrid Timesheet"
    primary_color: str = "#1a73e8"
    secondary_color: str = "#5f6368"
```

### SQLite Schema (Local_DB - WAL Mode)

```sql
-- Pragma for WAL mode (set on database open)
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE log_entries (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,              -- ISO 8601 UTC
    employee_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Online', 'Idle')),
    location TEXT NOT NULL CHECK(location IN ('office', 'home')),
    hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    synced INTEGER DEFAULT 0,
    integrity_flag TEXT,
    time_drift_flag TEXT,
    detection_error TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE sync_queue (
    id TEXT PRIMARY KEY,
    batch_date TEXT NOT NULL,             -- Date of the batch
    payload TEXT NOT NULL,                -- JSON serialized batch
    created_at TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT
);

CREATE TABLE heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT
);

CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX idx_log_entries_synced ON log_entries(synced);
CREATE INDEX idx_log_entries_timestamp ON log_entries(timestamp);
CREATE INDEX idx_sync_queue_created ON sync_queue(created_at);
```

### Google Sheets Schema (Central Store)

| Sheet Name | Columns |
|-----------|---------|
| `employees` | tenant_id, employee_id, full_name, email, role_ids, timezone, work_schedule, work_pattern_type, work_pattern_blocks, status, locale, created_at, deactivated_at, consecutive_clean_periods |
| `activity_log` | tenant_id, employee_id, date, timestamp, status, location, integrity_flag, time_drift_flag, synced_at |
| `clock_entries` | tenant_id, employee_id, clock_in_time, clock_out_time, declared_location, auto_closed, date, idempotency_key |
| `exceptions` | tenant_id, employee_id, date, category, source, ai_tag, duration_minutes, comment, submitted_at, status, hr_override_tag, rejection_reason, approved_by, idempotency_key |
| `heartbeats` | tenant_id, employee_id, timestamp |
| `sessions` | tenant_id, session_id, employee_id, email, created_at, last_activity, is_active |
| `magic_links` | tenant_id, token, email, created_at, expires_at, used |
| `audit_log` | tenant_id, id, timestamp, actor_id, action_type, target_resource, previous_value, new_value, source_ip, session_id |
| `incidents` | tenant_id, id, timestamp, severity, event_type, affected_employee_id, description, status, investigation_notes |
| `roles` | tenant_id, role_id, name, permissions, is_default, report_types |
| `config` | tenant_id, key, value, updated_by, updated_at, previous_value |
| `surveillance_notices` | tenant_id, version, content, effective_date, issued_at |
| `notice_acknowledgements` | tenant_id, employee_id, notice_version, acknowledged_at |
| `work_schedules` | tenant_id, employee_id, pattern_type, blocks_json, effective_from, updated_at |
| `transparency_reports` | tenant_id, employee_id, review_period_start, review_period_end, delivered_at, content_json |
| `self_correction_notifications` | tenant_id, employee_id, review_period_start, sent_at, running_variance |


## Visual Design System (Rhythm Brand Identity)

### Design Philosophy

The Rhythm visual identity is intentionally warm, organic, and human — designed to feel like a wellness tool rather than surveillance software. Every visual decision prioritizes employee comfort: rounded corners reduce visual tension, the sage-and-amber palette evokes nature rather than corporate coldness, and generous whitespace creates breathing room.

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--rhythm-primary` | `#5B8C5A` | Sage green — primary actions, badges, active states |
| `--rhythm-secondary` | `#E8A838` | Warm amber — secondary actions, highlights, warnings |
| `--rhythm-background` | `#FAFAF7` | Soft off-white — page background, card backgrounds |
| `--rhythm-text` | `#2D3436` | Dark charcoal — body text, headings |
| `--rhythm-accent` | `#E17055` | Soft coral — destructive actions, error states, attention |

**High-Contrast Mode Overrides** (detected via `prefers-contrast: more`):
| Token | High-Contrast Value |
|-------|-------------------|
| `--rhythm-primary` | `#3D6B3A` (darker green, 7:1 ratio) |
| `--rhythm-secondary` | `#B87E1A` (darker amber) |
| `--rhythm-background` | `#FFFFFF` (pure white) |
| `--rhythm-text` | `#000000` (pure black) |
| `--rhythm-accent` | `#C0392B` (deeper red, 4.5:1 ratio) |

### Typography

| Role | Font | Weight | Size |
|------|------|--------|------|
| Headings (H1-H3) | Nunito | 700 (Bold) | 28px / 24px / 20px |
| Body text | Inter | 400 (Regular) | 16px |
| UI labels / buttons | Inter | 500 (Medium) | 14px (minimum) |
| Legal fine print | Inter | 400 | 12px (minimum, only for legal) |
| Captions / secondary | Inter | 400 | 14px |

**Font loading strategy**: `font-display: swap` to prevent invisible text during load.

### Spacing System (8px Grid)

All spacing values are multiples of 8px:

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px | Icon margins (exception to 8px grid) |
| `--space-sm` | 8px | Tight element gaps, inline spacing |
| `--space-md` | 16px | Standard component padding |
| `--space-lg` | 24px | Section gaps, card padding |
| `--space-xl` | 32px | Page section separators |
| `--space-2xl` | 48px | Major layout breaks |

### Border Radius and Shape

| Element | Radius |
|---------|--------|
| Cards | 8px |
| Buttons | 8px |
| Input fields | 8px |
| Modals | 12px |
| Badges/chips | 16px (pill) |
| Avatars | 50% (circle) |

### Micro-Animations

All animations are capped at **300ms** maximum duration and respect `prefers-reduced-motion`:

```css
/* Animation tokens */
:root {
  --duration-instant: 100ms;
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;  /* maximum allowed */
  --ease-out: cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

/* Reduced motion override */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0ms !important;
    transition-duration: 0ms !important;
  }
}
```

| Interaction | Duration | Easing |
|-------------|----------|--------|
| Button hover/focus | 100ms | ease-out |
| Clock-in confirmation | 200ms | ease-out (subtle pulse) |
| Toast appearance | 200ms | ease-out (slide in) |
| Page transitions | 150ms | ease-out (fade) |
| Form submission feedback | 200ms | ease-out |

### Gradio Theming and CSS Strategy

The Portal runs on Gradio, which provides a `gr.themes.Base` class for custom theming. The Rhythm design system is applied through:

**1. Custom Gradio Theme Class:**
```python
import gradio as gr

class RhythmTheme(gr.themes.Base):
    def __init__(self):
        super().__init__(
            primary_hue=gr.themes.Color(
                c50="#f0f7f0", c100="#d4e8d4", c200="#b8d9b8",
                c300="#8cbf8c", c400="#6ba66b", c500="#5B8C5A",
                c600="#4a7349", c700="#3a5a39", c800="#2a4129", c900="#1a2819"
            ),
            secondary_hue=gr.themes.Color(
                c50="#fef9f0", c100="#fcecd4", c200="#f9deb8",
                c300="#f5c88c", c400="#f0b260", c500="#E8A838",
                c600="#c48e2e", c700="#9f7324", c800="#7a581a", c900="#553d10"
            ),
            neutral_hue=gr.themes.Color(
                c50="#FAFAF7", c100="#f0f0ed", c200="#e0e0dd",
                c300="#c0c0bd", c400="#8a8a87", c500="#5f5f5c",
                c600="#454543", c700="#2D3436", c800="#1a1c1d", c900="#0d0e0f"
            ),
            font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
            font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
        )
        self.set(
            body_background_fill="#FAFAF7",
            body_text_color="#2D3436",
            button_primary_background_fill="#5B8C5A",
            button_primary_text_color="#FFFFFF",
            button_secondary_background_fill="#E8A838",
            block_radius="8px",
            input_radius="8px",
            button_large_radius="8px",
            spacing_lg="24px",
            spacing_md="16px",
            spacing_sm="8px",
        )
```

**2. Custom CSS Overrides** (injected via `gr.Blocks(css=...)`):

The custom CSS file (`src/portal/static/rhythm.css`) handles:
- `prefers-reduced-motion` media query disabling all animations
- `prefers-contrast: more` media query applying high-contrast token overrides
- 8px grid enforcement for all margin/padding
- Focus indicator styling (2px solid outline, 3:1 contrast)
- Minimum touch target sizing (44x44px on mobile)
- Custom scrollbar styling consistent with Rhythm palette

**3. Component-Level Styling:**

Each Gradio component gets Rhythm styling via `elem_classes` and the theme:
```python
gr.Button("Clock In", variant="primary", elem_classes=["rhythm-action-btn"])
gr.Textbox(label="Notes", elem_classes=["rhythm-input"])
```


## Copywriting Architecture

### Overview

All user-facing text is externalized into a dedicated copy resource system, separate from locale/translation files. This allows the UX writing team to iterate on tone and messaging without touching code, and keeps the warm, human voice consistent across the entire application.

### File Structure

```
src/portal/
├── copy/
│   ├── __init__.py              # CopyManager: loads and renders templates
│   ├── en.copy.yaml             # English copy resource file (source of truth)
│   ├── tone_guidelines.md       # Editorial voice and tone documentation
│   └── templates/
│       ├── greetings.yaml       # Welcome messages, clock-in/out confirmations
│       ├── errors.yaml          # Error messages (empathy-first pattern)
│       ├── warnings.yaml        # Warning/heads-up messages
│       ├── empty_states.yaml    # Encouragement for empty views
│       ├── notifications.yaml   # Self-correction, transparency report, toast
│       ├── privacy.yaml         # Privacy notice and surveillance disclosure
│       └── hr_neutral.yaml      # HR dashboard factual language
├── locales/
│   ├── en.yaml                  # Structural translations (labels, nav, dates)
│   ├── ar.yaml                  # Arabic translations
│   └── ...                      # Other locale files
```

### Separation of Concerns: Copy vs. Locale

| Concern | File | Purpose | Who Edits |
|---------|------|---------|-----------|
| **Tone & messaging** | `copy/en.copy.yaml` | Human-readable messages, warmth, personality | UX Writer |
| **Structural labels** | `locales/en.yaml` | Navigation items, form labels, table headers | Translator |
| **Templates with variables** | `copy/templates/*.yaml` | Message templates with `{first_name}` placeholders | UX Writer |

This separation means a translator can localize labels without needing to understand the tone guidelines, and a UX writer can refine messaging without touching navigation structure.

### Copy Resource File Format

```yaml
# copy/en.copy.yaml
greetings:
  home_welcome: "Welcome back, {first_name}"
  clock_in_success: "You're clocked in. Have a great day!"
  clock_out_success: "You're off the clock. See you next time!"
  exception_submitted: "Exception logged, thanks for letting us know."
  exception_approved: "Good news — your exception was approved."

errors:
  generic_500: "Something went wrong on our end. Your data is safe — try again in a moment."
  session_expired: "Your session timed out. Let's get you back in."
  validation_failed: "A few things need fixing before we can save this."
  network_error: "We're having trouble connecting. Your data is safe locally — we'll sync when we can."

warnings:
  variance_employee: "Just a heads-up — your tracked hours are a bit below your claimed hours this week. Might want to mark any breaks you forgot."
  self_correction: "Hey {first_name}, you're a bit behind on tracked vs. claimed hours this period. No worries — you can log an exception to catch up."
  approaching_auto_close: "Still clocked in? We'll auto-close your session at {auto_close_time} if you forget."

empty_states:
  no_exceptions: "No exceptions this period — looks like smooth sailing!"
  no_flags: "All clear. Nice work, {first_name}."
  no_audit_results: "Nothing to show for those filters. Try widening your date range."
  no_notifications: "All quiet today. Enjoy your focus time."

notifications:
  self_correction_subject: "Quick check-in on your timesheet"
  transparency_report_subject: "Your timesheet summary for {period_label}"
  toast_idle_return: "Welcome back! What were you up to for the last {idle_minutes} minutes?"

hr_neutral:
  variance_detected: "Variance detected for review"
  flag_red: "Hours claimed exceed tracked + exceptions"
  flag_amber: "Tracked hours exceed claimed hours"
  location_mismatch: "Location mismatch detected"
  integrity_violation: "Data integrity flag"

privacy:
  notice_body: "We track whether you're active — never what you're doing. Your apps, files, and browsing are completely private."
  binary_only: "We only detect whether input activity occurred — we never record which applications you use, what websites you visit, or what content you view."
```

### CopyManager Implementation

```python
import yaml
from pathlib import Path
from typing import Optional

class CopyManager:
    """Loads and renders copy templates with variable substitution."""
    
    def __init__(self, copy_dir: Path, locale: str = "en"):
        self._copy: dict = self._load_copy(copy_dir, locale)
    
    def get(self, key: str, **kwargs) -> str:
        """Retrieve a copy string by dot-notation key, with variable substitution.
        
        Example: copy.get("greetings.home_welcome", first_name="Sarah")
        Returns: "Welcome back, Sarah"
        """
        template = self._resolve_key(key)
        return template.format(**kwargs) if kwargs else template
    
    def _load_copy(self, copy_dir: Path, locale: str) -> dict:
        """Load the copy YAML file for the given locale."""
        path = copy_dir / f"{locale}.copy.yaml"
        with open(path) as f:
            return yaml.safe_load(f)
    
    def _resolve_key(self, key: str) -> str:
        """Navigate nested dict by dot notation (e.g., 'greetings.home_welcome')."""
        parts = key.split(".")
        node = self._copy
        for part in parts:
            node = node[part]
        return node
```

### Tone Guidelines Summary

The `tone_guidelines.md` documents the editorial voice:

| Principle | Do | Don't |
|-----------|----|----|
| **Warm** | "Welcome back, Sarah" | "Employee ID: 4521 authenticated" |
| **Empathetic** | "Something went wrong on our end" | "Error 500: Internal Server Error" |
| **Supportive** | "Just a heads-up — your hours are a bit short" | "WARNING: Variance threshold exceeded" |
| **Celebratory** | "Nice — you're all set for the day!" | "Clock-in recorded at 09:02:31 UTC" |
| **Non-accusatory (HR)** | "Variance detected for review" | "Potential fraud identified" |
| **Plain (privacy)** | "We track whether you're active — never what you're doing" | "The system monitors input signal presence/absence exclusively" |

### Integration with Views

All Gradio view files use the CopyManager for user-facing text:

```python
# src/portal/views/employee_portal.py
class EmployeePortalView:
    def __init__(self, copy: CopyManager, ...):
        self._copy = copy
    
    def render_home(self, employee: Employee):
        greeting = self._copy.get(
            "greetings.home_welcome",
            first_name=employee.full_name.split()[0]
        )
        # ...
```


## Test Data Seeding

### Overview

The `scripts/seed_data.py` script generates realistic, comprehensive sample data for development, demos, and testing. It populates the Central Store (or JSON fixtures) with 10 employee personas covering all system scenarios.

### Script Architecture

```
scripts/
├── seed_data.py               # Main CLI entry point
├── seed/
│   ├── __init__.py
│   ├── personas.py            # 10 persona definitions with attributes
│   ├── activity_generator.py  # Generates 4 weeks of activity log entries
│   ├── clock_generator.py     # Generates clock-in/out entries per persona
│   ├── exception_generator.py # Generates exceptions with varying statuses
│   ├── audit_generator.py     # Generates realistic audit log entries
│   └── fixture_exporter.py    # Exports data to tests/fixtures/ as JSON
```

### CLI Interface

```bash
# Generate data for a specific tenant
python scripts/seed_data.py --tenant-id demo-tenant-001

# Export to JSON fixtures only (no Central Store write)
python scripts/seed_data.py --tenant-id test-tenant --fixtures-only

# Specify a custom seed for reproducibility
python scripts/seed_data.py --tenant-id demo-tenant-001 --seed 42
```

### Idempotency Strategy

The seed script is idempotent — running it multiple times produces the same result:

1. **Clear phase**: Delete all data for the specified `--tenant-id` from all sheets/tables
2. **Generate phase**: Deterministically generate all data using a fixed random seed
3. **Write phase**: Insert all generated records

Using a fixed `random.seed()` value ensures identical data on every run.

### Employee Personas (10)

| # | Persona | Schedule | Pattern | Expected Flag | Key Characteristics |
|---|---------|----------|---------|---------------|-------------------|
| 1 | Regular Employee (Sarah) | Hybrid | Standard (9-5) | GREEN | Clean variance, consistent patterns |
| 2 | Flexible Worker (Marcus) | Remote | Split (6-12, 18-21) | GREEN | Two work blocks, no issues |
| 3 | Remote-First (Priya) | Remote | Standard (9-5) | GREEN | 100% home, occasional office |
| 4 | New Hire (Alex) | Hybrid | Standard (9-5) | GREEN | Only 1 week of data (recently added) |
| 5 | Flagged Employee (Jordan) | Hybrid | Standard (9-5) | RED | Significant variance this period |
| 6 | HR Administrator (Rachel) | Office | Standard (9-5) | GREEN | Clocks in/out for themselves |
| 7 | Deactivated Employee (Tom) | Hybrid | Standard (9-5) | N/A | Historical data, status=inactive |
| 8 | Multi-Exception (Aisha) | Hybrid | Standard (9-5) | AMBER | Mix of approved, rejected, pending |
| 9 | Location Mismatch (Ben) | Hybrid | Standard (9-5) | GREEN* | Declares office, detected home >50% |
| 10 | Integrity Violation (Casey) | Remote | Standard (9-5) | N/A | Tampered hash chain flag |

### Activity Data Generation (4 Weeks)

For each persona, the generator creates activity log entries spanning 28 days:

```python
def generate_activity_for_persona(persona: Persona, weeks: int = 4) -> list[LogEntry]:
    """Generate realistic 5-minute interval activity entries.
    
    Strategy per persona type:
    - Regular: Online during 9-5 with 2-3 idle gaps (15-45 min) per day
    - Flexible: Online in declared blocks with minimal idle
    - Flagged: Patterns where manual hours significantly exceed tracked
    - New Hire: Only generate data for most recent 7 days
    - Deactivated: Full 4 weeks but deactivated_at set 2 weeks ago
    """
```

Each entry includes:
- Timestamp (aligned to 5-min boundary)
- Status (Online/Idle) matching persona pattern
- Location (office/home) matching persona work_schedule
- Valid hash chain (except Integrity Violation persona)
- Proper sync flag

### Fixture Directory Structure

```
tests/
├── fixtures/
│   ├── README.md                    # Documents fixture structure and usage
│   ├── personas.json                # All 10 employee records
│   ├── activity_log/
│   │   ├── regular_employee.json    # 4 weeks of activity for Sarah
│   │   ├── flexible_worker.json     # 4 weeks for Marcus (split schedule)
│   │   ├── flagged_employee.json    # 4 weeks for Jordan (high variance)
│   │   └── ...                      # One file per persona
│   ├── clock_entries/
│   │   ├── regular_employee.json
│   │   └── ...
│   ├── exceptions/
│   │   ├── multi_exception.json     # Aisha's approved/rejected/pending mix
│   │   └── ...
│   ├── audit_log.json               # Realistic admin actions
│   ├── config.json                  # Tenant configuration
│   └── expected_results/
│       ├── reconciliation.json      # Expected variance + flags per persona
│       └── location_mismatches.json # Expected mismatch flags
```

### Usage in Tests

```python
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> dict:
    """Load a JSON fixture file for use in tests."""
    with open(FIXTURES / name) as f:
        return json.load(f)

# In a unit test:
def test_reconciliation_flags_correctly():
    personas = load_fixture("personas.json")
    activity = load_fixture("activity_log/flagged_employee.json")
    expected = load_fixture("expected_results/reconciliation.json")
    # ... run reconciliation, assert flags match expected
```


## Enhanced Accessibility

### Overview

Accessibility is a first-class design concern, not a checkbox. The system targets **WCAG 2.0 AA** conformance verified through automated scanning (axe-core) integrated into the CI pipeline, supplemented by manual testing for flows that require screen reader verification.

### axe-core Integration in Playwright

axe-core runs as part of the Playwright E2E suite, scanning every page and interactive state:

```python
# tests/e2e/conftest.py
from axe_playwright_python.sync_playwright import Axe

@pytest.fixture
def axe(page):
    """Provide axe-core scanner for accessibility checks."""
    return Axe()

# tests/e2e/test_accessibility.py
def test_employee_home_accessibility(page, axe, authenticated_session):
    page.goto("/")
    results = axe.run(page)
    violations = [v for v in results["violations"]
                  if v["impact"] in ("critical", "serious")]
    assert violations == [], f"Accessibility violations: {violations}"
```

**Pages scanned**: Every page and modal state (clock-in, exception form, HR dashboard, settings, transparency report, empty states).

### CI Accessibility Gate

```yaml
# In .github/workflows/ci.yml
accessibility:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run Playwright with axe-core
      run: pytest tests/e2e/test_accessibility.py --browser chromium
    # Gate: any "critical" or "serious" violation fails the job
```

**Blocking rule**: If axe-core reports ANY violation with impact level "critical" or "serious", the CI job fails and deployment is blocked. "moderate" and "minor" violations are reported as warnings but do not block.

### High-Contrast Mode Detection

The Portal detects and responds to the user's OS contrast preference:

```css
/* Normal mode uses Rhythm palette */
:root {
  --rhythm-primary: #5B8C5A;
  --rhythm-text: #2D3436;
  /* ... */
}

/* High contrast mode overrides */
@media (prefers-contrast: more) {
  :root {
    --rhythm-primary: #3D6B3A;
    --rhythm-text: #000000;
    --rhythm-background: #FFFFFF;
    --rhythm-accent: #C0392B;
    /* All contrast ratios boosted to 7:1+ */
  }
  
  /* Ensure all borders are visible */
  button, input, .card {
    border: 2px solid currentColor;
  }
}
```

### ARIA Live Regions Strategy

Dynamic content updates are announced to assistive technologies via dedicated ARIA live regions:

| Content Type | ARIA Setting | Region Location | Example |
|-------------|-------------|-----------------|---------|
| Toast confirmations | `aria-live="polite"` | Top of page (hidden container) | "You're clocked in. Have a great day!" |
| Form validation errors | `aria-live="assertive"` | Adjacent to form | "Duration must be in 5-minute increments" |
| Status updates | `aria-live="polite"` | Status bar region | "Exception submitted — pending review" |
| Clock state changes | `aria-live="polite"` | Clock widget area | "Session started at 9:02 AM" |
| Error alerts | `aria-live="assertive"` | Alert container | "Something went wrong. Try again in a moment." |
| Badge earned | `aria-live="polite"` | Notification area | "Nice! You've earned the Great Standing badge." |

**Implementation in Gradio:**
```python
# ARIA live region container rendered once per page
gr.HTML(
    '<div role="status" aria-live="polite" id="rhythm-live-region" class="sr-only"></div>'
)
gr.HTML(
    '<div role="alert" aria-live="assertive" id="rhythm-alert-region" class="sr-only"></div>'
)

# JavaScript updates the live region content on dynamic events
# (Gradio's JS callback mechanism via gr.HTML + custom JS)
```

### Focus Management Approach

| Scenario | Focus Behavior |
|----------|----------------|
| Page load | Focus moves to main content heading (skip nav) |
| Modal opens | Focus trapped inside modal; moves to first interactive element |
| Modal closes | Focus returns to the element that triggered the modal |
| Toast appears | Focus stays where it is (toast announced via live region) |
| Form submission error | Focus moves to first invalid field |
| Navigation | Logical tab order follows visual layout (left-to-right, top-to-bottom) |
| Clock-in/out action | Focus stays on the action button (confirmation via live region) |

**Skip Navigation Link:**
```html
<a href="#main-content" class="skip-link">Skip to main content</a>
```

**Focus Indicators** (visible, meets 3:1 contrast):
```css
:focus-visible {
  outline: 2px solid var(--rhythm-primary);
  outline-offset: 2px;
  border-radius: 4px;
}
```

### Color Independence

All color-coded information includes a secondary non-color indicator:

| Status | Color | Secondary Indicator |
|--------|-------|-------------------|
| GREEN flag | Green (#5B8C5A) | Checkmark icon + "Clear" text label |
| AMBER flag | Amber (#E8A838) | Triangle icon + "Review" text label |
| RED flag | Red (#E17055) | Cross icon + "Flagged" text label |
| Online presence | Green dot | "Online" text label visible on hover/focus |
| Offline presence | Grey dot | "Offline" text label visible on hover/focus |
| Exception Approved | Green | Checkmark icon + "Approved" text |
| Exception Rejected | Red | Cross icon + "Rejected" text |
| Exception Pending | Amber | Clock icon + "Pending" text |

### Minimum Text Sizes

| Content Type | Minimum Size | Rationale |
|-------------|-------------|-----------|
| Body text | 16px | WCAG readability for body content |
| UI labels, buttons | 14px | Acceptable for UI chrome with good contrast |
| Legal fine print | 12px | Only for Terms/Privacy legal text |
| Never used | < 12px | Hard minimum — nothing smaller allowed |

### Touch Targets (Mobile)

All interactive elements on viewports <= 768px maintain a minimum tap target of **44 x 44 CSS pixels**:

```css
@media (max-width: 768px) {
  button, a, input[type="checkbox"], input[type="radio"],
  .interactive, [role="button"] {
    min-width: 44px;
    min-height: 44px;
  }
}
```

### Accessibility Statement

The project includes `docs/ACCESSIBILITY.md` with:
- **Conformance level**: WCAG 2.0 AA (target)
- **Testing methodology**: axe-core automated + Playwright keyboard tests + manual screen reader testing (NVDA on Windows, VoiceOver on macOS)
- **Known limitations**: Listed with target fix dates
- **Contact information**: How to report accessibility issues
- **Third-party components**: Gradio framework accessibility notes
- **Last review date**: Updated with each release

### Dedicated E2E Accessibility Test Scenarios

```python
# tests/e2e/test_accessibility_flows.py

def test_keyboard_only_clock_in(page, authenticated_session):
    """Full clock-in flow using only Tab, Enter, Space — no mouse."""
    # Tab to clock-in button, Enter to activate, verify confirmation

def test_keyboard_only_exception(page, authenticated_session):
    """Full exception submission using only keyboard."""
    # Tab through form fields, select category, submit

def test_keyboard_only_my_timesheet(page, authenticated_session):
    """Navigate My Timesheet view using only keyboard."""
    # Tab through period selector, daily breakdown, drill-down links

def test_screen_reader_announcements(page, authenticated_session):
    """Verify ARIA live regions announce dynamic content."""
    # Clock in, verify live region content updated

def test_focus_trap_modal(page, authenticated_session):
    """Verify focus is trapped in modal and returns on close."""
    # Open exception detail modal, Tab through, Escape, verify focus return

def test_skip_nav_link(page):
    """Verify skip-to-content link works."""
    # Tab once from page load, verify skip link focused, Enter, verify main content focused
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system - essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Clock-aligned boundary computation

*For any* arbitrary datetime, the computed next logging boundary SHALL be one of the 12 fixed 5-minute points within its hour (HH:00, HH:05, HH:10, ..., HH:55), and SHALL be the smallest such boundary that is greater than or equal to the input datetime.

**Validates: Requirements 1.3**

### Property 2: Activity-based status determination

*For any* sequence of activity events and any current time, the computed status SHALL be "Idle" if and only if the most recent continuous period with zero activity signals is greater than or equal to the configured idle threshold (default 10 minutes), and SHALL be "Online" otherwise.

**Validates: Requirements 1.4, 1.5**

### Property 3: Write retry bounded at 3 attempts

*For any* sequence of Local_DB write attempts for a single log entry, the entry SHALL be retried on subsequent cycles up to a maximum of 3 consecutive failed attempts, after which it is permanently discarded and never retried again.

**Validates: Requirements 1.8**

### Property 4: Location detection correctness

*For any* WiFi state (SSID, BSSID, or disconnected) and any office network list (including empty), the Location_Detector SHALL return "office" if and only if both the current SSID and BSSID exactly match an entry in the office network list; it SHALL return "home" in all other cases including no WiFi connection, empty office list, timeout, and config read failure.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 2.7**

### Property 5: SHA-256 hash chain integrity computation

*For any* ordered sequence of log entries, each entry's hash field SHALL equal SHA-256(serialized_entry_data || previous_entry_hash), forming a verifiable chain from the first entry forward. The chain SHALL be reproducible by recomputing all hashes sequentially.

**Validates: Requirements 4.4**

### Property 6: Hash chain tamper detection

*For any* valid hash chain of length N with one or more entries modified after initial computation, the verification function SHALL detect the first tampered entry and flag all entries from that point to the end of the chain as "Integrity Violation".

**Validates: Requirements 4.5, 4.6**

### Property 7: Hash chain recovery after incomplete write

*For any* valid hash chain followed by a single incomplete entry (partial write due to crash), the recovery function SHALL discard only the incomplete entry, start a new chain from the last fully-written valid entry, and SHALL NOT flag the incomplete entry as an integrity violation.

**Validates: Requirements 50.13**

### Property 8: Magic Link validity determination

*For any* Magic Link token with a given creation time, configured expiry duration (10 minutes for employees, 15 minutes for HR), current time, and usage state (used/unused), authentication SHALL succeed if and only if (current_time - created_at < expiry_duration) AND (token has not been previously used).

**Validates: Requirements 5.2, 5.3, 11.1, 11.5**

### Property 9: Session expiry after inactivity

*For any* authenticated session with a last_activity timestamp and any current time, the session SHALL be considered expired if and only if (current_time - last_activity) exceeds the configured session timeout (default 30 minutes).

**Validates: Requirements 5.5, 11.2**

### Property 10: Single active session per user invariant

*For any* sequence of session creation and invalidation operations for a given user (employee or HR administrator), at most one session SHALL be in the active state at any point in time. Creating a new session SHALL invalidate any existing active session for that user.

**Validates: Requirements 5.6, 5.7, 11.6**


### Property 11: Clock session state machine

*For any* employee at any point in time, the clock-in button SHALL be enabled if and only if no open session exists for that employee, and the clock-out button SHALL be enabled if and only if an open session exists. Attempting to clock-in while a session is open SHALL be rejected.

**Validates: Requirements 6.4, 6.5, 6.6**

### Property 12: Clock session duration calculation

*For any* valid clock-in timestamp and clock-out timestamp where clock_out > clock_in, the displayed session duration SHALL exactly equal (clock_out_time - clock_in_time).

**Validates: Requirements 6.3**

### Property 13: Auto-clock-out trigger

*For any* open clock-in session and any current time, the system SHALL automatically close the session with a clock-out timestamp equal to the configured auto-close time (default 23:00 in employee timezone) if and only if current_time >= auto_close_time AND the session was opened before auto_close_time on the same day.

**Validates: Requirements 6.7**

### Property 14: Input validation correctness

*For any* input value submitted to the Portal via the detailed Exception_Form, the validator SHALL accept the value if and only if it satisfies ALL applicable constraints: email fields against RFC 5322 format, duration fields as numeric values between 5 and 480 minutes and divisible by 5, text comment fields with length in [10, 500] characters, and category/location values are members of their defined allowed-value lists. Quick toast exceptions (submitted via Tracker notification) bypass form validation — they only require a valid category selection and the idle duration is auto-calculated from actual idle time.

**Validates: Requirements 7.2, 7.6, 7.7, 16.1**

### Property 15: Gemini Tagger skip conditions

*For any* exception submission, the Gemini_Tagger SHALL return "Unclassified" without calling the external API if: the comment text has fewer than 3 characters, OR the per-minute request count has reached 15, OR the daily request count has reached 1500, OR the API is unavailable/times out within 5 seconds.

**Validates: Requirements 8.4, 8.6, 8.7**

### Property 16: Gemini response validation

*For any* response string returned by the Gemini API, the system SHALL accept it as a valid classification if and only if it exactly matches one of the allowed category values: "Medical Break", "Client Meeting", "Hardware Issue", or "Personal Leave". Any other response SHALL result in a tag of "Unclassified".

**Validates: Requirements 39.3, 39.4**

### Property 17: Location mismatch detection

*For any* employee-day with a declared location of "office" and a set of Tracker-detected location entries during that session, the Reconciliation_Engine SHALL flag "Location Mismatch" if and only if the count of entries with detected location "home" divided by total entries exceeds 0.5 (50%).

**Validates: Requirements 9.1, 9.2**

### Property 18: Variance calculation and flag assignment (per review period)

*For any* employee and any review period (weekly/fortnightly/monthly) with manual claimed hours (M), tracked active hours within declared work schedule (T), total approved exception hours (E), and total auto-exempt idle hours (A, idle periods <= Auto_Exempt_Threshold), the variance SHALL equal round(M - (T + E + A), 1). The flag SHALL be RED ("Potential timesheet padding") when variance < -Variance_Flag_Threshold (default -3.0h per week, scaled proportionally for other periods), AMBER ("Unclaimed hours detected") when variance > +Variance_Flag_Threshold, and GREEN (no label) when within the threshold range. Only exceptions with status "Approved" SHALL be included in E. Single-day anomalies SHALL NOT trigger flags — only the aggregate period result determines the flag.

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.10, 34.6, 55.2**

### Property 19: NTP drift detection and timestamp correction

*For any* local system time (converted to UTC) and NTP authoritative time, the NTP_Validator SHALL flag "Clock Drift Detected" if and only if |local_UTC - NTP_time| > 2 minutes. When flagged, the Sync_Engine SHALL apply the offset (NTP_time - local_UTC) to all entry timestamps in the sync batch. When NTP is unreachable, sync SHALL proceed with local time marked "NTP Unavailable".

**Validates: Requirements 3.7, 14.2, 14.3, 14.4, 14.5**

### Property 20: Sync queue chronological ordering invariant

*For any* state of the sync queue, entries SHALL always be ordered by their original timestamp in ascending chronological order. A failed sync entry returned to the queue SHALL maintain this ordering. Entries SHALL be processed (popped) from the front of the queue only.

**Validates: Requirements 3.3, 3.8**


### Property 21: Reconciliation report filtering and sorting

*For any* set of reconciliation records and filter criteria (employee name substring match, review period selection, flag color), the returned results SHALL contain only records matching ALL active filters simultaneously, and SHALL be sorted by most recent review period first.

**Validates: Requirements 10.7**

### Property 22: RBAC permission enforcement

*For any* user with assigned roles and any requested action/view requiring a specific permission, access SHALL be granted if and only if at least one of the user's assigned roles contains the required permission in its permission set. A user with no matching permission SHALL be denied access regardless of how the request is made (UI or service layer).

**Validates: Requirements 11.3, 11.4, 35.3, 35.4, 35.5, 44.5**

### Property 23: Rate limiter enforcement

*For any* tracked entity (IP address or email) and configured limit (N requests per W-minute window), the rate limiter SHALL block requests if and only if the count of requests from that entity within the current window exceeds N. The window SHALL be a sliding window.

**Validates: Requirements 23.1, 23.2, 23.3, 23.4, 23.5, 23.6**

### Property 24: Structured JSON log entry completeness

*For any* operational event in the Tracker (startup, shutdown, sync attempt, heartbeat, activity state change, integrity violation, error), the emitted log entry SHALL be valid JSON containing ALL required fields: timestamp (ISO 8601), level, component, event_type, employee_id, message, and details.

**Validates: Requirements 18.1, 18.4, 18.5**

### Property 25: Log file rotation

*For any* sequence of log writes, the Tracker SHALL trigger file rotation when the active log file size reaches 5 MB, SHALL retain at most 5 rotated files, and SHALL overwrite the oldest rotated file when creating a 6th rotation.

**Validates: Requirements 18.6**

### Property 26: Heartbeat offline detection threshold

*For any* employee's last heartbeat timestamp and the current time, the HR_Dashboard SHALL display "Tracker Offline" if and only if (current_time - last_heartbeat_timestamp) exceeds 60 minutes.

**Validates: Requirements 18.3**

### Property 27: Circuit breaker state transitions

*For any* sequence of external service call results (success/failure) with timestamps, the circuit breaker SHALL transition from Closed to Open after 3 consecutive failures within 60 seconds, SHALL remain Open for 30 seconds (failing fast without attempting calls), SHALL transition to Half-Open after 30 seconds, and SHALL return to Closed on the next successful call in Half-Open state (or back to Open on failure).

**Validates: Requirements 44.3**

### Property 28: Exponential backoff retry delays

*For any* retry attempt number n (1-based, maximum 3), the delay before the nth retry SHALL be 4^(n-1) seconds (1s, 4s, 16s). After the 3rd failed retry, no further retries SHALL be attempted and the circuit breaker SHALL be triggered.

**Validates: Requirements 44.7**

### Property 29: Idempotency key deduplication

*For any* sequence of write operations (clock-in, clock-out, exception submission) sharing the same idempotency key, exactly one record SHALL be created in the Central Store. Subsequent submissions with the same key SHALL be acknowledged as successful without creating duplicate records.

**Validates: Requirements 50.9**

### Property 30: Configurable parameter validation

*For any* parameter change request, the system SHALL accept the new value if and only if it falls within the allowed range: Idle_Threshold [5-60 min], Auto_Exempt_Threshold [15-120 min], Review_Period [weekly/fortnightly/monthly], Variance_Flag_Threshold [1.0-10.0 hours per review period], Auto_Clock_Out_Time [20:00-23:59], Heartbeat_Interval [15-120 min], Magic_Link_Expiry [5-30 min], Session_Timeout [15-120 min].

**Validates: Requirements 22.4, 22.5**

### Property 31: SSID and BSSID output format validation

*For any* output string from the platform WiFi detection command, the Location_Detector SHALL accept the SSID only if it contains alphanumeric and standard characters, and SHALL accept the BSSID only if it matches the hexadecimal MAC address format (XX:XX:XX:XX:XX:XX). Malformed output SHALL be discarded with location defaulting to "home".

**Validates: Requirements 25.3, 25.4**

### Property 32: Timezone display conversion

*For any* UTC timestamp and any valid IANA timezone identifier, the displayed time SHALL equal the UTC timestamp converted to the specified timezone using standard timezone offset rules (including DST transitions).

**Validates: Requirements 21.1, 21.2, 21.4, 21.5**

### Property 33: Audit log entry completeness

*For any* auditable event (login, clock-in/out, exception submission, tag override, parameter change, role change), the generated Audit_Log entry SHALL contain all required fields: timestamp (UTC), actor_id, action_type, target_resource, source_ip, and session_id. The audit log SHALL be append-only with no entries modifiable or deletable.

**Validates: Requirements 26.1, 26.2, 26.3**

### Property 34: Auto-exempt idle threshold decision

*For any* idle period with a measured duration and the configured Auto_Exempt_Threshold (default 30 minutes, range 15-120), the system SHALL treat the idle period as auto-exempt (no notification displayed, excluded from variance) if and only if the idle duration is less than or equal to the threshold. When idle duration exceeds the threshold and Focus Mode is inactive, the system SHALL trigger a toast notification.

**Validates: Requirements 7.1, 7.3**

### Property 35: HR self-approval prohibition

*For any* exception submission where the submitter is an HR administrator, the system SHALL reject any approval action where the approver's Employee_ID equals the submitter's Employee_ID, regardless of the approver's role or permissions.

**Validates: Requirements 35.5, 35.8**

### Property 36: Presence indicator computation

*For any* employee's last heartbeat timestamp and the current time, the HR_Dashboard SHALL display "Online" (green dot) if and only if (current_time - last_heartbeat_timestamp) is less than or equal to 10 minutes, and "Offline" (grey dot) otherwise. This value SHALL NOT be persisted, logged, or included in any variance calculation.

**Validates: Requirements 52.1, 52.2**

### Property 37: Self-correction notification trigger and idempotency

*For any* employee, review period, and running variance computation at 75% period elapsed, the system SHALL send exactly one private self-correction notification if and only if: (a) the current date is at or past 75% of the review period, AND (b) the running variance exceeds the Variance_Flag_Threshold, AND (c) no self-correction notification has already been sent for this employee in this review period. The notification SHALL be private to the employee and not visible to HR.

**Validates: Requirements 53.1, 53.4, 53.7**

### Property 38: Positive reinforcement badge state

*For any* sequence of completed review period results for an employee, the "Great Standing" badge SHALL be displayed if and only if the most recent N consecutive review periods all have a GREEN flag (no variance flag), where N equals the configured positive_reinforcement_threshold (default 3). When a non-GREEN period occurs, the consecutive count SHALL reset to zero and the badge SHALL be removed without any punitive message.

**Validates: Requirements 54.1, 54.2, 54.3**

### Property 39: Work-schedule-aware variance counting

*For any* idle period timestamp and the employee's declared work schedule pattern (Standard/Split/Flexible/Custom), the idle period SHALL be counted toward variance calculations if and only if it falls within one of the employee's declared work schedule time blocks. Idle time outside declared work blocks SHALL be completely excluded. Activity recorded outside declared schedule blocks SHALL still count toward tracked active hours (not penalized).

**Validates: Requirements 55.2, 55.3, 55.5**

### Property 40: Focus mode recording invariant

*For any* sequence of activity and idle events with Focus Mode either active or inactive, the Local_DB log entries SHALL be identical regardless of Focus Mode state — Focus Mode SHALL only suppress toast notification display. When Focus Mode is active and an idle return event occurs that would normally trigger a notification, the idle period SHALL be automatically recorded as "Unmarked Idle". Focus Mode usage SHALL NOT be reported to HR or included in any HR-visible data.

**Validates: Requirements 56.4, 56.7, 56.9**

### Property 41: Transparency report delivery timing

*For any* review period with a configured end date and transparency_report_lead_hours (default 24), the Employee Transparency Report SHALL be delivered to the employee at a time that is at least transparency_report_lead_hours before the HR review data becomes visible in the HR_Dashboard. The HR review data SHALL NOT be accessible until after the report lead period has elapsed.

**Validates: Requirements 57.1, 57.2**

### Property 42: Drill-down daily breakdown aggregation consistency

*For any* review period and employee, the sum of all daily breakdown values (manual_hours, tracked_hours, exception_hours, auto_exempt_hours) SHALL equal the corresponding totals in the period-level PeriodVarianceResult. The drill-down SHALL return exactly one entry per working day in the review period.

**Validates: Requirements 10.9**

### Property 43: Personalized greeting and notification rendering

*For any* employee with a non-empty first name and any copy template containing a `{first_name}` placeholder (greetings, notifications, self-correction messages), the rendered output SHALL contain that employee's first name verbatim.

**Validates: Requirements 59.5, 60.7**

### Property 44: Animation duration bounded and reduced-motion compliance

*For any* animation or transition definition in the Rhythm theme, its duration SHALL be less than or equal to 300ms. Additionally, when the `prefers-reduced-motion: reduce` preference is active, the effective animation and transition duration for every element SHALL be 0ms.

**Validates: Requirements 59.7, 59.8**

### Property 45: Externalized copy resource completeness

*For any* user-facing string key referenced by a Portal view component, that key SHALL exist in the copy resource file (`en.copy.yaml` or templates) and SHALL NOT be a hardcoded string literal in the view source code.

**Validates: Requirements 60.8**

### Property 46: Seed data idempotency

*For any* number of consecutive executions of the seed script (N >= 1) with the same `--tenant-id` and `--seed` parameters, the resulting dataset in the Central Store SHALL be identical — same record count, same field values, no duplicates.

**Validates: Requirements 61.5**

### Property 47: Seed data temporal coverage per persona

*For any* seeded persona (except New Hire which has 7 days), the generated activity log SHALL span at least 28 calendar days with at least one entry per working day within that persona's declared work schedule pattern.

**Validates: Requirements 61.3**

### Property 48: ARIA live region announcement for dynamic content

*For any* dynamic content change in the Portal (toast confirmation, form validation error, status update, clock state change), the corresponding ARIA live region SHALL be updated with a non-empty text string describing the change, ensuring assistive technologies announce the update.

**Validates: Requirements 62.5**

### Property 49: Color-coded information has secondary indicator

*For any* UI element that conveys status information through color (flag colors red/amber/green, presence dots, approval status), a secondary non-color indicator (text label or icon with accessible name) SHALL be present and programmatically associated with the element.

**Validates: Requirements 62.7**


## Error Handling

### Error Classification Strategy

All subsystems implement structured error categorization per Requirement 50.14:

| Category | Behavior | Examples |
|----------|----------|----------|
| **Transient** | Retry automatically (exponential backoff: 1s, 4s, 16s) | Network timeout, rate limit (429), temporary unavailability |
| **Permanent** | Alert user immediately, no retry | Invalid credentials, permission denied, validation failure |
| **Fatal** | Log, alert admin, continue other subsystems | Corrupted state, unrecoverable config error |

### Tracker Error Handling

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| Local_DB write fails | Retain in memory, retry next 5-min cycle | Max 3 retries then discard (Property 3) |
| WiFi detection timeout (>5s) | Default to "home", log detection_error | Continue next interval |
| Office network config unreadable | Default to "home", log config error | Continue operation |
| NTP server unreachable (>5s) | Sync with local time, mark "NTP Unavailable" | Retry next sync cycle |
| Central Store unreachable at sync | Queue entries, retry next cycle | Retain up to 90 days; warn employee |
| Heartbeat fails | Silent retry next 30-min cycle | No employee notification |
| Hash chain integrity violation | Flag entries, start new chain | Continue logging (Property 6) |
| Incomplete entry after crash | Discard incomplete, start new chain | No integrity flag (Property 7) |
| Service registration fails | Retry 3x at 10s intervals | Log error if all fail |
| Unhandled exception in subsystem | Log + restart affected subsystem only | Other subsystems unaffected |

### Portal Error Handling

| Scenario | Behavior | Recovery |
|----------|----------|----------|
| Central Store unreachable (clock/exception) | Accept optimistically, queue for retry | Background sync with status indicator |
| Gemini API unavailable/timeout (>5s) | Tag as "Unclassified", proceed | Background reclassification when available |
| Gemini API rate limited (15/min or 1500/day) | Tag as "Unclassified", proceed | Automatic cooldown |
| Magic Link email delivery fails (>30s) | Display error, suggest retry | User retries |
| Input validation fails | Reject, retain form data, show field error | User corrects and resubmits |
| Session expired during form interaction | Preserve form data, redirect to login | Restore form after re-auth (Req 50.10) |
| Unauthorized access attempt | Deny + log in audit + increment incident counter | No retry allowed |
| Concurrent modification conflict | Detect conflict, show current state | User re-confirms action |
| Hugging Face cold start | Show branded loading screen | Auto-resolves when container wakes |
| Unhandled Gradio exception | Global error boundary catches, logs stack trace | Show friendly error page with "Return to Home" |
| Circuit breaker OPEN | Fail fast without attempting call | Follow graceful degradation (Req 15) |

### Graceful Degradation Summary

| Service Down | Tracker Behavior | Portal Behavior |
|-------------|-----------------|-----------------|
| Google Sheets | Queue locally, retry at next cycle | Accept optimistically, retry in background |
| Gemini API | N/A | Tag "Unclassified", proceed, reclassify later |
| NTP Server | Sync with local time + notation | N/A |
| Email Service | N/A | Show delivery error, suggest retry |
| Internet (full) | Continue logging to SQLite indefinitely | Show "Offline" indicator, preserve local state |

### Design Principles

1. **Never lose data**: All Tracker failures result in local retention and retry
2. **Never block the employee**: All external service failures have immediate graceful fallbacks
3. **Transparent to HR**: All anomalies (drift, integrity violations, missing data) are visibly flagged
4. **Fail-safe defaults**: Unknown location -> "home"; unknown time -> local time with notation
5. **Subsystem isolation**: One subsystem crash doesn't take down the whole application
6. **Idempotent retries**: Duplicate submissions produce exactly one record (idempotency keys)


## Testing Strategy

### Dual Testing Approach

The project uses complementary testing strategies:
- **Property-based tests** (Hypothesis): Verify universal invariants across all valid inputs (49 properties)
- **Unit tests** (pytest): Verify specific examples, edge cases, integration points
- Together they provide comprehensive coverage without over-testing any single aspect.

### Property-Based Tests (Hypothesis)

**Library**: Hypothesis (Python)

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with: `# Feature: fraud-proof-hybrid-timesheet, Property {N}: {title}`
- All property tests execute in under 45 seconds total on CI

**Property Test Groups**:

| Group | Properties | Domain |
|-------|-----------|--------|
| Time Logic | 1, 2, 9, 12, 13, 26, 32 | Clock alignment, idle detection, session expiry, duration, auto-close, heartbeat, timezone |
| Data Integrity | 5, 6, 7, 20, 29 | Hash chain, tamper detection, recovery, queue ordering, idempotency |
| Validation | 4, 14, 15, 16, 30, 31 | Location match, input validation, Gemini skip, response validation, params, SSID format |
| Reconciliation | 17, 18, 21, 39, 42 | Location mismatch, periodic variance + flags, filtering/sorting, work-schedule-aware counting, drill-down aggregation |
| Auth and Access | 8, 10, 22, 23, 35 | Magic link validity, single session, RBAC, rate limiting, HR self-approval prohibition |
| Session State | 11 | Clock-in/out button state machine |
| Logging | 24, 25 | JSON structure, file rotation |
| Resilience | 3, 19, 27, 28 | Write retry, NTP drift, circuit breaker, exponential backoff |
| Audit | 33 | Audit entry completeness and append-only invariant |
| Notification & Wellness | 34, 37, 38, 40, 41 | Auto-exempt threshold, self-correction trigger, positive reinforcement badge, focus mode invariant, transparency report timing |
| Presence | 36 | Online/offline indicator computation |
| Brand & Copy | 43, 44, 45 | Personalization, animation bounds, externalized copy |
| Seed Data | 46, 47 | Idempotency, temporal coverage |
| Accessibility | 48, 49 | ARIA live regions, color independence |

### Unit Tests (pytest - Example-Based)

Focus on specific scenarios that property tests don't cover well:

**Tracker Unit Tests:**
- Service registration success/failure sequences
- Sleep/wake cycle handling
- Midnight sync trigger timing
- Heartbeat scheduling
- Platform-specific adapter output parsing (mock subprocess)
- Log rotation file naming convention
- Toast notification display (4 category buttons present)
- Toast auto-dismiss after 5 minutes
- Toast dismiss records "Unmarked Idle"
- Focus Mode toggle activation/deactivation from system tray
- Focus Mode duration presets (1h, 2h, 3h, 4h)
- Focus Mode system tray icon change indicator
- Focus Mode early termination

**Portal Unit Tests:**
- Magic Link email template content
- Clock-in/out UI confirmation messages
- Auto-close at 23:00 with correct timezone
- Exception form category dropdown values
- Quick toast exception → ExceptionRecord mapping
- Detailed Exception_Form → ExceptionRecord mapping with AI tag
- Exception form note about quick exceptions vs detailed form
- HR dashboard flag color CSS rendering
- HR dashboard drill-down view rendering
- HR dashboard presence indicator (green/grey dot display)
- HR dashboard: presence NOT stored in audit log
- HR administrator clock-in/out for themselves (same controls as employee)
- HR self-approval rejection error message
- HR exception stays "Pending" when only one HR admin exists
- Work schedule pattern CRUD (Standard, Split, Flexible, Custom)
- Work schedule changes take effect next calendar day
- Default work pattern applied to new employees
- Self-correction notification message format and friendly language
- Self-correction notification direct link to Exception_Form
- Positive reinforcement "Great Standing" badge display/removal
- Encouraging message after clean period
- No leaderboard or gamification elements in wellness
- Transparency Report content structure and friendly language
- Transparency Report deadline messaging
- Transparency Report: HR cannot see employee warning status
- White-label branding application
- Locale detection and formatting per locale
- RTL layout activation for Arabic
- Accessibility: ARIA attributes presence
- Error message format (plain language + reference code)
- Kill switch activation/deactivation behavior
- Incident severity auto-classification
- Surveillance notice: updated privacy text re presence indicator and app tracking
- Privacy notice includes "binary active/idle only" statement (R58)
- No window title/app name/URL in any stored data model
- Rhythm theme applied: correct primary (#5B8C5A), secondary (#E8A838), background (#FAFAF7) colors
- Default product name "Rhythm" when no white-label override configured
- Border-radius of 8px on cards, buttons, inputs in theme
- Inter/Nunito font-family in theme configuration
- 8px grid spacing tokens (all multiples of 8)
- Micro-animation durations all <= 300ms
- prefers-reduced-motion CSS disables all animations
- High-contrast mode overrides applied when prefers-contrast: more
- "Great Standing" badge uses leaf/pulse icon (not trophy)
- CopyManager renders templates with correct variable substitution
- Copy resource file loads all expected keys without KeyError
- Error messages follow empathy-first pattern (no raw error codes)
- HR dashboard messages use neutral language (no accusatory tone)
- Copy resource file separate from locale translation files
- Seed script creates exactly 10 personas with correct attributes
- Seed script generates 4 weeks of data (28 days) per persona
- Seed script idempotent: second run produces identical data
- Seed script respects --tenant-id parameter (all records scoped)
- Seed script: "Flagged Employee" produces RED flag on reconciliation
- Seed script: "Regular Employee" produces GREEN flag on reconciliation
- Seed script: "Location Mismatch Employee" triggers mismatch detection
- Seed script: "Integrity Violation Employee" has tampered hash chain
- JSON fixtures in tests/fixtures/ match seed script output
- axe-core integration detects intentional WCAG violation (test harness)
- Focus indicators: 2px solid outline with >= 3:1 contrast ratio
- Touch targets: all interactive elements >= 44x44px on mobile viewport
- ARIA live regions update on clock-in/out, exception submit, validation error
- Skip navigation link present and functional
- Focus trap active in modal dialogs
- Color-coded flags include text labels and icons (not color-only)
- Minimum font size: body 16px, labels 14px, legal 12px
- Accessibility statement document exists with required sections

### Integration Tests

**External Service Integration** (using dedicated test accounts, wiped after each CI run):

| Service | Tests |
|---------|-------|
| Google Sheets API | Read, write, batch write, timeout (mocked), rate limit (429 response), auth failure |
| Gemini 2.0 Flash API | Classification success, timeout, rate limit, malformed response, prompt injection attempts |
| Email Service (Mailtrap) | Magic link generation, send success, send failure, token in email body |
| NTP (mock server) | Query success, timeout, unreachable, drift scenarios |
| SQLite | Write, read, concurrent access (WAL mode), corruption recovery, large queue |

**Platform Integration** (CI matrix: Windows + macOS):
- `netsh wlan show interfaces` output parsing (Windows)
- `system_profiler SPAirPortDataType` output parsing (macOS)
- Windows Service registration/unregistration
- macOS LaunchDaemon plist installation

### End-to-End Tests (Playwright)

**Complete user flows** (staging environment, max 300s total):

1. Employee login via Magic Link -> click link -> authenticated session
2. Clock-in (select location) -> Clock-out -> verify duration displayed
3. Exception submission -> AI tag assigned -> appears in HR dashboard
4. HR reconciliation review -> flags visible -> filter by color -> drill-down into daily view
5. Employee lifecycle: Add employee -> login -> deactivate -> login blocked
6. Auto-clock-out at 23:00 (time-mocked)
7. Keyboard navigation (Tab through all interactive elements)
8. Screen reader compatibility (ARIA announcements)
9. Mobile viewport (375px width) -> all elements operable
10. Session expiry during form -> re-login -> form data preserved
11. HR admin clocks in/out for themselves -> appears in reconciliation view
12. HR admin attempts to approve own exception -> rejected with error
13. Work schedule update (Standard -> Split) -> verify takes effect next day
14. Self-correction notification triggers at 75% period (time-mocked)
15. Positive reinforcement badge appears after 3 clean periods (data-seeded)
16. Transparency Report delivery -> verify employee sees before HR review
17. Presence indicator shows green dot for recently-active employee
18. Focus Mode: activate from system tray -> verify no toast during idle -> deactivate -> verify toast resumes
19. Accessibility: full axe-core scan of employee home, clock-in, exception form, HR dashboard — zero critical/serious violations
20. Accessibility: keyboard-only clock-in flow (Tab, Enter, Space — no mouse)
21. Accessibility: keyboard-only exception submission flow
22. Accessibility: focus trap in exception detail modal, focus return on Escape
23. Accessibility: ARIA live regions announce clock-in confirmation and validation errors
24. Rhythm branding: default theme colors visible, rounded corners on cards/buttons
25. Seed data: run seed script -> verify HR dashboard shows all 10 personas with expected flags

### Architecture Boundary Tests (import-linter)

Enforced rules:
- `src.tracker.domain` SHALL NOT import from `src.tracker.adapters`
- `src.portal.domain` SHALL NOT import from `src.portal.adapters`
- `src.tracker` SHALL NOT import from `src.portal` (and vice versa)
- No circular dependencies within any bounded context
- Shared kernel (`src.shared`) SHALL NOT import from either domain

### Security Tests

- All input validation rules from Requirement 16 (fuzz with invalid inputs)
- No secrets in source code (grep for API key patterns)
- HTTPS enforcement (connect without TLS -> rejected)
- Rate limiting blocks at configured limits
- Command injection prevention (craft malicious SSID/BSSID values)
- Prompt injection attempts (8 adversarial inputs from Requirement 39.8)
- RBAC bypass attempts (access HR endpoints with employee token)
- Audit log immutability (attempt delete/update -> rejected)

### Security Scanning (CI Pipeline)

| Tool | Stage | Blocking |
|------|-------|----------|
| Snyk Dependency Scan | Every PR | HIGH/CRITICAL block merge |
| Snyk Code (SAST) | Every PR | HIGH/CRITICAL block merge |
| OWASP ZAP (DAST) | Post-staging deploy | HIGH/CRITICAL block promotion |
| mypy (strict mode) | Every PR | Any type error blocks merge |
| import-linter | Every PR | Any violation blocks merge |
| Ruff (linting) | Every PR | Any error blocks merge |
| axe-core (accessibility) | Every PR | Critical/Serious violations block merge |

### Test Environment Strategy

| Tier | Dependencies | Data |
|------|-------------|------|
| Unit + Property | All mocked (freezegun, responses, pytest-mock) | Generated by Hypothesis |
| Integration | Dedicated test Google Sheet, Mailtrap, mock NTP | Wiped after each CI run |
| E2E | Staging HF Space + staging Google Sheet | Seeded test data, reset between runs |

### CI/CD Pipeline Stages

```mermaid
graph LR
    PR[Pull Request] --> L[Ruff Lint]
    L --> T[Type Check<br/>mypy strict]
    T --> U[Unit Tests<br/>pytest]
    U --> P[Property Tests<br/>Hypothesis]
    P --> A[Architecture<br/>import-linter]
    A --> S[Security Scan<br/>Snyk]
    S --> I[Integration Tests]
    I --> D[Deploy Staging]
    D --> E[E2E Tests<br/>Playwright]
    E --> Z[DAST<br/>OWASP ZAP]
    Z --> PROD[Deploy Production]
```

