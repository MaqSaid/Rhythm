"""Unit tests for the HashChainManager domain logic.

Tests cover Requirements 4.4, 4.5, 4.6, and 51.13:
- Correct SHA-256 hash computation (R4.4)
- Valid chain verification passes (R4.4)
- Single entry modification detected (R4.5)
- Multiple entry modifications — first flagged correctly (R4.5)
- New chain continues after violation (R4.6)
- Crash recovery: incomplete last entry discarded without false alarm (R51.13)
- Genesis hash is consistent
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime

from shared.enums import ActivityStatus, LocationType
from tracker.domain.integrity import INCOMPLETE_HASH_MARKER, HashChainManager
from tracker.domain.models import LogEntry

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

manager = HashChainManager()


def _make_entry(
    *,
    timestamp: datetime | None = None,
    employee_id: str = "EMP001",
    status: ActivityStatus = ActivityStatus.ONLINE,
    location: LocationType = LocationType.OFFICE,
    previous_hash: str = "",
    hash_value: str = "",
    entry_id: str = "entry-1",
    integrity_flag: str | None = None,
) -> LogEntry:
    """Helper to build a LogEntry with sensible defaults."""
    ts = timestamp or datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
    return LogEntry(
        id=entry_id,
        timestamp=ts,
        employee_id=employee_id,
        status=status,
        location=location,
        hash=hash_value,
        previous_hash=previous_hash,
        integrity_flag=integrity_flag,
    )


def _build_valid_chain(count: int = 3) -> list[LogEntry]:
    """Build a valid hash chain of the given length."""
    entries: list[LogEntry] = []
    prev_hash = HashChainManager.get_initial_hash()

    for i in range(count):
        ts = datetime(2024, 1, 15, 9, i * 5, 0, tzinfo=UTC)
        entry = _make_entry(
            timestamp=ts,
            previous_hash=prev_hash,
            entry_id=f"entry-{i}",
        )
        entry_data = manager.serialize_entry_for_hash(entry)
        computed_hash = manager.compute_hash(entry_data, prev_hash)
        entry = replace(entry, hash=computed_hash)
        entries.append(entry)
        prev_hash = computed_hash

    return entries


# ---------------------------------------------------------------------------
# R4.4: Correct hash computation
# ---------------------------------------------------------------------------


class TestHashComputation:
    """Tests for SHA-256 hash computation chaining."""

    def test_compute_hash_returns_sha256_hex_digest(self) -> None:
        """compute_hash returns a 64-char hex string (SHA-256)."""
        result = manager.compute_hash("test_data", "prev_hash")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_hash_matches_manual_sha256(self) -> None:
        """compute_hash produces the same result as manual SHA-256."""
        entry_data = "2024-01-15T09:00:00+00:00|EMP001|Online|office"
        previous_hash = HashChainManager.get_initial_hash()
        expected = hashlib.sha256(
            (entry_data + previous_hash).encode("utf-8")
        ).hexdigest()

        result = manager.compute_hash(entry_data, previous_hash)

        assert result == expected

    def test_compute_hash_is_deterministic(self) -> None:
        """Same inputs always produce the same hash."""
        result1 = manager.compute_hash("data", "prev")
        result2 = manager.compute_hash("data", "prev")
        assert result1 == result2

    def test_different_data_produces_different_hash(self) -> None:
        """Different entry data produces different hashes."""
        hash1 = manager.compute_hash("data_a", "prev")
        hash2 = manager.compute_hash("data_b", "prev")
        assert hash1 != hash2

    def test_different_previous_hash_produces_different_hash(self) -> None:
        """Different previous hash produces different output."""
        hash1 = manager.compute_hash("data", "prev_a")
        hash2 = manager.compute_hash("data", "prev_b")
        assert hash1 != hash2


# ---------------------------------------------------------------------------
# R4.4: Serialization determinism
# ---------------------------------------------------------------------------


class TestSerializeEntryForHash:
    """Tests for deterministic entry serialization."""

    def test_serialize_produces_expected_format(self) -> None:
        """Serialization uses pipe-separated timestamp|employee|status|location."""
        ts = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        entry = _make_entry(timestamp=ts)

        result = manager.serialize_entry_for_hash(entry)

        assert "2024-01-15T09:00:00+00:00" in result
        assert "EMP001" in result
        assert "Online" in result
        assert "office" in result
        assert result.count("|") == 3

    def test_serialize_is_deterministic(self) -> None:
        """Same entry always serializes to the same string."""
        entry = _make_entry()
        result1 = manager.serialize_entry_for_hash(entry)
        result2 = manager.serialize_entry_for_hash(entry)
        assert result1 == result2

    def test_serialize_different_entries_differ(self) -> None:
        """Different entries produce different serializations."""
        entry_a = _make_entry(employee_id="EMP001")
        entry_b = _make_entry(employee_id="EMP002")
        assert manager.serialize_entry_for_hash(entry_a) != manager.serialize_entry_for_hash(
            entry_b
        )


# ---------------------------------------------------------------------------
# R4.4: Valid chain verification passes
# ---------------------------------------------------------------------------


class TestValidChainVerification:
    """Tests for chain verification on untampered data."""

    def test_empty_chain_is_valid(self) -> None:
        """An empty list of entries is considered a valid chain."""
        valid, index = manager.verify_chain([])
        assert valid is True
        assert index is None

    def test_single_entry_valid_chain(self) -> None:
        """A single correctly-hashed entry passes verification."""
        chain = _build_valid_chain(count=1)
        valid, index = manager.verify_chain(chain)
        assert valid is True
        assert index is None

    def test_multi_entry_valid_chain(self) -> None:
        """A multi-entry correctly-hashed chain passes verification."""
        chain = _build_valid_chain(count=5)
        valid, index = manager.verify_chain(chain)
        assert valid is True
        assert index is None


# ---------------------------------------------------------------------------
# R4.5: Single entry modification detected
# ---------------------------------------------------------------------------


class TestTamperDetectionSingle:
    """Tests for detecting a single tampered entry."""

    def test_modified_hash_detected(self) -> None:
        """Changing an entry's hash field is detected."""
        chain = _build_valid_chain(count=3)
        # Tamper with middle entry's hash
        tampered = replace(chain[1], hash="0000000000000000000000000000000000000000000000000000000000000000")
        chain[1] = tampered

        valid, index = manager.verify_chain(chain)

        assert valid is False
        assert index == 1

    def test_modified_entry_data_detected(self) -> None:
        """Changing entry data (e.g., status) without updating hash is detected."""
        chain = _build_valid_chain(count=3)
        # Tamper with first entry's status (data change without hash update)
        tampered = replace(chain[0], status=ActivityStatus.IDLE)
        chain[0] = tampered

        valid, index = manager.verify_chain(chain)

        assert valid is False
        assert index == 0

    def test_modified_last_entry_detected(self) -> None:
        """Tampering with the last entry in the chain is detected."""
        chain = _build_valid_chain(count=3)
        tampered = replace(chain[2], employee_id="HACKER")
        chain[2] = tampered

        valid, index = manager.verify_chain(chain)

        assert valid is False
        assert index == 2


