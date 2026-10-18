"""Question extraction, migration, topic corrections, filtered bulk marks, and previews."""
import http.client
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

from .catalogue import SOURCE, document, atomic_json
from .index_tasks import SCHEMA
from .questions import extract_questions
from .server import StudyServer
from .store import Store
from .task_library import TaskLibrary
from .topics import classify
from .task_previews import answer_page


def line(text, x, y):
    words, position = [], x
    for token in text.split():
        words.append([token, position, y, position + len(token) * 5, y + 11])
        position += len(token) * 5 + 5
    return {"text": text, "words": words, "x": x, "y": y, "bottom": y + 11}


def fixture_document():
    return document("https://pastpapers.papacambridge.com/directories/9702_s26_qp_22.pdf",
                    "9702_s26_qp_22.pdf", SOURCE + "-2026-may-june", "2026 May June", ["2026 May June"])


def make_pdf():
    content = b"BT /F1 12 Tf 50 700 Td (1 Calculate the kinetic energy of a moving ball.) Tj ET\n"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream"]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode() + value + b"\nendobj\n"
    start = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    result += f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    return result


def seed_index(root):
    doc = fixture_document()
    db = sqlite3.connect(root / "tasks.sqlite3")
    db.executescript(SCHEMA)
    db.execute("INSERT INTO metadata VALUES('indexed_at','2026-10-18T00:00:00+00:00')")
    db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
               (doc["id"], doc["filename"], "yearly", 2026, "s", "2", json.dumps(doc), 3, "indexed", ""))
    for number, topic in [(1, "energy"), (2, "energy"), (3, "circuits")]:
        key = f"{doc['id']}-q{number}"
        db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (key, doc["id"], number, 1, 1, 1, "Calculate kinetic energy of the ball.",
                    "Calculate kinetic energy of the ball.",
                    json.dumps([{"page": 1, "top": 70, "bottom": 220, "width": 612, "height": 792}]),
                    '["a","b"]', json.dumps([topic]), "suggested", '{}'))
    db.commit()
    db.close()
    return doc


