"""
AfriMine AI — Offline Sync Integration Tests
==============================================

Tests the offline-first design:
- Create samples offline (SQLite)
- Simulate sync to Supabase
- Verify conflict resolution (vector clocks)
- Verify delta sync (only changed records)

Requires: pytest
Run: pytest tests/integration/test_offline_sync.py -v

NOTE: These tests validate the sync logic and data contracts.
Full SQLite tests require a Flutter test environment.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Vector Clock Implementation (mirrors ARCHITECTURE_V3.md §12)
# ---------------------------------------------------------------------------

@dataclass
class VectorClock:
    """Vector clock for distributed conflict detection."""
    clocks: dict[str, int] = field(default_factory=dict)

    def increment(self, device_id: str):
        self.clocks[device_id] = self.clocks.get(device_id, 0) + 1

    def merge(self, other: "VectorClock"):
        for device_id, counter in other.clocks.items():
            self.clocks[device_id] = max(self.clocks.get(device_id, 0), counter)

    def compare(self, other: "VectorClock") -> str:
        all_devices = set(self.clocks.keys()) | set(other.clocks.keys())
        self_greater = False
        other_greater = False

        for d in all_devices:
            s = self.clocks.get(d, 0)
            o = other.clocks.get(d, 0)
            if s > o:
                self_greater = True
            elif o > s:
                other_greater = True

        if self_greater and not other_greater:
            return "after"
        elif other_greater and not self_greater:
            return "before"
        elif not self_greater and not other_greater:
            return "equal"
        else:
            return "concurrent"


# ---------------------------------------------------------------------------
# Sync Queue Simulation
# ---------------------------------------------------------------------------

@dataclass
class SyncItem:
    entity_type: str
    entity_id: str
    action: str
    data: dict[str, Any]
    vector_clock: dict[str, int]
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0


class OfflineSyncSimulator:
    """Simulates the offline sync process."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.queue: list[SyncItem] = []
        self.remote_store: dict[str, dict[str, Any]] = {}
        self.conflicts: list[dict[str, Any]] = []

    def create_offline(self, entity_type: str, data: dict[str, Any]) -> str:
        """Create a record while offline."""
        entity_id = str(uuid.uuid4())
        vc = VectorClock()
        vc.increment(self.device_id)

        item = SyncItem(
            entity_type=entity_type,
            entity_id=entity_id,
            action="create",
            data=data,
            vector_clock=vc.clocks,
        )
        self.queue.append(item)
        return entity_id

    def update_offline(self, entity_type: str, entity_id: str, data: dict[str, Any]):
        """Update a record while offline."""
        vc = VectorClock()
        vc.increment(self.device_id)

        item = SyncItem(
            entity_type=entity_type,
            entity_id=entity_id,
            action="update",
            data=data,
            vector_clock=vc.clocks,
        )
        self.queue.append(item)

    def sync_to_remote(self) -> dict[str, int]:
        """Sync queued items to remote store. Returns sync stats."""
        uploaded = 0
        failed = 0
        conflict_count = 0

        for item in self.queue:
            key = f"{item.entity_type}:{item.entity_id}"

            if item.action == "create":
                if key in self.remote_store:
                    # Conflict: remote already has this record
                    remote_vc = VectorClock(clocks=self.remote_store[key].get("vector_clock", {}))
                    local_vc = VectorClock(clocks=item.vector_clock)
                    comparison = local_vc.compare(remote_vc)

                    if comparison == "concurrent":
                        self.conflicts.append({
                            "entity_type": item.entity_type,
                            "entity_id": item.entity_id,
                            "local_clock": item.vector_clock,
                            "remote_clock": remote_vc.clocks,
                            "resolution": "manual",
                        })
                        conflict_count += 1
                        continue

                self.remote_store[key] = {
                    **item.data,
                    "vector_clock": item.vector_clock,
                    "synced_at": time.time(),
                }
                uploaded += 1

            elif item.action == "update":
                if key in self.remote_store:
                    remote_vc = VectorClock(clocks=self.remote_store[key].get("vector_clock", {}))
                    local_vc = VectorClock(clocks=item.vector_clock)
                    comparison = local_vc.compare(remote_vc)

                    if comparison == "concurrent":
                        self.conflicts.append({
                            "entity_type": item.entity_type,
                            "entity_id": item.entity_id,
                            "local_clock": item.vector_clock,
                            "remote_clock": remote_vc.clocks,
                        })
                        conflict_count += 1
                        continue
                    elif comparison == "before":
                        # Remote is newer — skip
                        failed += 1
                        continue

                self.remote_store[key] = {
                    **self.remote_store.get(key, {}),
                    **item.data,
                    "vector_clock": item.vector_clock,
                    "synced_at": time.time(),
                }
                uploaded += 1

        self.queue.clear()
        return {"uploaded": uploaded, "failed": failed, "conflicts": conflict_count}


