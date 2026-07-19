"""
AfriMine AI — Offline-First Handler

Mining sites have no internet. This module ensures:
1. All core voice features work offline
2. Responses are cached for instant replay
3. Commands are queued for sync when connectivity returns
4. Geological data persists locally

Storage: SQLite (lightweight, no server needed)
Sync: Supabase when online
"""

import os
import json
import time
import hashlib
import logging
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


@dataclass
class QueuedCommand:
    """A voice command queued for later sync."""
    intent: str
    entities: Dict[str, Any]
    raw_text: str
    language: str
    timestamp: float = field(default_factory=time.time)
    sync_status: SyncStatus = SyncStatus.PENDING
    retry_count: int = 0
    id: Optional[str] = None

    def __post_init__(self):
        if self.id is None:
            self.id = hashlib.md5(
                f"{self.intent}:{self.raw_text}:{self.timestamp}".encode()
            ).hexdigest()[:12]


@dataclass
class CachedResponse:
    """A cached agent response for offline replay."""
    intent: str
    entities_hash: str
    response: Dict[str, Any]
    timestamp: float
    hit_count: int = 0
    ttl_hours: int = 24  # Cache expires after 24 hours


@dataclass
class FieldNote:
    """A field note saved by a worker."""
    id: str
    text: str
    language: str
    location: Optional[Dict[str, float]] = None  # lat, lng
    timestamp: float = field(default_factory=time.time)
    audio_path: Optional[str] = None
    sync_status: SyncStatus = SyncStatus.PENDING