# ---------------------------------------------------------------------------
# R4.5: Multiple modifications — first flagged correctly
# ---------------------------------------------------------------------------


class TestTamperDetectionMultiple:
    """Tests for detecting multiple tampered entries — first is flagged."""

    def test_multiple_modifications_flags_first(self) -> None:
        """When multiple entries are tampered, verify_chain returns the first."""
        chain = _build_valid_chain(count=5)
        # Tamper with entries at index 1 and 3
        chain[1] = replace(chain[1], hash="bad_hash_1")
        chain[3] = replace(chain[3], hash="bad_hash_3")

        valid, index = manager.verify_chain(chain)

        assert valid is False
        assert index == 1

    def test_broken_linkage_detected(self) -> None:
        """A broken previous_hash linkage is detected."""
        chain = _build_valid_chain(count=3)
        # Break the linkage by changing entry[2]'s previous_hash
        chain[2] = replace(chain[2], previous_hash="wrong_previous")

        valid, index = manager.verify_chain(chain)

        assert valid is False
        assert index == 2


# ---------------------------------------------------------------------------
# R4.6: Continue logging new entries with a new chain after violation
# ---------------------------------------------------------------------------


class TestNewChainAfterViolation:
    """Tests confirming new chains can start after a violation."""

    def test_new_chain_after_violation_is_independently_valid(self) -> None:
        """A new chain started after a violation verifies correctly on its own."""
        # Build a valid chain of 3 entries starting from genesis
        new_chain = _build_valid_chain(count=3)

        valid, index = manager.verify_chain(new_chain)
        assert valid is True
        assert index is None

    def test_chain_starting_from_arbitrary_hash_is_valid(self) -> None:
        """A chain can start from any hash (new chain after violation)."""
        # Simulate starting a new chain from a non-genesis hash
        arbitrary_start = hashlib.sha256(b"RESTART").hexdigest()
        entries: list[LogEntry] = []
        prev_hash = arbitrary_start

        for i in range(3):
            ts = datetime(2024, 1, 15, 10, i * 5, 0, tzinfo=UTC)
            entry = _make_entry(
                timestamp=ts,
                previous_hash=prev_hash,
                entry_id=f"new-{i}",
            )
            entry_data = manager.serialize_entry_for_hash(entry)
            computed = manager.compute_hash(entry_data, prev_hash)
            entry = replace(entry, hash=computed)
            entries.append(entry)
            prev_hash = computed

        valid, index = manager.verify_chain(entries)
        assert valid is True
        assert index is None


