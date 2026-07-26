"""Shared kernel value objects providing type safety across bounded contexts."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EmployeeID:
    """Unique identifier for an employee, providing type safety over raw strings."""

    value: str

    def __post_init__(self) -> None:
        """Validate that the employee ID is not empty."""
        if not self.value or not self.value.strip():
            raise ValueError("EmployeeID cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TenantID:
    """Unique identifier for a tenant organization."""

    value: str

    def __post_init__(self) -> None:
        """Validate that the tenant ID is not empty."""
        if not self.value or not self.value.strip():
            raise ValueError("TenantID cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Timestamp:
    """UTC timestamp wrapper ensuring timezone awareness."""

    value: datetime

    def __post_init__(self) -> None:
        """Validate that the timestamp has timezone info (UTC expected)."""
        if self.value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC expected)")

    def __str__(self) -> str:
        return self.value.isoformat()
