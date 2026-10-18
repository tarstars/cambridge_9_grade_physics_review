"""Filtered, paginated question queries with independently persisted progress."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .catalogue import PAPERS, SESSIONS
from .topics import TOPICS, TOPIC_IDS
from .methods import PUBLIC_TYPES, TYPE_IDS, BY_ID

LABELS = {topic["id"]: topic["label"] for topic in TOPICS}
JOIN = """FROM tasks t JOIN documents d ON d.id=t.document_id
          LEFT JOIN progress.marks m ON m.kind='task' AND m.id=t.id
          LEFT JOIN progress.task_categories o ON o.task_id=t.id
          LEFT JOIN progress.task_type_overrides c ON c.task_id=t.id"""
TOPIC = "COALESCE(o.topics,t.topics)"
TYPES = "COALESCE(c.types,(SELECT json_group_array(s.type_id) FROM task_type_suggestions s WHERE s.task_id=t.id))"
STATUS = "COALESCE(m.status,'unmarked')"


class TaskLibrary:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "tasks.sqlite3"
        self._stamp = None
        self._ids = set()
        self._groups = set()

    @contextmanager
    def connect(self):
        if not self.path.exists():
            raise ValueError("Question index is missing. Run python3 -m past_papers.index_tasks")
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("ATTACH DATABASE ? AS progress", (str(self.data_dir / "progress.sqlite3"),))
            yield db
        finally:
            db.close()

    def targets(self):
        if not self.path.exists():
            return set(), set()
        stamp = (self.path.stat().st_mtime_ns, self.path.stat().st_size)
        if stamp != self._stamp:
            with self.connect() as db:
                self._ids = {row[0] for row in db.execute("SELECT id FROM tasks")}
                groups = {f"tasks:topic:{topic}" for topic in TOPIC_IDS}
                groups.update(f"tasks:type:{key}" for key in TYPE_IDS | {"unassigned"})
                for doc in db.execute("SELECT * FROM documents"):
                    groups.update((f"tasks:document:{doc['id']}", f"tasks:year:{doc['year'] or 'undated'}",
                                   f"tasks:paper:{doc['component'] or 'unspecified'}",
                                   f"tasks:session:{doc['year'] or 'undated'}:{doc['session'] or 'unspecified'}"))
                self._groups = groups
            self._stamp = stamp
        return self._ids, self._groups

    def conditions(self, filters, with_status=True, with_topic=True):
        clauses, values = [], []
        for key, column in (("collection", "d.collection"), ("paper", "d.component"),
                            ("year", "d.year"), ("session", "d.session"), ("document", "d.id")):
            value = filters.get(key)
            if value and value != "all":
                clauses.append(column + "=?")
                values.append(str(value))
        if filters.get("structured") == "1":
            clauses.append("COALESCE(d.component,'') != '1'")
        topic = filters.get("topic")
        if topic and with_topic:
            if topic not in TOPIC_IDS:
                raise ValueError("Unknown question topic")
            clauses.append(f"EXISTS(SELECT 1 FROM json_each({TOPIC}) j WHERE j.value=?)")
            values.append(topic)
        task_type = filters.get("type")
        if task_type:
            if task_type == "unassigned":
                clauses.append(f"json_array_length({TYPES})=0")
            elif task_type in TYPE_IDS:
                clauses.append(f"EXISTS(SELECT 1 FROM json_each({TYPES}) j WHERE j.value=?)")
                values.append(task_type)
            else:
                raise ValueError("Unknown task type")
        if filters.get("status") and with_status:
            if filters["status"] not in ("unmarked", "to_process", "know_how", "solved"):
                raise ValueError("Unknown progress status")
            clauses.append(STATUS + "=?")
            values.append(filters["status"])
        if filters.get("review") == "1":
            clauses.append("o.task_id IS NULL AND t.confidence='review'")
        query = str(filters.get("q", ""))[:300]
        for term in query.lower().split()[:12]:
            clauses.append("instr(lower(t.text || ' ' || d.filename || ' ' || COALESCE(m.notes,'')),?)>0")
            values.append(term)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), values

    def grouping(self, filters):
        group = filters.get("group", "topic")
        if group == "type":
            if filters.get("type") in TYPE_IDS | {"unassigned"}:
                return "'tasks:type:" + filters["type"] + "'"
            return "'tasks:type:' || COALESCE(json_extract(" + TYPES + ",'$[0]'),'unassigned')"
        if group == "topic":
            if filters.get("topic") in TOPIC_IDS:
                return "'tasks:topic:" + filters["topic"] + "'"
            return "'tasks:topic:' || json_extract(" + TOPIC + ",'$[0]')"
        if group == "document":
            return "'tasks:document:' || d.id"
        if group == "year":
            return "'tasks:year:' || COALESCE(d.year,'undated')"
        if group == "paper":
            return "'tasks:paper:' || COALESCE(d.component,'unspecified')"
        if group == "session":
            return "'tasks:session:' || COALESCE(d.year,'undated') || ':' || COALESCE(d.session,'unspecified')"
        raise ValueError("Unknown question grouping")

    def group_label(self, key, documents):
        _, kind, value = key.split(":", 2)
        if kind == "topic":
            return LABELS.get(value, value)
        if kind == "type":
            return BY_ID[value]["label"] if value in BY_ID else "Awaiting a task type"
        if kind == "document":
            return documents.get(value, {}).get("filename", value)
        if kind == "year":
            return "Undated topic collections" if value == "undated" else value
        if kind == "paper":
            return f"Paper {value} · {PAPERS.get(value, 'Other questions')}"
        if kind == "session":
            year, session = value.split(":")
            return f"{SESSIONS.get(session, 'Undated')} {year if year != 'undated' else ''}".strip()
        return value

    def group_order(self, filters):
        group = filters.get("group", "topic")
        if group == "type":
            return "CASE WHEN d.component='1' THEN 0 ELSE 1 END, CASE WHEN d.collection='yearly' THEN 0 ELSE 1 END"
        if group == "topic":
            primary = "json_extract(" + TOPIC + ",'$[0]')"
            return "CASE " + primary + " " + " ".join(
                f"WHEN '{topic['id']}' THEN {index}" for index, topic in enumerate(TOPICS)) + " ELSE 999 END"
        if group in ("year", "document"):
            return "COALESCE(d.year,0) DESC"
        if group == "session":
            return "COALESCE(d.year,0) DESC,CASE d.session WHEN 'w' THEN 3 WHEN 's' THEN 2 ELSE 1 END DESC"
        return "CAST(COALESCE(d.component,'99') AS INTEGER)"

    def serialize(self, row, full=False):
        value = dict(row)
        for key in ("topics", "subparts", "task_types", "regions"):
            if key not in value:
                continue
            value[key] = json.loads(value[key])
        value["topic_source"] = "confirmed" if value.pop("override_topics", None) is not None else "suggested"
        value["type_source"] = "confirmed" if value.pop("override_types", None) is not None else "suggested"
        if "regions" in value:
            value["images"] = [{"url": f"/task-images/{value['id']}/{i}.png", "page": region["page"]}
                               for i, region in enumerate(value["regions"])]
        if full:
            value["evidence"] = json.loads(value["evidence"])
            value["document"] = json.loads(value.pop("metadata"))
        return value

    def list(self, filters):
        page = max(1, int(filters.get("page", 1)))
        page_size = min(100, max(1, int(filters.get("page_size", 40))))
        where, params = self.conditions(filters)
        group = self.grouping(filters)
        order = self.group_order(filters)
        tab_where, tab_params = self.conditions(filters, with_status=False)
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) " + JOIN + where, params).fetchone()[0]
            page = min(page, max(1, (total + page_size - 1) // page_size))
            rows = db.execute(f"""SELECT t.id,t.document_id,t.number,t.occurrence,t.page,t.end_page,
                    t.summary,t.subparts,t.regions,{TOPIC} AS topics,t.confidence,o.topics AS override_topics,
                    {TYPES} AS task_types,c.types AS override_types,
                    d.filename,d.year,d.session,d.component,d.collection,
                    {STATUS} AS status,COALESCE(m.notes,'') AS notes,{group} AS group_id
                    {JOIN} {where}
                    ORDER BY {order},group_id,d.year DESC,d.session DESC,d.filename,t.number,t.occurrence
                    LIMIT ? OFFSET ?""", [*params, page_size, (page - 1) * page_size]).fetchall()
            group_rows = db.execute(f"""SELECT {group} AS id,COUNT(*) AS total,
                    SUM({STATUS}='solved') AS solved {JOIN} {where} GROUP BY 1 ORDER BY 1""", params).fetchall()
            documents = {row["id"]: dict(row) for row in db.execute("SELECT id,filename FROM documents")}
            group_marks = {row["id"]: dict(row) for row in db.execute("SELECT * FROM progress.marks WHERE kind='group'")}
            tabs = dict(db.execute(f"SELECT {STATUS},COUNT(*) {JOIN} {tab_where} GROUP BY 1", tab_params).fetchall())
            stats = dict(db.execute(f"SELECT {STATUS},COUNT(*) {JOIN} GROUP BY 1").fetchall())
            topics = dict(db.execute(f"""SELECT j.value,COUNT(DISTINCT t.id) {JOIN}
                                      JOIN json_each({TOPIC}) j GROUP BY j.value""").fetchall())
            meta = dict(db.execute("SELECT key,value FROM metadata").fetchall())
            years = [row[0] for row in db.execute("SELECT DISTINCT year FROM documents WHERE year IS NOT NULL ORDER BY year DESC")]
            papers = dict(db.execute("SELECT d.component,COUNT(*) FROM tasks t JOIN documents d ON d.id=t.document_id GROUP BY d.component").fetchall())
            collections = dict(db.execute("SELECT d.collection,COUNT(*) FROM tasks t JOIN documents d ON d.id=t.document_id GROUP BY d.collection").fetchall())
            issues = [dict(row) for row in db.execute("SELECT id,filename,task_count,state,note FROM documents WHERE state IN ('needs_review','unavailable') ORDER BY filename")]
            doc_count = db.execute("SELECT COUNT(*) FROM documents WHERE task_count>0").fetchone()[0]
        groups = [{**dict(row), "label": self.group_label(row["id"], documents),
                   "status": group_marks.get(row["id"], {}).get("status", "unmarked"),
                   "notes": group_marks.get(row["id"], {}).get("notes", "")} for row in group_rows]
        return {"tasks": [self.serialize(row) for row in rows], "total": total, "page": page,
                "page_size": page_size, "groups": groups, "status_counts": tabs,
                "stats": stats, "topic_counts": topics, "years": years, "paper_counts": papers,
                "collection_counts": collections, "topics": TOPICS, "papers": PAPERS,
                "sessions": SESSIONS, "indexed_at": meta.get("indexed_at"),
                "issues": issues, "document_count": doc_count}

    def get(self, key):
        with self.connect() as db:
            row = db.execute(f"""SELECT t.*, {TOPIC} AS effective_topics,o.topics AS override_topics,
                        d.metadata,d.filename,d.collection,d.year,d.session,d.component,
                        {TYPES} AS task_types,c.types AS override_types,
                        {STATUS} AS status,COALESCE(m.notes,'') AS notes
                        {JOIN} WHERE t.id=?""", (key,)).fetchone()
        if row is None:
            return None
        row = dict(row)
        row["suggested_topics"] = json.loads(row["topics"])
        row["topics"] = row.pop("effective_topics")
        return self.serialize(row, full=True)

    def types(self, filters):
        """One specific pattern per card, with an original question as a sample."""
        filters = {key: value for key, value in filters.items() if key not in ("type", "group", "page", "q")}
        where, params = self.conditions(filters)
        with self.connect() as db:
            rows = db.execute(f"""SELECT t.id,t.number,t.page,t.end_page,t.regions,
                t.document_id,d.filename,d.year,d.collection,d.component,{TYPES} AS types,
                {STATUS} AS status FROM tasks t JOIN documents d ON d.id=t.document_id
                LEFT JOIN progress.marks m ON m.kind='task' AND m.id=t.id
                LEFT JOIN progress.task_categories o ON o.task_id=t.id
                LEFT JOIN progress.task_type_overrides c ON c.task_id=t.id {where}""", params).fetchall()
            marks = {row['id']: dict(row) for row in db.execute("SELECT * FROM progress.marks WHERE kind='group'")}
        cards = {item["id"]: {**item, "total": 0, "solved": 0, "know_how": 0, "to_process": 0,
                                      "unmarked": 0, "sample": None} for item in PUBLIC_TYPES}
        cards["unassigned"] = {"id": "unassigned", "topic": "unclassified", "label": "Awaiting a task type",
            "approach": "These questions do not yet have a reliable specific pattern. Read a question and assign a type when you recognise its approach.",
            "total": 0, "solved": 0, "know_how": 0, "to_process": 0, "unmarked": 0, "sample": None}
        assigned = 0
        for row in rows:
            keys = json.loads(row["types"])
            assigned += bool(keys)
            for key in keys or ["unassigned"]:
                if key not in cards:
                    continue
                card = cards[key]
                card["total"] += 1
                card[row["status"]] += 1
                rank = (row["component"] != "1", row["collection"] != "yearly", -(row["year"] or 0),
                        row["end_page"] - row["page"], row["number"])
                if card["sample"] is None or rank < card["sample"]["rank"]:
                    card["sample"] = {**dict(row), "rank": rank,
                                      "image": f"/task-images/{row['id']}/0.png"}
        for card in cards.values():
            mark = marks.get("tasks:type:" + card["id"], {})
            card.update(status=mark.get("status", "unmarked"), notes=mark.get("notes", ""))
            if card["sample"]:
                card["sample"] = {key: value for key, value in card["sample"].items()
                                  if key not in ("rank", "types", "regions")}
        return {"types": list(cards.values()), "topics": TOPICS, "total": len(rows),
                "assigned": assigned, "unassigned": len(rows) - assigned}

    def bulk_ids(self, filters, group_id=None):
        where, params = self.conditions(filters)
        if group_id:
            where += (" AND " if where else " WHERE ") + self.grouping(filters) + "=?"
            params.append(group_id)
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT t.id " + JOIN + where, params)]