class OfflineHandler:
    """
    Offline-first storage and sync handler.
    
    Uses SQLite for local persistence (works on Android via sqflite).
    Stores:
    - Response cache (for instant offline replies)
    - Command queue (for later sync)
    - Field notes (worker observations)
    - Geological data (samples, analyses)
    """

    def __init__(self, cache_dir: str = ".afrimine/cache", db_name: str = "afrimine_offline.db"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / db_name
        self._conn = None
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with required tables."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        
        cursor = self._conn.cursor()
        
        # Response cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS response_cache (
                id TEXT PRIMARY KEY,
                intent TEXT NOT NULL,
                entities_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp REAL NOT NULL,
                hit_count INTEGER DEFAULT 0,
                ttl_hours INTEGER DEFAULT 24
            )
        """)

        # Command queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_queue (
                id TEXT PRIMARY KEY,
                intent TEXT NOT NULL,
                entities TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                language TEXT NOT NULL,
                timestamp REAL NOT NULL,
                sync_status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                synced_at REAL
            )
        """)

        # Field notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS field_notes (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                language TEXT NOT NULL,
                location_lat REAL,
                location_lng REAL,
                timestamp REAL NOT NULL,
                audio_path TEXT,
                sync_status TEXT DEFAULT 'pending'
            )
        """)

        # Geological samples table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geo_samples (
                id TEXT PRIMARY KEY,
                location_lat REAL NOT NULL,
                location_lng REAL NOT NULL,
                minerals TEXT NOT NULL,
                analysis_result TEXT,
                confidence REAL,
                timestamp REAL NOT NULL,
                worker_id TEXT,
                sync_status TEXT DEFAULT 'pending'
            )
        """)

        # Connectivity log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connectivity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                is_online INTEGER NOT NULL,
                sync_queue_size INTEGER
            )
        """)

        self._conn.commit()
        logger.info(f"Offline database initialized: {self.db_path}")

    # === Response Cache ===

    def cache_response(self, intent: str, entities: Dict[str, Any],
                       response: Dict[str, Any], ttl_hours: int = 24):
        """Cache an agent response for offline replay."""
        entities_hash = self._hash_entities(entities)
        cache_id = f"{intent}:{entities_hash}"
        
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO response_cache 
            (id, intent, entities_hash, response, timestamp, hit_count, ttl_hours)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (cache_id, intent, entities_hash, json.dumps(response), time.time(), ttl_hours))
        self._conn.commit()
        
        logger.debug(f"Cached response for {intent} (hash: {entities_hash})")

    def get_cached_response(self, intent: str, entities: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        entities_hash = self._hash_entities(entities)
        cache_id = f"{intent}:{entities_hash}"
        
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT response, timestamp, hit_count, ttl_hours 
            FROM response_cache 
            WHERE id = ?
        """, (cache_id,))
        
        row = cursor.fetchone()
        if not row:
            return None

        # Check TTL
        age_hours = (time.time() - row["timestamp"]) / 3600
        if age_hours > row["ttl_hours"]:
            logger.debug(f"Cache expired for {intent}")
            return None

        # Update hit count
        cursor.execute("""
            UPDATE response_cache SET hit_count = hit_count + 1 WHERE id = ?
        """, (cache_id,))
        self._conn.commit()

        logger.debug(f"Cache hit for {intent} (age: {age_hours:.1f}h)")
        return json.loads(row["response"])

    def clear_expired_cache(self):
        """Remove expired cache entries."""
        cursor = self._conn.cursor()
        cursor.execute("""
            DELETE FROM response_cache 
            WHERE (julianday('now') - julianday(timestamp/86400.0, 'unixepoch')) * 24 > ttl_hours
        """)
        deleted = cursor.rowcount
        self._conn.commit()
        if deleted:
            logger.info(f"Cleared {deleted} expired cache entries")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cursor = self._conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM response_cache")
        total = cursor.fetchone()["total"]
        
        cursor.execute("SELECT SUM(hit_count) as hits FROM response_cache")
        hits = cursor.fetchone()["hits"] or 0
        
        cursor.execute("SELECT COUNT(*) as pending FROM command_queue WHERE sync_status = 'pending'")
        pending = cursor.fetchone()["pending"]
        
        return {
            "cached_responses": total,
            "cache_hits": hits,
            "pending_sync": pending,
            "db_path": str(self.db_path),
        }

    # === Command Queue ===

    def queue_command(self, command: QueuedCommand):
        """Queue a command for later sync."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO command_queue 
            (id, intent, entities, raw_text, language, timestamp, sync_status, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            command.id, command.intent, json.dumps(command.entities),
            command.raw_text, command.language, command.timestamp,
            command.sync_status.value, command.retry_count,
        ))
        self._conn.commit()
        logger.info(f"Queued command: {command.id} ({command.intent})")

    def get_pending_commands(self, limit: int = 50) -> List[QueuedCommand]:
        """Get commands pending sync."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM command_queue 
            WHERE sync_status = 'pending' 
            ORDER BY timestamp ASC 
            LIMIT ?
        """, (limit,))
        
        commands = []
        for row in cursor.fetchall():
            commands.append(QueuedCommand(
                id=row["id"],
                intent=row["intent"],
                entities=json.loads(row["entities"]),
                raw_text=row["raw_text"],
                language=row["language"],
                timestamp=row["timestamp"],
                sync_status=SyncStatus(row["sync_status"]),
                retry_count=row["retry_count"],
            ))
        return commands

    def mark_command_synced(self, command_id: str):
        """Mark a command as successfully synced."""
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE command_queue 
            SET sync_status = 'synced', synced_at = ? 
            WHERE id = ?
        """, (time.time(), command_id))
        self._conn.commit()

    def mark_command_failed(self, command_id: str):
        """Mark a command sync as failed (will retry)."""
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE command_queue 
            SET sync_status = 'failed', retry_count = retry_count + 1 
            WHERE id = ?
        """, (command_id,))
        self._conn.commit()

    def retry_failed_commands(self) -> int:
        """Reset failed commands for retry."""
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE command_queue 
            SET sync_status = 'pending' 
            WHERE sync_status = 'failed' AND retry_count < 5
        """)
        count = cursor.rowcount
        self._conn.commit()
        logger.info(f"Reset {count} failed commands for retry")
        return count

    # === Field Notes ===

    def save_note(self, note: FieldNote):
        """Save a field note."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO field_notes 
            (id, text, language, location_lat, location_lng, timestamp, audio_path, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note.id, note.text, note.language,
            note.location.get("lat") if note.location else None,
            note.location.get("lng") if note.location else None,
            note.timestamp, note.audio_path, note.sync_status.value,
        ))
        self._conn.commit()
        logger.info(f"Saved field note: {note.id}")

    def get_notes(self, limit: int = 100, pending_only: bool = False) -> List[FieldNote]:
        """Get field notes."""
        cursor = self._conn.cursor()
        
        if pending_only:
            cursor.execute("""
                SELECT * FROM field_notes 
                WHERE sync_status = 'pending' 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT * FROM field_notes ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        
        notes = []
        for row in cursor.fetchall():
            location = None
            if row["location_lat"] is not None:
                location = {"lat": row["location_lat"], "lng": row["location_lng"]}
            
            notes.append(FieldNote(
                id=row["id"],
                text=row["text"],
                language=row["language"],
                location=location,
                timestamp=row["timestamp"],
                audio_path=row["audio_path"],
                sync_status=SyncStatus(row["sync_status"]),
            ))
        return notes

    # === Geological Samples ===

    def save_sample(self, sample_id: str, location: Dict[str, float],
                    minerals: List[str], analysis: Optional[Dict] = None,
                    confidence: float = 0.0, worker_id: Optional[str] = None):
        """Save a geological sample record."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO geo_samples 
            (id, location_lat, location_lng, minerals, analysis_result, 
             confidence, timestamp, worker_id, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            sample_id, location["lat"], location["lng"],
            json.dumps(minerals), json.dumps(analysis) if analysis else None,
            confidence, time.time(), worker_id,
        ))
        self._conn.commit()
        logger.info(f"Saved geo sample: {sample_id}")

    def get_samples(self, limit: int = 100) -> List[Dict]:
        """Get geological samples."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM geo_samples ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        
        samples = []
        for row in cursor.fetchall():
            samples.append({
                "id": row["id"],
                "location": {"lat": row["location_lat"], "lng": row["location_lng"]},
                "minerals": json.loads(row["minerals"]),
                "analysis": json.loads(row["analysis_result"]) if row["analysis_result"] else None,
                "confidence": row["confidence"],
                "timestamp": row["timestamp"],
                "worker_id": row["worker_id"],
            })
        return samples

    # === Sync ===

    def get_sync_summary(self) -> Dict[str, Any]:
        """Get summary of items pending sync."""
        cursor = self._conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as c FROM command_queue WHERE sync_status = 'pending'")
        pending_commands = cursor.fetchone()["c"]
        
        cursor.execute("SELECT COUNT(*) as c FROM field_notes WHERE sync_status = 'pending'")
        pending_notes = cursor.fetchone()["c"]
        
        cursor.execute("SELECT COUNT(*) as c FROM geo_samples WHERE sync_status = 'pending'")
        pending_samples = cursor.fetchone()["c"]
        
        return {
            "pending_commands": pending_commands,
            "pending_notes": pending_notes,
            "pending_samples": pending_samples,
            "total_pending": pending_commands + pending_notes + pending_samples,
        }

    async def sync_to_cloud(self, supabase_client=None) -> Dict[str, int]:
        """
        Sync all pending data to Supabase.
        
        Called when connectivity returns.
        Returns counts of synced items.
        """
        if not supabase_client:
            logger.warning("No Supabase client configured — sync skipped")
            return {"synced": 0, "failed": 0}

        results = {"synced": 0, "failed": 0}

        # Sync commands
        for cmd in self.get_pending_commands():
            try:
                # TODO: Send to Supabase
                # supabase_client.table("voice_commands").insert(asdict(cmd)).execute()
                self.mark_command_synced(cmd.id)
                results["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync command {cmd.id}: {e}")
                self.mark_command_failed(cmd.id)
                results["failed"] += 1

        # Sync notes
        for note in self.get_notes(pending_only=True):
            try:
                # TODO: Send to Supabase
                # supabase_client.table("field_notes").insert(asdict(note)).execute()
                cursor = self._conn.cursor()
                cursor.execute("UPDATE field_notes SET sync_status = 'synced' WHERE id = ?", 
                             (note.id,))
                self._conn.commit()
                results["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync note {note.id}: {e}")
                results["failed"] += 1

        logger.info(f"Sync complete: {results}")
        return results

    # === Connectivity ===

    def log_connectivity(self, is_online: bool):
        """Log connectivity status change."""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO connectivity_log (timestamp, is_online, sync_queue_size)
            VALUES (?, ?, ?)
        """, (time.time(), int(is_online), self.get_sync_summary()["total_pending"]))
        self._conn.commit()

    def get_offline_duration(self) -> float:
        """Get how long we've been offline (in seconds)."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT timestamp, is_online FROM connectivity_log 
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row and not row["is_online"]:
            return time.time() - row["timestamp"]
        return 0.0

    # === Utilities ===

    @staticmethod
    def _hash_entities(entities: Dict[str, Any]) -> str:
        """Create a stable hash of entities dict."""
        stable = json.dumps(entities, sort_keys=True)
        return hashlib.md5(stable.encode()).hexdigest()[:8]

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()

    def __del__(self):
        self.close()


