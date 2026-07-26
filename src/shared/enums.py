"""Shared kernel enums used across Tracker and Portal bounded contexts."""

from enum import Enum


class ActivityStatus(str, Enum):
    """Binary activity status for an employee during a time interval."""

    ONLINE = "Online"
    IDLE = "Idle"


class LocationType(str, Enum):
    """Detected work location based on WiFi network matching."""

    OFFICE = "office"
    HOME = "home"


class FlagColor(str, Enum):
    """Variance flag severity for reconciliation reports."""

    RED = "red"
    AMBER = "amber"
    GREEN = "green"


class Permission(str, Enum):
    """Granular permissions assignable to RBAC roles."""

    VIEW_OWN_DATA = "view_own_data"
    VIEW_ALL_EMPLOYEE_DATA = "view_all_employee_data"
    VIEW_REPORTS = "view_reports"
    MANAGE_EMPLOYEES = "manage_employees"
    APPROVE_EXCEPTIONS = "approve_exceptions"
    MANAGE_CONFIGURATION = "manage_configuration"
    VIEW_AUDIT_LOG = "view_audit_log"
    VIEW_INCIDENTS = "view_incidents"
    EXPORT_DATA = "export_data"


class ExceptionCategory(str, Enum):
    """Categories for idle exception reporting."""

    MEDICAL_BREAK = "Medical Break"
    CLIENT_MEETING = "Client Meeting"
    HARDWARE_ISSUE = "Hardware Issue"
    PERSONAL_LEAVE = "Personal Leave"


class ApprovalStatus(str, Enum):
    """Approval workflow states for exception reports."""

    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class WorkPatternType(str, Enum):
    """Types of work schedule patterns supported."""

    STANDARD = "standard"
    SPLIT = "split"
    FLEXIBLE = "flexible"
    CUSTOM = "custom"


class EmployeeStatus(str, Enum):
    """Employee lifecycle status."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class CircuitState(str, Enum):
    """Circuit breaker states for external service calls."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ErrorCategory(str, Enum):
    """Classification of errors for retry/handling strategy."""

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    FATAL = "FATAL"


class IncidentSeverity(str, Enum):
    """Security incident severity levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class IncidentStatus(str, Enum):
    """Security incident lifecycle states."""

    OPEN = "Open"
    INVESTIGATING = "Investigating"
    RESOLVED = "Resolved"


class ReviewPeriodType(str, Enum):
    """Configurable reconciliation review period types."""

    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"


class ExceptionSource(str, Enum):
    """Source of an exception report submission."""

    TOAST_QUICK = "toast_quick"
    DETAILED_FORM = "detailed_form"
