"""Local Python/SQLite study dashboard. Run: python3 -m past_papers.server"""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
from urllib.parse import quote, urlsplit, parse_qs

from .catalogue import BASE, KINDS, PAPERS, SESSIONS, build_tests, load_catalogue
from .store import STATUSES, Store
from .task_library import TaskLibrary
from .task_previews import render_question, answer_page
from .methods import VERSION as TYPE_VERSION
from .index_types import index_types

TASK_KEY = r"[a-f0-9]{20}-q\d{1,5}(?:-o\d+)?"


class StudyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir, catalogue_path):
        self.data_dir = Path(data_dir).resolve()
        self.catalogue_path = Path(catalogue_path)
        self.store = Store(self.data_dir / "progress.sqlite3")
        self.tasks = TaskLibrary(self.data_dir)
        if self.tasks.path.exists():
            with sqlite3.connect(self.tasks.path) as db:
                version = db.execute("SELECT value FROM metadata WHERE key='type_rules_version'").fetchone()
            if not version or version[0] != TYPE_VERSION:
                index_types(self.tasks.path)
        self.render_lock = threading.Lock()
        super().__init__(address, Handler)

    def library(self):
        catalogue = load_catalogue(self.catalogue_path)
        documents = catalogue["documents"]
        try:
            report = json.loads((self.data_dir / "download-report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report = {}
        download_errors = {item["id"]: item["error"] for item in report.get("errors", [])}
        files = {}
        for doc in documents:
            path = self.file_path(doc)
            available = path is not None and path.is_file()
            files[doc["id"]] = {"filename": doc["filename"], "url": doc["url"],
                                 "available": available, "bytes": path.stat().st_size if available else 0,
                                 "error": download_errors.get(doc["id"]) if not available else None}
        tests, resources = build_tests(documents)
        return {"tests": tests, "resources": resources, "files": files,
                "source": catalogue["source"], "synced_at": catalogue.get("synced_at"),
                "index_errors": catalogue.get("errors", []), "statuses": STATUSES,
                "papers": PAPERS, "sessions": SESSIONS, "kinds": KINDS}

    def file_path(self, doc):
        path = (self.data_dir / doc["local_path"]).resolve()
        return path if path.is_relative_to(self.data_dir / "papers") else None

    def task_detail(self, key):
        task = self.tasks.get(key)
        if task is None:
            return None
        document = task["document"]
        by_id = {doc["id"]: doc for doc in load_catalogue(self.catalogue_path)["documents"]}
        files = []
        for reference in [{"id": document["id"], "label": "Source question paper"}, *document.get("attachments", [])]:
            doc = by_id.get(reference["id"])
            if doc is None:
                continue
            path = self.file_path(doc)
            available = path is not None and path.is_file()
            page = task["page"] if doc["id"] == document["id"] else None
            if reference.get("kind") == "ms" and available and doc.get("variant") and task["occurrence"] == 1:
                page = answer_page(path, task["number"], self.data_dir / "text-cache", document.get("component") == "1")
            url = f"/files/{doc['id']}" if available else doc["url"]
            if page:
                url += f"#page={page}"
            files.append({"id": doc["id"], "label": reference["label"], "filename": doc["filename"],
                          "available": available, "url": url, "page": page})
        task["files"] = files
        task["images"] = [{"url": f"/task-images/{key}/{i}.png", "page": region["page"]}
                          for i, region in enumerate(task["regions"])]
        return task


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True  # normal when a PDF or preview tab is closed

    def respond(self, status, body, content_type="application/json; charset=utf-8", headers=None, head=False):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html", "/questions", "/papers", "/app.js", "/style.css", "/tasks.js", "/tasks.css", "/types.js", "/types.css"):
            filename = "types.html" if path in ("/", "/index.html") else "tasks.html" if path == "/questions" else "index.html" if path == "/papers" else path[1:]
            content_type = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                            "style.css": "text/css; charset=utf-8", "tasks.html": "text/html; charset=utf-8",
                            "tasks.js": "text/javascript; charset=utf-8", "tasks.css": "text/css; charset=utf-8",
                            "types.html": "text/html; charset=utf-8", "types.js": "text/javascript; charset=utf-8", "types.css": "text/css; charset=utf-8"}[filename]
            self.respond(200, (BASE / "static" / filename).read_bytes(), content_type, head=head)
        elif path == "/api/library":
            self.respond(200, self.server.library(), head=head)
        elif path == "/api/state":
            self.respond(200, self.server.store.all(), head=head)
        elif path == "/api/export":
            self.respond(200, {"version": 2, "exported_at": datetime.now(timezone.utc).isoformat(),
                               "marks": self.server.store.all()},
                         headers={"Content-Disposition": 'attachment; filename="physics-progress.json"'}, head=head)
        elif path == "/api/tasks":
            try:
                filters = {key: values[0] for key, values in parse_qs(urlsplit(self.path).query).items()}
                self.respond(200, self.server.tasks.list(filters), head=head)
            except (ValueError, sqlite3.Error) as exc:
                self.respond(400, {"error": str(exc)}, head=head)
        elif path == "/api/task-types":
            try:
                filters = {key: values[0] for key, values in parse_qs(urlsplit(self.path).query).items()}
                self.respond(200, self.server.tasks.types(filters), head=head)
            except (ValueError, sqlite3.Error) as exc:
                self.respond(400, {"error": str(exc)}, head=head)
        elif re.fullmatch(r"/api/tasks/" + TASK_KEY, path):
            try:
                task = self.server.task_detail(path.rsplit("/", 1)[-1])
                self.respond(200 if task else 404, task or {"error": "Question not found"}, head=head)
            except (ValueError, sqlite3.Error) as exc:
                self.respond(400, {"error": str(exc)}, head=head)
        elif re.fullmatch(r"/task-images/" + TASK_KEY + r"/\d+\.png", path):
            self.serve_task_image(path, head)
        elif re.fullmatch(r"/files/[a-f0-9]{20}", path):
            self.serve_pdf(path.rsplit("/", 1)[-1], head)
        else:
            self.respond(404, {"error": "Not found"}, head=head)

    def serve_task_image(self, path, head):
        _, _, key, region = path.split("/")
        try:
            task = self.server.tasks.get(key)
            if task is None:
                raise ValueError("Question not found")
            pdf = self.server.file_path(task["document"])
            if pdf is None or not pdf.is_file():
                raise ValueError("Source PDF is unavailable")
            with self.server.render_lock:
                image = render_question(task, int(region[:-4]), pdf, self.server.data_dir,
                                        self.server.tasks.path.stat().st_mtime_ns,
                                        compact=parse_qs(urlsplit(self.path).query).get("compact") == ["1"])
            self.respond(200, image.read_bytes(), "image/png", head=head)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
            self.respond(400, {"error": str(exc)}, head=head)

    def serve_pdf(self, key, head):
        doc = next((d for d in load_catalogue(self.server.catalogue_path)["documents"] if d["id"] == key), None)
        path = self.server.file_path(doc) if doc else None
        if path is None or not path.is_file():
            self.respond(404, {"error": "PDF not downloaded. Run python3 -m past_papers.sync --download-only"}, head=head)
            return
        size, start, end, status = path.stat().st_size, 0, path.stat().st_size - 1, 200
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match or not any(match.groups()):
                self.respond(416, {"error": "Invalid range"}, headers={"Content-Range": f"bytes */{size}"}, head=head)
                return
            first, last = match.groups()
            if first:
                start, end = int(first), min(int(last), size - 1) if last else size - 1
            else:
                start = max(0, size - int(last))
            if start > end or start >= size:
                self.respond(416, {"error": "Range outside PDF"}, headers={"Content-Range": f"bytes */{size}"}, head=head)
                return
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Disposition", "inline; filename*=UTF-8''" + quote(doc["filename"], safe=""))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if not head:
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(262144, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/api/marks", "/api/import", "/api/task-bulk"):
            self.respond(404, {"error": "Not found"})
            return
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.close_connection = True
            self.respond(403, {"error": "Cross-origin changes are not allowed"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 20_000_000:
                raise ValueError("Request must be between 1 byte and 20 MB")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Use application/json")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            library = self.server.library()
            valid_tests = {t["id"] for t in library["tests"]}
            valid_groups = {group for test in library["tests"] for group in test["groups"]}
            valid_tasks, task_groups = self.server.tasks.targets()
            valid_groups |= task_groups
            if path == "/api/import":
                if data.get("version") not in (1, 2) or not isinstance(data.get("marks"), dict):
                    raise ValueError("Unsupported progress backup")
                updates = []
                for kind in ("test", "task", "group"):
                    marks = data["marks"].get(kind, {})
                    if not isinstance(marks, dict):
                        raise ValueError("Invalid progress backup")
                    for key, mark in marks.items():
                        if not isinstance(mark, dict):
                            raise ValueError("Invalid mark in backup")
                        updates.append({"kind": kind, "id": key, "status": mark.get("status"),
                                        "notes": mark.get("notes", "")})
                topics = data["marks"].get("topics", {})
                types = data["marks"].get("types", {})
                result = self.server.store.save(updates, valid_tests, valid_groups, valid_tasks, topics, types) if updates or topics or types else self.server.store.all()
            elif path == "/api/task-bulk":
                if not isinstance(data.get("filters"), dict):
                    raise ValueError("Supply the question filters")
                ids = self.server.tasks.bulk_ids(data["filters"], data.get("group_id"))
                if not ids:
                    raise ValueError("No questions match this selection")
                result = self.server.store.save([{"kind": "task", "id": key, "status": data.get("status")}
                                                for key in ids], valid_tests, valid_groups, valid_tasks)
                result["updated_count"] = len(ids)
            else:
                result = self.server.store.save(data.get("updates", []), valid_tests, valid_groups, valid_tasks, data.get("topics"), data.get("types"))
            self.respond(200, result)
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            self.close_connection = True
            self.respond(400, {"error": str(exc)})
        except sqlite3.Error:
            self.respond(503, {"error": "Could not save progress. Please retry."})

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--data-dir", type=Path, default=BASE / "data")
    parser.add_argument("--catalogue", type=Path, default=BASE / "catalogue.json")
    args = parser.parse_args()
    try:
        server = StudyServer((args.host, args.port), args.data_dir, args.catalogue)
    except OSError as exc:
        raise SystemExit(f"Cannot start study library on {args.host}:{args.port}: {exc}") from exc
    print(f"Physics question bank: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