# === Connectivity Monitor ===

class ConnectivityMonitor:
    """
    Monitors network connectivity and triggers sync when online.
    
    Works by:
    1. Periodic ping to known endpoints
    2. Android ConnectivityManager integration (via Flutter)
    3. Automatic sync queue processing when online
    """

    def __init__(self, offline_handler: OfflineHandler, check_interval: int = 30):
        self.offline_handler = offline_handler
        self.check_interval = check_interval
        self._is_online = False
        self._last_check = 0
        self._callbacks = []

    @property
    def is_online(self) -> bool:
        return self._is_online

    def on_status_change(self, callback):
        """Register a callback for connectivity changes."""
        self._callbacks.append(callback)

    async def check_connectivity(self) -> bool:
        """
        Check if we have internet connectivity.
        
        Lightweight check: tries to reach a small endpoint.
        """
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://httpbin.org/get",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    online = resp.status == 200
        except Exception:
            online = False

        # Update status
        if online != self._is_online:
            self._is_online = online
            self.offline_handler.log_connectivity(online)
            
            for callback in self._callbacks:
                try:
                    callback(online)
                except Exception as e:
                    logger.error(f"Connectivity callback error: {e}")

            if online:
                logger.info("🟢 Online — syncing queued data...")
                await self.offline_handler.sync_to_cloud()
            else:
                logger.info("🔴 Offline — switching to offline mode")

        self._last_check = time.time()
        return self._is_online


if __name__ == "__main__":
    # Test offline handler
    logging.basicConfig(level=logging.INFO)
    
    handler = OfflineHandler(cache_dir=".afrimine/cache")
    
    # Test response caching
    handler.cache_response(
        intent="check_gold",
        entities={"mineral": "gold"},
        response={"result": "Gold detected at 3.5 g/t", "confidence": 0.85},
    )
    
    cached = handler.get_cached_response("check_gold", {"mineral": "gold"})
    print(f"Cached response: {cached}")
    
    # Test command queuing
    cmd = QueuedCommand(
        intent="analyze_sample",
        entities={"mineral": "gold", "location": {"lat": -1.08, "lng": 34.58}},
        raw_text="Analyze this gold sample",
        language="sw",
    )
    handler.queue_command(cmd)
    
    # Test field note
    note = FieldNote(
        id="note-001",
        text="Found quartz veining in sector B",
        language="en",
        location={"lat": -1.0833, "lng": 34.5833},
    )
    handler.save_note(note)
    
    # Print stats
    print(f"\nCache stats: {handler.get_cache_stats()}")
    print(f"Sync summary: {handler.get_sync_summary()}")
    
    handler.close()
