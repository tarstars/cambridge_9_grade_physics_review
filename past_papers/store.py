"""Transactional study marks, independent of the downloadable catalogue."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from .topics import TOPIC_IDS
from .methods import TYPE_IDS

STATUSES = {"unmarked": "Not marked", "to_process": "To process",
            "know_how": "Know how to solve", "solved": "Solved"}


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='marks'").fetchone()
            migrate = existing is not None and "'task'" not in existing[0]
            if migrate:
                db.execute("ALTER TABLE marks RENAME TO marks_legacy")
            db.execute("""CREATE TABLE IF NOT EXISTS marks (
                kind TEXT NOT NULL CHECK(kind IN ('test', 'task', 'group')),
                id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'unmarked',
                notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
                PRIMARY KEY(kind, id))""")
            if migrate:
                db.execute("INSERT INTO marks SELECT * FROM marks_legacy")
                db.execute("DROP TABLE marks_legacy")
            db.execute("""CREATE TABLE IF NOT EXISTS task_categories (
                task_id TEXT PRIMARY KEY, topics TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS task_type_overrides (
                task_id TEXT PRIMARY KEY, types TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def all(self):
        with closing(self.connect()) as db:
            rows = db.execute("SELECT * FROM marks ORDER BY kind, id").fetchall()
            categories = db.execute("SELECT task_id,topics FROM task_categories").fetchall()
            types = db.execute("SELECT task_id,types FROM task_type_overrides").fetchall()
        return {**{kind: {r["id"]: dict(r) for r in rows if r["kind"] == kind}
                   for kind in ("test", "task", "group")},
                "topics": {row["task_id"]: json.loads(row["topics"]) for row in categories},
                "types": {row["task_id"]: json.loads(row["types"]) for row in types}}

    def save(self, updates, valid_tests, valid_groups, valid_tasks=None, topic_updates=None, type_updates=None,
             preserve_timestamps=False):
        valid_tasks = valid_tasks or set()
        if not isinstance(updates, list) or (not updates and not topic_updates and not type_updates) or len(updates) > 50000:
            raise ValueError("Supply between 1 and 50000 updates")
        for value in updates:
            if not isinstance(value, dict):
                raise ValueError("Each update must be an object")
            kind, key = value.get("kind"), value.get("id")
            if kind not in ("test", "task", "group") or not isinstance(key, str):
                raise ValueError("Invalid mark target")
            if key not in {"test": valid_tests, "group": valid_groups, "task": valid_tasks}[kind]:
                raise ValueError("Unknown paper, task, or group")
            if "status" in value and (not isinstance(value["status"], str) or value["status"] not in STATUSES):
                raise ValueError("Invalid study status")
            if "notes" in value and (not isinstance(value["notes"], str) or len(value["notes"]) > 20000):
                raise ValueError("Notes must be text, up to 20000 characters")
            if "status" not in value and "notes" not in value:
                raise ValueError("Supply a status or notes")
            if preserve_timestamps and "updated_at" in value:
                try:
                    timestamp = datetime.fromisoformat(value["updated_at"])
                    if timestamp.tzinfo is None:
                        raise ValueError("Progress timestamps must include a timezone")
                except (TypeError, ValueError) as exc:
                    raise ValueError("Invalid progress timestamp") from exc
        if topic_updates is not None:
            if not isinstance(topic_updates, dict) or len(topic_updates) > 50000:
                raise ValueError("Invalid topic updates")
            for key, topics in topic_updates.items():
                if key not in valid_tasks:
                    raise ValueError("Unknown task for topic correction")
                if topics is not None and (not isinstance(topics, list) or not 1 <= len(topics) <= 5
                        or any(not isinstance(topic, str) or topic not in TOPIC_IDS for topic in topics)
                        or len(set(topics)) != len(topics) or ("unclassified" in topics and len(topics) != 1)):
                    raise ValueError("Choose between 1 and 5 valid topics")
        if type_updates is not None:
            if not isinstance(type_updates, dict) or len(type_updates) > 50000:
                raise ValueError("Invalid task-type updates")
            for key, types in type_updates.items():
                if key not in valid_tasks:
                    raise ValueError("Unknown task for type correction")
                if types is not None and (not isinstance(types, list) or len(types) > 12
                        or any(not isinstance(item, str) or item not in TYPE_IDS for item in types)
                        or len(set(types)) != len(types)):
                    raise ValueError("Choose up to 12 valid task types")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db, db:
            for value in updates:
                db.execute("""INSERT INTO marks(kind,id,status,notes,updated_at)
                    VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET
                    status=CASE WHEN ? THEN excluded.status ELSE marks.status END,
                    notes=CASE WHEN ? THEN excluded.notes ELSE marks.notes END,
                    updated_at=excluded.updated_at""",
                           (value["kind"], value["id"], value.get("status", "unmarked"),
                            value.get("notes", ""), value.get("updated_at", now) if preserve_timestamps else now,
                            "status" in value, "notes" in value))
            for key, topics in (topic_updates or {}).items():
                if topics is None:
                    db.execute("DELETE FROM task_categories WHERE task_id=?", (key,))
                else:
                    db.execute("""INSERT INTO task_categories VALUES(?,?,?) ON CONFLICT(task_id)
                                  DO UPDATE SET topics=excluded.topics,updated_at=excluded.updated_at""",
                               (key, json.dumps(topics), now))
            for key, types in (type_updates or {}).items():
                if types is None:
                    db.execute("DELETE FROM task_type_overrides WHERE task_id=?", (key,))
                else:
                    db.execute("""INSERT INTO task_type_overrides VALUES(?,?,?) ON CONFLICT(task_id)
                                  DO UPDATE SET types=excluded.types,updated_at=excluded.updated_at""",
                               (key, json.dumps(types), now))
        return self.all()
