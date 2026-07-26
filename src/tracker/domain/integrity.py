"""Hash Chain Manager — cryptographic tamper resistance for log entries.

Implements SHA-256 hash chain computation and verification as specified in
Requirements 4.4, 4.5, 4.6, and 51.13. The HashChainManager is a pure
computation class with no external dependencies (ports).

Chain Computation:
    hash = SHA256(serialize_entry_for_hash(entry) + previous_hash)

Verification:
    Recompute each hash from the serialized entry data and compare against
    the stored hash. Flag all entries from the first mismatch onward.

Recovery:
    After a crash, discard incomplete entries (empty hash or special marker),
    start a new chain from the last valid entry, and do NOT flag as violation.
"""

from __future__ import annotations

import hashlib

from tracker.domain.models import LogEntry

# Sentinel value indicating an incomplete entry (e.g., after a crash)
INCOMPLETE_HASH_MARKER = ""


class HashChainManager:
    """Pure computation class for SHA-256 hash chain operations.

    This class accepts no ports and performs no I/O. All methods are
    deterministic and side-effect free.
    """

    @staticmethod
    def get_initial_hash() -> str:
        """Return the genesis hash used for the first entry in a new chain.

        Returns:
            SHA-256 hex digest of the string "GENESIS".
        """
        return hashlib.sha256(b"GENESIS").hexdigest()

    def compute_hash(self, entry_data: str, previous_hash: str) -> str:
        """Compute SHA-256 hash by chaining entry data with the previous hash.

        Args:
            entry_data: Serialized entry fields (from serialize_entry_for_hash).
            previous_hash: The hash of the preceding entry in the chain.

        Returns:
            SHA-256 hex digest of (entry_data + previous_hash).
        """
        payload = entry_data + previous_hash
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def serialize_entry_for_hash(self, entry: LogEntry) -> str:
        """Serialize entry fields into a deterministic string for hashing.

        The serialization includes: timestamp (ISO format), employee_id,
        status value, and location value — concatenated with pipe separators.

        Args:
            entry: The LogEntry to serialize.

        Returns:
            A deterministic string representation of the entry's key fields.
        """
        return (
            f"{entry.timestamp.isoformat()}"
            f"|{entry.employee_id}"
            f"|{entry.status.value}"
            f"|{entry.location.value}"
        )

    def verify_chain(self, entries: list[LogEntry]) -> tuple[bool, int | None]:
        """Verify the integrity of the entire hash chain.

        Recomputes each entry's hash from its serialized data and the
        previous entry's hash, then compares against the stored hash.

        Args:
            entries: Ordered list of LogEntry objects forming the chain.

        Returns:
            (True, None) if the chain is valid.
            (False, index) if tampering detected, where index is the
            position of the first entry with a hash mismatch.
        """
        if not entries:
            return (True, None)

        for i, entry in enumerate(entries):
            # Determine expected previous hash
            if i == 0:
                expected_previous = entry.previous_hash
            else:
                expected_previous = entries[i - 1].hash

            # Verify the previous_hash linkage
            if i > 0 and entry.previous_hash != expected_previous:
                return (False, i)

            # Recompute hash and compare to stored
            entry_data = self.serialize_entry_for_hash(entry)
            expected_hash = self.compute_hash(entry_data, entry.previous_hash)

            if entry.hash != expected_hash:
                return (False, i)

        return (True, None)

    def detect_incomplete_entry(self, entries: list[LogEntry]) -> bool:
        """Check if the last entry in the list is incomplete (crash recovery).

        An incomplete entry is one with an empty hash or the special
        incomplete marker, indicating the Tracker crashed before finishing
        the write.

        Args:
            entries: Ordered list of LogEntry objects.

        Returns:
            True if the last entry appears incomplete; False otherwise.
        """
        if not entries:
            return False

        last_entry = entries[-1]
        return last_entry.hash == INCOMPLETE_HASH_MARKER or last_entry.hash == ""