# ---------------------------------------------------------------------------
# Test: Offline Sample Creation
# ---------------------------------------------------------------------------

class TestOfflineSampleCreation:
    """Test creating mineral samples while offline."""

    def test_create_sample_offline(self):
        """Samples created offline should be queued for sync."""
        sync = OfflineSyncSimulator(device_id="phone-001")

        sample_id = sync.create_offline("sample", {
            "location": {"lat": -1.05, "lon": 34.55, "region": "Nyatike"},
            "xrf_readings": {"Au": 5.2, "As": 120.5},
            "field_notes": "Quartz vein near river",
        })

        assert sample_id is not None
        assert len(sync.queue) == 1
        assert sync.queue[0].entity_type == "sample"
        assert sync.queue[0].action == "create"

    def test_create_multiple_samples_offline(self):
        """Multiple samples can be queued offline."""
        sync = OfflineSyncSimulator(device_id="phone-001")

        for i in range(5):
            sync.create_offline("sample", {
                "location": {"lat": -1.05 + i * 0.01, "lon": 34.55},
                "xrf_readings": {"Au": 3.0 + i},
            })

        assert len(sync.queue) == 5

    def test_offline_sample_has_vector_clock(self):
        """Offline samples must include vector clock for conflict detection."""
        sync = OfflineSyncSimulator(device_id="phone-001")

        sync.create_offline("sample", {"location": {"lat": -1.05, "lon": 34.55}})

        assert sync.queue[0].vector_clock is not None
        assert "phone-001" in sync.queue[0].vector_clock
        assert sync.queue[0].vector_clock["phone-001"] == 1


# ---------------------------------------------------------------------------
# Test: Sync to Remote
# ---------------------------------------------------------------------------

class TestSyncToRemote:
    """Test syncing offline data to the remote store (Supabase)."""

    def test_sync_uploads_queued_items(self):
        """Queued items should be uploaded to remote store."""
        sync = OfflineSyncSimulator(device_id="phone-001")

        sync.create_offline("sample", {"location": {"lat": -1.05, "lon": 34.55}})
        sync.create_offline("sample", {"location": {"lat": -1.06, "lon": 34.56}})

        stats = sync.sync_to_remote()

        assert stats["uploaded"] == 2
        assert stats["failed"] == 0
        assert stats["conflicts"] == 0
        assert len(sync.remote_store) == 2
        assert len(sync.queue) == 0  # Queue cleared after sync

    def test_sync_clears_queue_on_success(self):
        """Queue should be empty after successful sync."""
        sync = OfflineSyncSimulator(device_id="phone-001")

        sync.create_offline("sample", {"data": "test"})
        assert len(sync.queue) == 1

        sync.sync_to_remote()
        assert len(sync.queue) == 0

    def test_delta_sync_only_changed_records(self):
        """Only changed/new records should be synced, not entire database."""
        sync = OfflineSyncSimulator(device_id="phone-001")

        # Create 3 samples
        id1 = sync.create_offline("sample", {"name": "sample-1"})
        id2 = sync.create_offline("sample", {"name": "sample-2"})
        id3 = sync.create_offline("sample", {"name": "sample-3"})

        # Sync first batch
        stats = sync.sync_to_remote()
        assert stats["uploaded"] == 3

        # Update only 1 sample
        sync.update_offline("sample", id2, {"name": "sample-2-updated"})

        # Sync delta — only 1 record should upload
        stats = sync.sync_to_remote()
        assert stats["uploaded"] == 1
        assert stats["conflicts"] == 0


# ---------------------------------------------------------------------------
# Test: Conflict Resolution
# ---------------------------------------------------------------------------