class ExtractionTests(unittest.TestCase):
    def test_numbered_question_keeps_subparts_and_excludes_the_next_question(self):
        pages = [{"width": 595, "height": 842, "lines": [line("Cover page", 50, 100)]},
                 {"width": 595, "height": 842, "lines": [line("1", 50, 70),
                  line("(a) Calculate the kinetic energy of the ball.", 75, 70),
                  line("(b) Explain the energy transfer in this collision.", 75, 120),
                  line("2", 50, 300), line("A resistor is connected to an electric circuit.", 75, 300)]}]
        tasks = extract_questions(pages, fixture_document())
        self.assertEqual([q["number"] for q in tasks], [1, 2])
        self.assertEqual(tasks[0]["subparts"], ["a", "b"])
        self.assertIn("collision", tasks[0]["text"])
        self.assertNotIn("resistor", tasks[0]["text"])
        self.assertLess(tasks[0]["regions"][0]["bottom"], tasks[1]["regions"][0]["top"])

    def test_compilation_citations_define_tasks_and_repeated_numbers_keep_unique_ids(self):
        doc = {**fixture_document(), "collection": "topical"}
        pages = [{"width": 612, "height": 792, "lines": [
            line("1. Nov/2021/Paper_21/No.4", 54, 49), line("A longitudinal wave transfers energy.", 77, 75),
            line("1. Nov/2020/Paper_22/No.4", 54, 330), line("A sound wave travels through the air.", 77, 355)]}]
        tasks = extract_questions(pages, doc)
        self.assertEqual(len(tasks), 2)
        self.assertNotEqual(tasks[0]["id"], tasks[1]["id"])

    def test_topic_suggestions_use_each_questions_content(self):
        self.assertEqual(classify("A radioactive isotope has a half-life of two hours.")["topics"][0], "nuclear")
        self.assertEqual(classify("Find the capacitance and energy stored in this capacitor.")["topics"][0], "capacitance")
        self.assertEqual(classify("A question with no identifiable physics information.")["topics"], ["unclassified"])

    def test_compilation_numbers_above_one_thousand_are_preserved(self):
        doc = {**fixture_document(), "collection": "topical"}
        pages = [{"width": 612, "height": 792, "lines": [
            line("1008. 9702_m20_qp_12 Q: 30", 65, 70), line("Two electric charges exert a force on each other.", 80, 95),
            line("1009. 9702_s20_qp_11 Q: 31", 65, 320), line("Find the electric field strength at this point.", 80, 345)]}]
        self.assertEqual([q["number"] for q in extract_questions(pages, doc)], [1008, 1009])

    def test_explicit_compilation_labels_take_priority_over_original_paper_numbering(self):
        doc = {**fixture_document(), "collection": "topical"}
        pages = [{"width": 612, "height": 792, "lines": [
            line("Qi.", 100, 75), line("3 (a) A copper wire is stretched by a tensile force.", 110, 105),
            line("Q2.", 100, 320), line("7 (a) Calculate the strain in this stretched wire.", 110, 350)]}]
        self.assertEqual([q["number"] for q in extract_questions(pages, doc)], [1, 2])

    def test_bundled_paper_variants_keep_separate_questions_and_stop_at_the_cover(self):
        content = [line(str(n), 50, 70 + n * 120) for n in (1, 2, 3)]
        content += [line("Calculate the kinetic energy of this moving ball.", 75, 70 + n * 120) for n in (1, 2, 3)]
        pages = [{"width": 595, "height": 842, "lines": []},
                 {"width": 595, "height": 842, "lines": content},
                 {"width": 595, "height": 842, "lines": [line("READ THESE INSTRUCTIONS FIRST", 50, 100)]},
                 {"width": 595, "height": 842, "lines": content}]
        tasks = extract_questions(pages, fixture_document())
        self.assertEqual([q["number"] for q in tasks], [1, 2, 3, 1, 2, 3])
        self.assertEqual(tasks[2]["end_page"], 2)
        self.assertNotEqual(tasks[0]["id"], tasks[3]["id"])

    def test_recovered_scan_marker_keeps_a_question_when_page_ocr_drops_its_text(self):
        pages = [{"width": 595, "height": 842, "lines": []},
                 {"width": 595, "height": 842, "lines": [], "ocr": True,
                  "question_headers": [{"number": 1, "page": 2, "x": 50, "y": 100}]}]
        tasks = extract_questions(pages, fixture_document())
        self.assertEqual(len(tasks), 1)
        self.assertTrue(tasks[0]["needs_text_ocr"])
        self.assertEqual(tasks[0]["regions"][0]["page"], 2)

    def test_multiple_choice_distractors_do_not_determine_the_topic(self):
        text = "1\nA projectile is thrown with an initial velocity.\nA\nRadioactive decay\nB\nNuclear fission\nC\nPhotoelectric effect\nD\nQuantum physics"
        self.assertEqual(classify(text, "1")["topics"][0], "kinematics")

    def test_last_mcq_does_not_absorb_later_damaged_pages(self):
        doc = {**fixture_document(), "component": "1"}
        pages = [{"width": 595, "height": 842, "lines": []},
                 {"width": 595, "height": 842, "lines": [line("1", 50, 70),
                  line("Which diagram shows the electric field?", 75, 70)]},
                 {"width": 595, "height": 842, "lines": [line("Unrelated diagram without readable question text", 150, 100)]}]
        tasks = extract_questions(pages, doc)
        self.assertEqual(tasks[0]["end_page"], 2)
        self.assertNotIn("Unrelated", tasks[0]["text"])

    def test_mcq_answer_page_uses_question_column_not_mark_values(self):
        pages = [{"width": 595, "height": 842, "lines": []},
                 {"width": 595, "height": 842, "lines": [line("1", 78, 100),line("B", 295, 100),line("1", 534, 100)]},
                 {"width": 595, "height": 842, "lines": [line("40", 78, 100),line("D", 295, 100),line("1", 534, 100)]}]
        with patch("past_papers.task_previews.pdf_pages", return_value=pages):
            self.assertEqual(answer_page("unused.pdf", 1, None, True), 2)
            self.assertEqual(answer_page("unused.pdf", 40, None, True), 3)


