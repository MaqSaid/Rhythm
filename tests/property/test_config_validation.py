# Feature: fraud-proof-hybrid-timesheet, Property 30: Configurable parameter validation
"""Property tests for configurable parameter validation.

**Validates: Requirements 22.4, 22.5**

Tests that for any parameter change request, the system accepts the new value if and only if
it falls within the allowed range. Covers all configurable parameters:
- idle_threshold (5-60)
- auto_exempt_threshold (15-120)
- review_period (weekly/fortnightly/monthly)
- variance_flag_threshold (1.0-10.0)
- auto_clock_out_time (20:00-23:59)
- heartbeat_interval (15-120)
- magic_link_expiry (5-30)
- session_timeout (15-120)
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from shared.config import TenantConfig

# --- Strategies for valid values ---

valid_idle_threshold = st.integers(min_value=5, max_value=60)
valid_auto_exempt_threshold = st.integers(min_value=15, max_value=120)
valid_review_period = st.sampled_from(["weekly", "fortnightly", "monthly"])
valid_variance_flag_threshold = st.floats(min_value=1.0, max_value=10.0, allow_nan=False)
valid_heartbeat_interval = st.integers(min_value=15, max_value=120)
valid_magic_link_expiry = st.integers(min_value=5, max_value=30)
valid_session_timeout = st.integers(min_value=15, max_value=120)

# Valid auto_clock_out_time: 20:00 to 23:59
valid_auto_clock_out_time = st.builds(
    lambda h, m: f"{h:02d}:{m:02d}",
    st.integers(min_value=20, max_value=23),
    st.integers(min_value=0, max_value=59),
)

# --- Strategies for invalid values ---

invalid_idle_threshold_low = st.integers(min_value=-1000, max_value=4)
invalid_idle_threshold_high = st.integers(min_value=61, max_value=10000)

invalid_auto_exempt_threshold_low = st.integers(min_value=-1000, max_value=14)
invalid_auto_exempt_threshold_high = st.integers(min_value=121, max_value=10000)

invalid_review_period = st.text(min_size=1, max_size=20).filter(
    lambda s: s not in ("weekly", "fortnightly", "monthly")
)

invalid_variance_flag_threshold_low = st.floats(
    min_value=-100.0, max_value=0.99, allow_nan=False, allow_infinity=False
)
invalid_variance_flag_threshold_high = st.floats(
    min_value=10.01, max_value=1000.0, allow_nan=False, allow_infinity=False
)

invalid_heartbeat_interval_low = st.integers(min_value=-1000, max_value=14)
invalid_heartbeat_interval_high = st.integers(min_value=121, max_value=10000)

invalid_magic_link_expiry_low = st.integers(min_value=-1000, max_value=4)
invalid_magic_link_expiry_high = st.integers(min_value=31, max_value=10000)

invalid_session_timeout_low = st.integers(min_value=-1000, max_value=14)
invalid_session_timeout_high = st.integers(min_value=121, max_value=10000)

# Invalid auto_clock_out_time: hours outside 20-23 range
invalid_auto_clock_out_time_low_hour = st.builds(
    lambda h, m: f"{h:02d}:{m:02d}",
    st.integers(min_value=0, max_value=19),
    st.integers(min_value=0, max_value=59),
)


@pytest.mark.property
class TestConfigurableParameterValidation:
    """Property 30: Configurable parameter validation."""

    # --- Valid value acceptance tests ---

    @given(value=valid_idle_threshold)
    @settings(max_examples=200)
    def test_valid_idle_threshold_accepted(self, value: int) -> None:
        """idle_threshold in [5, 60] SHALL be accepted."""
        config = TenantConfig(idle_threshold_minutes=value)
        assert config.idle_threshold_minutes == value

    @given(value=valid_auto_exempt_threshold)
    @settings(max_examples=200)
    def test_valid_auto_exempt_threshold_accepted(self, value: int) -> None:
        """auto_exempt_threshold in [15, 120] SHALL be accepted."""
        config = TenantConfig(auto_exempt_threshold_minutes=value)
        assert config.auto_exempt_threshold_minutes == value

    @given(value=valid_review_period)
    @settings(max_examples=10)
    def test_valid_review_period_accepted(self, value: str) -> None:
        """review_period in {weekly, fortnightly, monthly} SHALL be accepted."""
        config = TenantConfig(review_period=value)
        assert config.review_period == value

    @given(value=valid_variance_flag_threshold)
    @settings(max_examples=200)
    def test_valid_variance_flag_threshold_accepted(self, value: float) -> None:
        """variance_flag_threshold in [1.0, 10.0] SHALL be accepted."""
        config = TenantConfig(variance_flag_threshold=value)
        assert config.variance_flag_threshold == value

    @given(time_str=valid_auto_clock_out_time)
    @settings(max_examples=200)
    def test_valid_auto_clock_out_time_accepted(self, time_str: str) -> None:
        """auto_clock_out_time in [20:00, 23:59] SHALL be accepted."""
        config = TenantConfig(auto_clock_out_time=time_str)
        assert config.auto_clock_out_time == time_str

    @given(value=valid_heartbeat_interval)
    @settings(max_examples=200)
    def test_valid_heartbeat_interval_accepted(self, value: int) -> None:
        """heartbeat_interval in [15, 120] SHALL be accepted."""
        config = TenantConfig(heartbeat_interval_minutes=value)
        assert config.heartbeat_interval_minutes == value

    @given(value=valid_magic_link_expiry)
    @settings(max_examples=200)
    def test_valid_magic_link_expiry_accepted(self, value: int) -> None:
        """magic_link_expiry in [5, 30] SHALL be accepted."""
        config = TenantConfig(magic_link_expiry_minutes=value)
        assert config.magic_link_expiry_minutes == value

    @given(value=valid_session_timeout)
    @settings(max_examples=200)
    def test_valid_session_timeout_accepted(self, value: int) -> None:
        """session_timeout in [15, 120] SHALL be accepted."""
        config = TenantConfig(session_timeout_minutes=value)
        assert config.session_timeout_minutes == value

    # --- Invalid value rejection tests ---

    @given(value=invalid_idle_threshold_low | invalid_idle_threshold_high)
    @settings(max_examples=200)
    def test_invalid_idle_threshold_rejected(self, value: int) -> None:
        """idle_threshold outside [5, 60] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(idle_threshold_minutes=value)

    @given(value=invalid_auto_exempt_threshold_low | invalid_auto_exempt_threshold_high)
    @settings(max_examples=200)
    def test_invalid_auto_exempt_threshold_rejected(self, value: int) -> None:
        """auto_exempt_threshold outside [15, 120] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(auto_exempt_threshold_minutes=value)

    @given(value=invalid_review_period)
    @settings(max_examples=200)
    def test_invalid_review_period_rejected(self, value: str) -> None:
        """review_period not in {weekly, fortnightly, monthly} SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(review_period=value)

    @given(value=invalid_variance_flag_threshold_low | invalid_variance_flag_threshold_high)
    @settings(max_examples=200)
    def test_invalid_variance_flag_threshold_rejected(self, value: float) -> None:
        """variance_flag_threshold outside [1.0, 10.0] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(variance_flag_threshold=value)

    @given(time_str=invalid_auto_clock_out_time_low_hour)
    @settings(max_examples=200)
    def test_invalid_auto_clock_out_time_rejected(self, time_str: str) -> None:
        """auto_clock_out_time with hours outside [20, 23] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(auto_clock_out_time=time_str)

    @given(value=invalid_heartbeat_interval_low | invalid_heartbeat_interval_high)
    @settings(max_examples=200)
    def test_invalid_heartbeat_interval_rejected(self, value: int) -> None:
        """heartbeat_interval outside [15, 120] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(heartbeat_interval_minutes=value)

    @given(value=invalid_magic_link_expiry_low | invalid_magic_link_expiry_high)
    @settings(max_examples=200)
    def test_invalid_magic_link_expiry_rejected(self, value: int) -> None:
        """magic_link_expiry outside [5, 30] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(magic_link_expiry_minutes=value)

    @given(value=invalid_session_timeout_low | invalid_session_timeout_high)
    @settings(max_examples=200)
    def test_invalid_session_timeout_rejected(self, value: int) -> None:
        """session_timeout outside [15, 120] SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(session_timeout_minutes=value)

    # --- Edge case tests: exactly at range limits ---

    def test_idle_threshold_at_lower_bound(self) -> None:
        """idle_threshold exactly at 5 (lower bound) SHALL be accepted."""
        config = TenantConfig(idle_threshold_minutes=5)
        assert config.idle_threshold_minutes == 5

    def test_idle_threshold_at_upper_bound(self) -> None:
        """idle_threshold exactly at 60 (upper bound) SHALL be accepted."""
        config = TenantConfig(idle_threshold_minutes=60)
        assert config.idle_threshold_minutes == 60

    def test_idle_threshold_just_below_lower_bound(self) -> None:
        """idle_threshold at 4 (below lower bound) SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(idle_threshold_minutes=4)

    def test_idle_threshold_just_above_upper_bound(self) -> None:
        """idle_threshold at 61 (above upper bound) SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(idle_threshold_minutes=61)

    def test_auto_clock_out_time_at_lower_bound(self) -> None:
        """auto_clock_out_time at 20:00 (lower bound) SHALL be accepted."""
        config = TenantConfig(auto_clock_out_time="20:00")
        assert config.auto_clock_out_time == "20:00"

    def test_auto_clock_out_time_at_upper_bound(self) -> None:
        """auto_clock_out_time at 23:59 (upper bound) SHALL be accepted."""
        config = TenantConfig(auto_clock_out_time="23:59")
        assert config.auto_clock_out_time == "23:59"

    def test_auto_clock_out_time_just_below_lower_bound(self) -> None:
        """auto_clock_out_time at 19:59 (below lower bound) SHALL be rejected."""
        with pytest.raises(ValidationError):
            TenantConfig(auto_clock_out_time="19:59")

    def test_variance_flag_threshold_at_bounds(self) -> None:
        """variance_flag_threshold exactly at 1.0 and 10.0 SHALL be accepted."""
        config_low = TenantConfig(variance_flag_threshold=1.0)
        assert config_low.variance_flag_threshold == 1.0
        config_high = TenantConfig(variance_flag_threshold=10.0)
        assert config_high.variance_flag_threshold == 10.0