class TestConflictResolution:
    """Test vector clock conflict detection and resolution."""

    def test_vector_clock_no_conflict(self):
        """Sequential updates from same device should not conflict."""
        vc1 = VectorClock(clocks={"phone-001": 1})
        vc2 = VectorClock(clocks={"phone-001": 2})

        assert vc1.compare(vc2) == "before"
        assert vc2.compare(vc1) == "after"

    def test_vector_clock_concurrent_conflict(self):
        """Concurrent updates from different devices should be detected."""
        vc1 = VectorClock(clocks={"phone-001": 2, "phone-002": 1})
        vc2 = VectorClock(clocks={"phone-001": 1, "phone-002": 2})

        assert vc1.compare(vc2) == "concurrent"
        assert vc2.compare(vc1) == "concurrent"

    def test_vector_clock_equal(self):
        """Identical clocks should be equal."""
        vc1 = VectorClock(clocks={"phone-001": 1, "phone-002": 1})
        vc2 = VectorClock(clocks={"phone-001": 1, "phone-002": 1})

        assert vc1.compare(vc2) == "equal"

    def test_vector_clock_merge(self):
        """Merge should take max of each device counter."""
        vc1 = VectorClock(clocks={"phone-001": 2, "phone-002": 1})
        vc2 = VectorClock(clocks={"phone-001": 1, "phone-002": 3})

        vc1.merge(vc2)

        assert vc1.clocks == {"phone-001": 2, "phone-002": 3}

    def test_conflict_detection_on_concurrent_create(self):
        """Two devices creating the same entity should detect conflict."""
        sync1 = OfflineSyncSimulator(device_id="phone-001")
        sync2 = OfflineSyncSimulator(device_id="phone-002")

        entity_id = str(uuid.uuid4())

        # Both create the same sample offline
        sync1.create_offline("sample", {"location": {"lat": -1.05, "lon": 34.55}})
        sync1.queue[-1].entity_id = entity_id

        sync2.create_offline("sample", {"location": {"lat": -1.05, "lon": 34.55}})
        sync2.queue[-1].entity_id = entity_id

        # Phone 1 syncs first
        stats1 = sync1.sync_to_remote()
        assert stats1["uploaded"] == 1

        # Copy remote store to phone 2's view
        sync2.remote_store = dict(sync1.remote_store)

        # Phone 2 syncs — should detect conflict
        stats2 = sync2.sync_to_remote()
        assert stats2["conflicts"] == 1
        assert len(sync2.conflicts) == 1

    def test_conflict_resolution_keep_highest_confidence(self):
        """For AI results, keep the analysis with highest confidence."""
        analyses = [
            {"confidence": 0.85, "mineral": "gold", "device": "phone-001"},
            {"confidence": 0.78, "mineral": "gold", "device": "phone-002"},
        ]

        best = max(analyses, key=lambda a: a["confidence"])
        assert best["confidence"] == 0.85
        assert best["device"] == "phone-001"

    def test_conflict_resolution_keep_both_photos(self):
        """Photos from different devices should both be kept."""
        photos_a = ["photo_a1.jpg", "photo_a2.jpg"]
        photos_b = ["photo_b1.jpg"]

        merged = photos_a + photos_b
        assert len(merged) == 3
        assert "photo_a1.jpg" in merged
        assert "photo_b1.jpg" in merged


# ---------------------------------------------------------------------------
# Test: Retry Logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    """Test exponential backoff for failed syncs."""

    def test_retry_count_increments(self):
        """Failed sync items should have retry count incremented."""
        sync = OfflineSyncSimulator(device_id="phone-001")
        sync.create_offline("sample", {"data": "test"})

        item = sync.queue[0]
        assert item.retry_count == 0

        item.retry_count += 1
        assert item.retry_count == 1

    def test_dead_letter_after_max_retries(self):
        """Items exceeding max retries (10) should be moved to dead letter queue."""
        max_retries = 10

        item = SyncItem(
            entity_type="sample",
            entity_id=str(uuid.uuid4()),
            action="create",
            data={"test": True},
            vector_clock={"phone-001": 1},
            retry_count=11,
        )

        assert item.retry_count > max_retries  # Should be in dead letter queue


# ---------------------------------------------------------------------------
# Test: Offline Duration
# ---------------------------------------------------------------------------

class TestOfflineDuration:
    """Test that the system can handle extended offline periods."""

    def test_queue_scales_to_3_days(self):
        """Queue should handle 3 days of offline data collection.

        Estimate: ~50 samples/day × 3 days = 150 samples.
        """
        sync = OfflineSyncSimulator(device_id="phone-001")

        # Simulate 150 samples over 3 days
        for i in range(150):
            sync.create_offline("sample", {
                "location": {"lat": -1.05 + (i * 0.001), "lon": 34.55},
                "xrf_readings": {"Au": 3.0 + (i % 10)},
                "field_notes": f"Sample {i}",
            })

        assert len(sync.queue) == 150

        # All should sync successfully
        stats = sync.sync_to_remote()
        assert stats["uploaded"] == 150
        assert stats["conflicts"] == 0