class MigrationTests(unittest.TestCase):
    def test_existing_paper_progress_survives_schema_migration_and_task_marks_are_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "progress.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE marks(kind TEXT CHECK(kind IN ('test','group')),id TEXT,status TEXT,notes TEXT,updated_at TEXT,PRIMARY KEY(kind,id))")
                db.execute("INSERT INTO marks VALUES('test','paper','solved','Keep my notes','yesterday')")
            store = Store(path)
            store.save([{"kind": "task", "id": "paper-q1", "status": "to_process"}], {"paper"}, set(), {"paper-q1"})
            state = Store(path).all()
            self.assertEqual(state["test"]["paper"]["notes"], "Keep my notes")
            self.assertEqual(state["test"]["paper"]["status"], "solved")
            self.assertEqual(state["task"]["paper-q1"]["status"], "to_process")

    def test_invalid_topic_correction_rolls_back_status_and_notes(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(Path(temporary) / "progress.sqlite3")
            with self.assertRaises(ValueError):
                store.save([{"kind": "task", "id": "q1", "status": "solved", "notes": "Changed"}],
                           set(), set(), {"q1"}, {"q1": ["not-a-topic"]})
            self.assertEqual(store.all()["task"], {})


class TaskHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.doc = seed_index(self.root)
        self.keys = [f"{self.doc['id']}-q{n}" for n in (1, 2, 3)]
        path = self.root / self.doc["local_path"]
        path.parent.mkdir(parents=True)
        path.write_bytes(make_pdf())
        atomic_json(self.root / "catalogue.json", {"source": SOURCE, "documents": [self.doc]})
        self.server = StudyServer(("127.0.0.1", 0), self.root, self.root / "catalogue.json")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, path, payload=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=20)
        connection.request("POST" if payload is not None else "GET", path,
                           body=json.dumps(payload) if payload is not None else None,
                           headers={"Content-Type": "application/json"} if payload is not None else {})
        response = connection.getresponse()
        status, body = response.status, response.read()
        connection.close()
        return status, body

    def get_json(self, path):
        code, body = self.request(path)
        self.assertEqual(code, 200)
        return json.loads(body)

    def test_topic_filter_and_pagination_count_individual_questions(self):
        result = self.get_json("/api/tasks?topic=energy&page_size=1")
        self.assertEqual((result["total"], len(result["tasks"])), (2, 1))
        self.assertEqual(result["groups"][0]["total"], 2)
        detail = self.get_json("/api/tasks/" + result["tasks"][0]["id"])
        self.assertEqual(detail["subparts"], ["a", "b"])
        self.assertTrue(detail["files"][0]["url"].endswith("#page=1"))

    def test_filtered_bulk_update_includes_questions_on_other_pages_only_in_that_group(self):
        code, _ = self.request("/api/task-bulk", {"filters": {"topic": "energy", "page_size": "1"},
                              "group_id": "tasks:topic:energy", "status": "solved"})
        self.assertEqual(code, 200)
        state = self.server.store.all()
        self.assertEqual(set(state["task"]), set(self.keys[:2]))
        self.assertEqual(state["test"], {})
        self.assertEqual(state["group"], {})

    def test_correction_changes_topic_filter_and_survives_rebuilding_the_index(self):
        code, _ = self.request("/api/marks", {"updates": [], "topics": {self.keys[0]: ["kinematics"]}})
        self.assertEqual(code, 200)
        self.assertEqual(self.get_json("/api/tasks?topic=kinematics")["total"], 1)
        replacement = self.root / "replacement"
        replacement.mkdir()
        seed_index(replacement)
        (replacement / "tasks.sqlite3").replace(self.root / "tasks.sqlite3")
        self.assertEqual(self.get_json("/api/tasks?topic=kinematics")["tasks"][0]["topic_source"], "confirmed")

    def test_question_export_restore_and_old_paper_backup(self):
        self.request("/api/marks", {"updates": [{"kind": "task", "id": self.keys[0], "status": "solved", "notes": "Remember the diagram"}],
                                    "topics": {self.keys[0]: ["kinematics"]}})
        backup = self.get_json("/api/export")
        self.assertEqual(backup["version"], 2)
        self.request("/api/marks", {"updates": [{"kind": "task", "id": self.keys[0], "status": "unmarked"}],
                                    "topics": {self.keys[0]: ["waves"]}})
        self.assertEqual(self.request("/api/import", backup)[0], 200)
        state = self.server.store.all()
        self.assertEqual(state["task"][self.keys[0]]["status"], "solved")
        self.assertEqual(state["topics"][self.keys[0]], ["kinematics"])
        old = {"version": 1, "marks": {"test": {self.doc["id"]: {"status": "solved", "notes": "Old paper notes"}}, "group": {}}}
        self.assertEqual(self.request("/api/import", old)[0], 200)
        self.assertEqual(self.server.store.all()["test"][self.doc["id"]]["notes"], "Old paper notes")

    def test_question_image_is_cropped_and_unknown_question_is_rejected(self):
        code, body = self.request(f"/task-images/{self.keys[0]}/0.png")
        self.assertEqual(code, 200)
        self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", body[16:24])
        self.assertEqual(width, 1000)
        self.assertLess(height, 300)
        self.assertEqual(self.request(f"/task-images/{self.keys[0]}/99.png")[0], 400)
        self.assertEqual(self.request("/api/tasks/" + "f" * 20 + "-q1")[0], 404)


if __name__ == "__main__":
    unittest.main()
