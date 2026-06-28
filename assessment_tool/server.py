"""Tiny stdlib HTTP server for the physics assessment tool.

No third-party dependencies — run with: python3 server.py
Serves the UI and a small JSON API backed by questions.json / results.json.
"""
import argparse
import errno
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import store

BASE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_PATH = os.path.join(BASE, "questions.json")
RESULTS_PATH = os.path.join(BASE, "results.json")
INDEX_PATH = os.path.join(BASE, "index.html")
ASSETS_DIR = os.path.join(BASE, "assets")


def load_questions():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_file(INDEX_PATH, "text/html; charset=utf-8")
        elif self.path == "/api/questions":
            self._send_json(200, load_questions())
        elif self.path == "/api/results":
            self._send_json(200, store.load_results(RESULTS_PATH))
        elif self.path == "/api/summary":
            questions = load_questions()
            results = store.load_results(RESULTS_PATH)
            summary = {s["id"]: store.rollup(results, questions, s["id"])
                       for s in results.get("sessions", [])}
            self._send_json(200, summary)
        elif self.path.startswith("/assets/"):
            self._serve_asset(self.path[len("/assets/"):])
        else:
            self._send_json(404, {"error": "not found"})

    def _serve_asset(self, name):
        # only a bare .svg filename inside assets/ — no path traversal
        if "/" in name or "\\" in name or ".." in name or not name.endswith(".svg"):
            self._send_json(404, {"error": "not found"})
            return
        path = os.path.join(ASSETS_DIR, name)
        if not os.path.isfile(path):
            self._send_json(404, {"error": "not found"})
            return
        self._send_file(path, "image/svg+xml; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/results":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._send_json(400, {"ok": False, "errors": [f"invalid JSON: {exc}"]})
            return
        errors = store.validate_results(data, load_questions())
        if errors:
            self._send_json(400, {"ok": False, "errors": errors})
            return
        store.save_results(RESULTS_PATH, data)
        self._send_json(200, {"ok": True})

    def log_message(self, fmt, *args):  # keep the console quiet
        pass


def main():
    parser = argparse.ArgumentParser(description="Physics assessment tool server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit(
                f"Port {args.port} is already in use by another program.\n"
                f"Start on a different port, e.g.:  python3 server.py --port {args.port + 1}"
            )
        raise
    print(f"Assessment tool running at http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
