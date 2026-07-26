# Feature: fraud-proof-hybrid-timesheet, Properties 5, 6, 7: Hash chain integrity
"""Property tests for SHA-256 hash chain integrity, tamper detection, and recovery.

**Validates: Requirements 4.4, 4.5, 4.6, 51.13**

Property 5: SHA-256 hash chain integrity computation — For any ordered sequence of
    log entries, each entry's hash equals SHA256(serialized_data || previous_hash).
    Chain is reproducible by recomputing sequentially.

Property 6: Hash chain tamper detection — For any valid chain with one or more entries
    modified, the verification function detects the first tampered entry.

Property 7: Hash chain recovery after incomplete write — For any valid chain followed
    by a single incomplete entry, the recovery discards only the incomplete entry and
    does NOT flag it as a violation.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shared.enums import ActivityStatus, LocationType
from tracker.domain.integrity import INCOMPLETE_HASH_MARKER, HashChainManager
from tracker.domain.models import LogEntry

# --- Strategies ---

employee_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Nd")),
    min_size=3,
    max_size=12,
)

timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(UTC),
)

statuses = st.sampled_from([ActivityStatus.ONLINE, ActivityStatus.IDLE])
locations = st.sampled_from([LocationType.OFFICE, LocationType.HOME])

chain_lengths = st.integers(min_value=1, max_value=20)


def build_valid_chain(
    manager: HashChainManager,
    employee_id: str,
    base_timestamp: datetime,
    status_list: list[ActivityStatus],
    location_list: list[LocationType],
) -> list[LogEntry]:
    """Build a valid hash chain of LogEntry objects."""
    entries: list[LogEntry] = []
    previous_hash = manager.get_initial_hash()

    for i in range(len(status_list)):
        entry_without_hash = LogEntry(
            id=uuid.uuid4().hex,
            timestamp=base_timestamp + timedelta(minutes=5 * i),
            employee_id=employee_id,
            status=status_list[i],
            location=location_list[i],
            hash="",  # placeholder
            previous_hash=previous_hash,
        )
        entry_data = manager.serialize_entry_for_hash(entry_without_hash)
        computed_hash = manager.compute_hash(entry_data, previous_hash)

        entry = replace(entry_without_hash, hash=computed_hash)
        entries.append(entry)
        previous_hash = computed_hash

    return entries


@pytest.mark.property
class TestHashChainIntegrity:
    """Property 5: SHA-256 hash chain integrity computation."""

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=chain_lengths,
        data=st.data(),
    )
    @settings(max_examples=300)
    def test_chain_hash_equals_sha256_of_data_plus_previous(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """Each entry's hash SHALL equal SHA256(serialized_data || previous_hash).

        For any ordered sequence of log entries, the hash chain is reproducible
        by recomputing sequentially from the genesis hash.
        """
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        # Verify each entry's hash manually
        previous_hash = manager.get_initial_hash()
        for entry in entries:
            entry_data = manager.serialize_entry_for_hash(entry)
            expected_payload = entry_data + previous_hash
            expected_hash = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()

            assert entry.hash == expected_hash, (
                f"Entry hash mismatch: got {entry.hash}, expected {expected_hash}"
            )
            assert entry.previous_hash == previous_hash
            previous_hash = entry.hash

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=chain_lengths,
        data=st.data(),
    )
    @settings(max_examples=300)
    def test_valid_chain_passes_verification(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """A correctly built chain SHALL always pass verify_chain."""
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        is_valid, tamper_index = manager.verify_chain(entries)
        assert is_valid is True
        assert tamper_index is None


@pytest.mark.property
class TestHashChainTamperDetection:
    """Property 6: Hash chain tamper detection."""

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=st.integers(min_value=2, max_value=20),
        data=st.data(),
    )
    @settings(max_examples=300)
    def test_tamper_status_detected(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """Modifying an entry's status SHALL be detected by verify_chain.

        The verification function SHALL detect the first tampered entry.
        """
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        # Pick a random position to tamper
        tamper_pos = data.draw(st.integers(min_value=0, max_value=length - 1))

        # Flip the status at that position
        original_entry = entries[tamper_pos]
        new_status = (
            ActivityStatus.IDLE
            if original_entry.status == ActivityStatus.ONLINE
            else ActivityStatus.ONLINE
        )
        tampered_entry = replace(original_entry, status=new_status)
        entries[tamper_pos] = tampered_entry

        is_valid, detected_index = manager.verify_chain(entries)
        assert is_valid is False
        assert detected_index is not None
        # The detected index should be <= the tamper position
        # (it detects the first mismatch which is at or before the tamper)
        assert detected_index <= tamper_pos

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=st.integers(min_value=2, max_value=20),
        data=st.data(),
    )
    @settings(max_examples=300)
    def test_tamper_employee_id_detected(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """Modifying an entry's employee_id SHALL be detected by verify_chain."""
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        tamper_pos = data.draw(st.integers(min_value=0, max_value=length - 1))

        # Change the employee_id
        original_entry = entries[tamper_pos]
        new_employee_id = employee_id + "TAMPERED"
        tampered_entry = replace(original_entry, employee_id=new_employee_id)
        entries[tamper_pos] = tampered_entry

        is_valid, detected_index = manager.verify_chain(entries)
        assert is_valid is False
        assert detected_index is not None
        assert detected_index <= tamper_pos

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=st.integers(min_value=2, max_value=20),
        data=st.data(),
    )
    @settings(max_examples=300)
    def test_tamper_location_detected(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """Modifying an entry's location SHALL be detected by verify_chain."""
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        tamper_pos = data.draw(st.integers(min_value=0, max_value=length - 1))

        # Flip the location at that position
        original_entry = entries[tamper_pos]
        new_location = (
            LocationType.HOME
            if original_entry.location == LocationType.OFFICE
            else LocationType.OFFICE
        )
        tampered_entry = replace(original_entry, location=new_location)
        entries[tamper_pos] = tampered_entry

        is_valid, detected_index = manager.verify_chain(entries)
        assert is_valid is False
        assert detected_index is not None
        assert detected_index <= tamper_pos


@pytest.mark.property
class TestHashChainRecovery:
    """Property 7: Hash chain recovery after incomplete write."""

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=st.integers(min_value=1, max_value=20),
        data=st.data(),
    )
    @settings(max_examples=300)
    def test_incomplete_entry_detected_not_flagged_as_violation(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """An incomplete trailing entry SHALL be detected and discarded, not flagged.

        After a crash, the last entry may have an empty hash. The recovery
        mechanism discards it and the remaining valid chain passes verification.
        """
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        valid_entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        # Append an incomplete entry (empty hash simulating crash)
        last_valid_hash = valid_entries[-1].hash
        incomplete_entry = LogEntry(
            id=uuid.uuid4().hex,
            timestamp=base_timestamp + timedelta(minutes=5 * length),
            employee_id=employee_id,
            status=data.draw(statuses),
            location=data.draw(locations),
            hash=INCOMPLETE_HASH_MARKER,
            previous_hash=last_valid_hash,
        )

        all_entries = valid_entries + [incomplete_entry]

        # The manager should detect the incomplete entry
        assert manager.detect_incomplete_entry(all_entries) is True

        # After discarding the incomplete entry, the valid chain passes
        recovered_entries = all_entries[:-1]
        is_valid, tamper_index = manager.verify_chain(recovered_entries)
        assert is_valid is True
        assert tamper_index is None

    @given(
        employee_id=employee_ids,
        base_timestamp=timestamps,
        length=st.integers(min_value=1, max_value=20),
        data=st.data(),
    )
    @settings(max_examples=200)
    def test_valid_chain_without_incomplete_not_detected(
        self,
        employee_id: str,
        base_timestamp: datetime,
        length: int,
        data: st.DataObject,
    ) -> None:
        """A valid chain without incomplete entries SHALL NOT trigger recovery."""
        status_list = data.draw(st.lists(statuses, min_size=length, max_size=length))
        location_list = data.draw(st.lists(locations, min_size=length, max_size=length))

        manager = HashChainManager()
        valid_entries = build_valid_chain(
            manager, employee_id, base_timestamp, status_list, location_list
        )

        # No incomplete entry at end
        assert manager.detect_incomplete_entry(valid_entries) is False

    def test_empty_chain_no_incomplete_detection(self) -> None:
        """An empty chain SHALL NOT trigger incomplete detection."""
        manager = HashChainManager()
        assert manager.detect_incomplete_entry([]) is False
