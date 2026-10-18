"""Regression checks for persistence, archive parsing, and the real HTTP API."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from .catalogue import SOURCE, atomic_json, build_tests, document, parse_page
from .server import StudyServer
from .store import Store
from .sync import download, valid_pdf


class CatalogueTests(unittest.TestCase):
    def test_crawl_stays_within_subject_and_extracts_encoded_pdf(self):
        html = '''<a href="papers/caie/as-and-a-level-physics-9702-2026-march">2026 March</a>
        <a href="papers/caie/as-and-a-level-chemistry-9701">Other subject</a>
        <a href="https://example.com/elsewhere.pdf">External</a>
        <a href="download_file.php?files=https://pastpapers.papacambridge.com/directories/CAIE/test%20paper.pdf">Download</a>
        <a href="download_file.php?files=https://pastpapers.papacambridge.com/directories/CAIE/Work%20%26%20Power.pdf">Encoded</a>
        <a href="download_file.php?files=https://pastpapers.papacambridge.com/directories/CAIE/Energy &amp; Power.pdf">Raw ampersand</a>'''
        folders, files = parse_page(html, SOURCE)
        self.assertEqual(list(folders), [SOURCE + "-2026-march"])
        self.assertEqual(list(files.values()), ["test paper.pdf", "Work & Power.pdf", "Energy & Power.pdf"])

    def test_pair_combined_legacy_schemes_and_extended_time_variant(self):
        def doc(name):
            return document("https://pastpapers.papacambridge.com/directories/" + name,
                            name, SOURCE + "-2003-jun", "2003 June", ["2003 June"])
        tests, _ = build_tests([doc("9702_s03_qp_2.pdf"), doc("9702_s03_ms.pdf")])
        self.assertEqual(tests[0]["attachments"][0]["filename"], "9702_s03_ms.pdf")
        extended = doc("9702_w09_qp_et_33.pdf")
        self.assertEqual((extended["variant"], extended["component"]), ("33", "3"))

    def test_topical_titles_and_absent_schemes_are_preserved(self):
        name = "Physics 9702 Paper 2 - Kinematics.pdf"
        topical = document("https://pastpapers.papacambridge.com/directories/" + name,
                           name, SOURCE + "-topical-past-papers", "Topical", ["Topical"])
        tests, _ = build_tests([topical])
        self.assertEqual(tests[0]["collection"], "topical")
        self.assertEqual(tests[0]["component"], "2")
        self.assertEqual(tests[0]["attachments"], [])

    def test_topical_answers_are_paired_and_kept_out_of_practice_counts(self):
        folder = SOURCE + "-topical-past-papers-p4-topical-past-papers"
        docs = [document("https://pastpapers.papacambridge.com/directories/" + name,
                         name, folder, "P4 Topical Past Papers", ["Topical", "P4 Topical Past Papers"])
                for name in ("circular motion_qp.pdf", "circular motion_ms.pdf")]
        tests, resources = build_tests(docs)
        self.assertEqual((len(tests), len(resources)), (1, 1))
        self.assertEqual(tests[0]["component"], "4")
        self.assertEqual(tests[0]["attachments"][0]["filename"], "circular motion_ms.pdf")


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "progress.sqlite3"
        self.store = Store(self.path)
        self.tests, self.groups = {"one", "two"}, {"year:2026"}

    def save(self, updates):
        return self.store.save(updates, self.tests, self.groups)

    def test_notes_and_status_persist_separately_across_restarts(self):
        self.save([{"kind": "test", "id": "one", "status": "solved", "notes": "Review vectors"}])
        self.save([{"kind": "test", "id": "one", "status": "know_how"}])
        self.save([{"kind": "test", "id": "one", "notes": "Now confident"}])
        mark = Store(self.path).all()["test"]["one"]
        self.assertEqual((mark["status"], mark["notes"]), ("know_how", "Now confident"))

    def test_group_mark_does_not_change_paper_marks(self):
        self.save([{"kind": "group", "id": "year:2026", "status": "solved"}])
        result = self.store.all()
        self.assertEqual(result["test"], {})
        self.assertEqual(result["group"]["year:2026"]["status"], "solved")

    def test_invalid_bulk_update_is_atomic(self):
        with self.assertRaises(ValueError):
            self.save([{"kind": "test", "id": "one", "status": "solved"},
                       {"kind": "test", "id": "unknown", "status": "solved"}])
        self.assertEqual(self.store.all()["test"], {})

    def test_concurrent_note_and_status_updates_do_not_lose_fields(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(self.save, [{"kind": "test", "id": "one", "notes": "Keep this"}]),
                       pool.submit(self.save, [{"kind": "test", "id": "one", "status": "solved"}])]
            for result in results:
                result.result()
        mark = self.store.all()["test"]["one"]
        self.assertEqual((mark["status"], mark["notes"]), ("solved", "Keep this"))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.doc = document("https://pastpapers.papacambridge.com/directories/9702_s26_qp_11.pdf",
                           "9702_s26_qp_11.pdf", SOURCE + "-2026-may-june", "2026 May June", ["2026 May June"])
        atomic_json(cls.root / "catalogue.json", {"source": SOURCE, "documents": [cls.doc]})
        cls.pdf = b"%PDF-1.4\n" + b"x" * 200 + b"\n%%EOF\n"
        path = cls.root / cls.doc["local_path"]
        path.parent.mkdir(parents=True)
        path.write_bytes(cls.pdf)
        cls.server = StudyServer(("127.0.0.1", 0), cls.root, cls.root / "catalogue.json")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        status, response_headers, content = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, response_headers, content

    def post(self, path, body):
        return self.request(path, "POST", json.dumps(body), {"Content-Type": "application/json"})

    def test_catalogue_and_pdf_byte_ranges(self):
        code, _, body = self.request("/api/library")
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["files"][self.doc["id"]]["available"])
        code, headers, body = self.request("/files/" + self.doc["id"], headers={"Range": "bytes=0-7"})
        self.assertEqual((code, body), (206, b"%PDF-1.4"))
        self.assertTrue(headers["Content-Range"].startswith("bytes 0-7/"))
        code, _, body = self.request("/files/" + self.doc["id"], "HEAD")
        self.assertEqual((code, body), (200, b""))

    def test_export_restore_preserves_notes(self):
        update = {"kind": "test", "id": self.doc["id"], "status": "solved", "notes": "✓ Done"}
        self.assertEqual(self.post("/api/marks", {"updates": [update]})[0], 200)
        _, _, backup = self.request("/api/export")
        self.post("/api/marks", {"updates": [{**update, "status": "to_process", "notes": "Changed"}]})
        code, _, restored = self.post("/api/import", json.loads(backup))
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(restored)["test"][self.doc["id"]]["notes"], "✓ Done")

    def test_bad_input_unknown_targets_cross_origin_and_traversal(self):
        for data in [[], {"updates": "wrong"}, {"updates": [{"kind": "test", "id": "unknown", "status": "solved"}]},
                     {"updates": [{"kind": "test", "id": self.doc["id"], "status": []}]}]:
            self.assertEqual(self.post("/api/marks", data)[0], 400)
        self.assertEqual(self.request("/api/marks", "POST", "{}", {"Origin": "https://example.com", "Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.request("/files/../../README.md")[0], 404)
        self.assertEqual(self.request("/files/" + self.doc["id"], headers={"Range": "bytes=99999-"})[0], 416)

    def test_download_resume_skips_valid_pdf_without_network(self):
        result, size = download(self.doc, self.root)
        self.assertEqual((result, size), ("cached", len(self.pdf)))

    def test_truncated_pdf_is_not_accepted_as_a_completed_download(self):
        path = self.root / "truncated.pdf"
        path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)
        self.assertFalse(valid_pdf(path))


if __name__ == "__main__":
    unittest.main()
