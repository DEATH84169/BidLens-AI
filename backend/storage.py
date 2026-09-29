"""SQLite snapshots and append-only hash-linked events (not immutable storage)."""

from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


@contextmanager
def connection():
    path = Path(
        os.getenv(
            "BIDLENS_DB_PATH", str(Path(__file__).parent / "state" / "bidlens.sqlite3")
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS records (
          kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
          aggregate_id TEXT NOT NULL, payload TEXT NOT NULL,
          previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
    """)
    try:
        with db:
            yield db
    finally:
        db.close()


def put(kind, key, value):
    with connection() as db:
        db.execute("INSERT INTO records VALUES (?,?,?)", (kind, key, canonical(value)))


def get(kind, key):
    with connection() as db:
        row = db.execute(
            "SELECT payload FROM records WHERE kind=? AND id=?", (kind, key)
        ).fetchone()
    return json.loads(row[0]) if row else None


def listing(kind):
    with connection() as db:
        rows = db.execute(
            "SELECT payload FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)
        ).fetchall()
    return [json.loads(r[0]) for r in rows]


def append_event(aggregate_id, event_type, actor, data):
    event = {
        "id": str(uuid.uuid4()),
        "aggregate_id": aggregate_id,
        "type": event_type,
        "actor": actor,
        "timestamp": now(),
        "data": data,
    }
    body = canonical(event)
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        previous = row[0] if row else "0" * 64
        digest = hashlib.sha256((previous + body).encode()).hexdigest()
        db.execute(
            "INSERT INTO events(id,aggregate_id,payload,previous_hash,event_hash) VALUES (?,?,?,?,?)",
            (event["id"], aggregate_id, body, previous, digest),
        )
    return {**event, "previous_hash": previous, "event_hash": digest}


def events(aggregate_id):
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM events WHERE aggregate_id=? ORDER BY seq", (aggregate_id,)
        ).fetchall()
    return [
        {
            **json.loads(r["payload"]),
            "previous_hash": r["previous_hash"],
            "event_hash": r["event_hash"],
        }
        for r in rows
    ]


def verify_chain():
    previous = "0" * 64
    with connection() as db:
        rows = db.execute("SELECT * FROM events ORDER BY seq").fetchall()
    for row in rows:
        expected = hashlib.sha256((previous + row["payload"]).encode()).hexdigest()
        if row["previous_hash"] != previous or row["event_hash"] != expected:
            return {
                "valid": False,
                "checked_events": len(rows),
                "broken_sequence": row["seq"],
            }
        previous = expected
    return {
        "valid": True,
        "checked_events": len(rows),
        "head_hash": previous,
        "limitation": "Local integrity check; not independently anchored or immutable storage.",
    }
