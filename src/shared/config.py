"""Shared configuration models with validation for tenant-specific parameters."""

from typing import Literal

from pydantic import BaseModel, Field

from shared.value_objects import TenantID


class TenantConfig(BaseModel):
    """Configurable parameters for a tenant with validation ranges.

    All thresholds, timeouts, and behavioral settings are configurable per tenant.
    Defaults match the design specification.
    """

    idle_threshold_minutes: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Minutes of inactivity before marking as Idle",
    )
    auto_exempt_threshold_minutes: int = Field(
        default=30,
        ge=15,
        le=120,
        description="Minutes of idle below which no notification is sent",
    )
    review_period: Literal["weekly", "fortnightly", "monthly"] = Field(
        default="weekly",
        description="Reconciliation review period type",
    )
    variance_flag_threshold: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        description="Hours of variance before flagging",
    )
    auto_clock_out_time: str = Field(
        default="23:00",
        pattern=r"^(2[0-3]):[0-5][0-9]$",
        description="Time for automatic clock-out (range 20:00-23:59)",
    )
    heartbeat_interval_minutes: int = Field(
        default=30,
        ge=15,
        le=120,
        description="Minutes between heartbeat signals to Portal",
    )
    magic_link_expiry_minutes: int = Field(
        default=10,
        ge=5,
        le=30,
        description="Minutes before a magic link expires",
    )
    session_timeout_minutes: int = Field(
        default=30,
        ge=15,
        le=120,
        description="Minutes of inactivity before session expires",
    )
    data_retention_days: int = Field(
        default=180,
        ge=30,
        description="Days to retain activity data",
    )
    surveillance_notice_period_days: int = Field(
        default=14,
        ge=7,
        description="Days of notice before surveillance changes take effect",
    )
    self_correction_notification_enabled: bool = Field(
        default=True,
        description="Whether to send self-correction notifications at 75% threshold",
    )
    transparency_report_enabled: bool = Field(
        default=True,
        description="Whether to generate employee transparency reports",
    )
    transparency_report_lead_hours: int = Field(
        default=24,
        ge=12,
        le=72,
        description="Hours before HR review that transparency report is sent",
    )
    default_work_pattern: Literal["standard", "split", "flexible", "custom"] = Field(
        default="standard",
        description="Default work pattern for new employees",
    )
    positive_reinforcement_threshold: int = Field(
        default=3,
        ge=1,
        le=12,
        description="Consecutive clean review periods before badge award",
    )


class WhiteLabelConfig(BaseModel):
    """White-label branding configuration for a tenant.

    Allows customization of visual branding while maintaining Rhythm defaults.
    """

    tenant_id: TenantID
    logo_url: str | None = None
    company_name: str = Field(default="Rhythm")
    primary_color: str = Field(
        default="#5B8C5A",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Primary brand color (hex)",
    )
    secondary_color: str = Field(
        default="#E8A838",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Secondary brand color (hex)",
    )

    class Config:
        """Pydantic model configuration."""

        arbitrary_types_allowed = True