# ---------------------------------------------------------------------------
# R51.13: Crash recovery — incomplete entry discarded without false alarm
# ---------------------------------------------------------------------------


class TestCrashRecovery:
    """Tests for crash recovery with incomplete entries."""

    def test_detect_incomplete_empty_hash(self) -> None:
        """An entry with an empty hash is detected as incomplete."""
        entry = _make_entry(hash_value="")
        assert manager.detect_incomplete_entry([entry]) is True

    def test_detect_incomplete_marker_hash(self) -> None:
        """An entry with the INCOMPLETE_HASH_MARKER is detected as incomplete."""
        entry = _make_entry(hash_value=INCOMPLETE_HASH_MARKER)
        assert manager.detect_incomplete_entry([entry]) is True

    def test_complete_entry_not_detected_as_incomplete(self) -> None:
        """A properly hashed entry is NOT detected as incomplete."""
        chain = _build_valid_chain(count=1)
        assert manager.detect_incomplete_entry(chain) is False

    def test_empty_list_not_detected_as_incomplete(self) -> None:
        """An empty entry list returns False (nothing to detect)."""
        assert manager.detect_incomplete_entry([]) is False

    def test_only_last_entry_checked_for_incompleteness(self) -> None:
        """Only the last entry is checked; earlier entries don't matter."""
        chain = _build_valid_chain(count=3)
        # Even if we add an incomplete entry at position 0, detect checks last
        incomplete = _make_entry(hash_value="", entry_id="incomplete")
        mixed_list = [incomplete, chain[0], chain[1], chain[2]]
        # Last entry (chain[2]) has a valid hash
        assert manager.detect_incomplete_entry(mixed_list) is False

    def test_chain_valid_after_discarding_incomplete_entry(self) -> None:
        """After discarding an incomplete last entry, the chain remains valid.

        This confirms R51.13: discard incomplete entry, start new chain
        from last valid, do NOT flag as integrity violation.
        """
        chain = _build_valid_chain(count=3)
        # Simulate a crash: append an incomplete entry
        incomplete = _make_entry(
            hash_value="",
            previous_hash=chain[-1].hash,
            entry_id="crashed",
            timestamp=datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC),
        )
        chain_with_crash = chain + [incomplete]

        # Detect the incomplete entry
        assert manager.detect_incomplete_entry(chain_with_crash) is True

        # Discard it (simulating recovery logic)
        recovered_chain = chain_with_crash[:-1]

        # Verify the recovered chain is valid — no false alarm
        valid, index = manager.verify_chain(recovered_chain)
        assert valid is True
        assert index is None


# ---------------------------------------------------------------------------
# Genesis hash consistency
# ---------------------------------------------------------------------------


class TestGenesisHash:
    """Tests for the genesis hash."""

    def test_genesis_hash_is_sha256_of_genesis_string(self) -> None:
        """Genesis hash is SHA-256 of 'GENESIS'."""
        expected = hashlib.sha256(b"GENESIS").hexdigest()
        assert HashChainManager.get_initial_hash() == expected

    def test_genesis_hash_is_consistent(self) -> None:
        """Genesis hash returns the same value on every call."""
        hash1 = HashChainManager.get_initial_hash()
        hash2 = HashChainManager.get_initial_hash()
        assert hash1 == hash2

    def test_genesis_hash_is_64_hex_chars(self) -> None:
        """Genesis hash is a valid 64-character hex string."""
        genesis = HashChainManager.get_initial_hash()
        assert len(genesis) == 64
        assert all(c in "0123456789abcdef" for c in genesis)
