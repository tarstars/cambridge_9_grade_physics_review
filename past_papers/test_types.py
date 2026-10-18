"""Specific pattern membership and learner progress must remain independent."""
import json
import sqlite3
import shutil
import struct
import unittest

from .methods import classify_types, build_type_index
from . import test_tasks as fixtures


def keys(text, component="1"):
    return {key for key, _ in classify_types(text, component)}


class PatternTests(unittest.TestCase):
    def test_clipboard_question_is_grouped_by_base_quantity_not_base_unit(self):
        self.assertEqual(keys("1\nWhat is an SI base quantity?\nA\nampere\nB\ncharge\nC\ncoulomb\nD\ncurrent"),
                         {"si-base-quantity"})

    def test_base_units_and_derived_units_are_separate_methods(self):
        self.assertEqual(keys("Which is an SI base unit?"), {"si-base-unit"})
        self.assertEqual(keys("What are the base units for intensity?"), {"derive-base-units"})
        self.assertIn("derive-base-units", keys("What is the unit of constant b, expressed in SI base units?"))

    def test_answer_options_do_not_introduce_unrelated_methods(self):
        text = "1\nWhat is an SI base quantity?\nA\nphotoelectric effect\nB\nhalf-life\nC\npotential divider\nD\ncurrent"
        self.assertEqual(keys(text), {"si-base-quantity"})

    def test_generic_topic_is_not_misrepresented_as_a_specific_method(self):
        self.assertEqual(keys("This question is about electricity."), set())

    def test_negligible_internal_resistance_is_not_a_task_about_internal_resistance(self):
        self.assertNotIn("internal-resistance", keys("A potential divider has a battery of negligible internal resistance."))
        self.assertIn("potential-divider", keys("A potential divider has a battery of negligible internal resistance."))

    def test_uncertainty_and_potential_divider_patterns(self):
        self.assertIn("uncertainty-propagation", keys("The uncertainty in the cube side is 1%. Find the percentage uncertainty in the calculated volume."))
        self.assertIn("potential-divider", keys("Which potential divider circuit has the largest output voltage?"))

    def test_the_required_operation_takes_priority_over_the_numerical_context(self):
        text = "The specific heat capacity is c = b T cubed. What is the unit of constant b expressed in SI base units?"
        self.assertEqual(keys(text), {"derive-base-units"})
        text = "A resistor has a measured current and potential difference. Find the percentage uncertainty in the calculated resistance."
        self.assertEqual(keys(text), {"uncertainty-propagation"})
        text = "A battery has internal resistance. Which statement describes the electromotive force (e.m.f.) of the battery?"
        self.assertEqual(keys(text), {"emf-definition"})
        self.assertIn("internal-resistance", keys("A cell with non-negligible internal resistance supplies a resistor."))


class TypeHTTPTests(unittest.TestCase):
    tearDown = fixtures.TaskHTTPTests.tearDown
    request = fixtures.TaskHTTPTests.request
    get_json = fixtures.TaskHTTPTests.get_json

    def setUp(self):
        fixtures.TaskHTTPTests.setUp(self)
        with sqlite3.connect(self.root / "tasks.sqlite3") as db:
            db.execute("UPDATE tasks SET text='What is an SI base quantity?' WHERE id=?", (self.keys[0],))
            db.execute("UPDATE tasks SET text='Which SI base quantities are used?' WHERE id=?", (self.keys[1],))
            db.execute("UPDATE tasks SET text='This question is about electricity.' WHERE id=?", (self.keys[2],))
            build_type_index(db)

    def test_type_navigation_returns_similar_individual_questions_with_inline_crops(self):
        catalogue = self.get_json("/api/task-types")
        base = next(item for item in catalogue["types"] if item["id"] == "si-base-quantity")
        self.assertEqual(base["total"], 2)
        self.assertEqual((catalogue["assigned"], catalogue["unassigned"]), (2, 1))
        self.assertTrue(base["sample"]["image"].startswith("/task-images/"))
        tasks = self.get_json("/api/tasks?type=si-base-quantity&group=type&page_size=1")
        self.assertEqual((tasks["total"], len(tasks["tasks"])), (2, 1))
        self.assertEqual(tasks["groups"][0]["id"], "tasks:type:si-base-quantity")
        self.assertEqual(tasks["tasks"][0]["images"][0]["page"], 1)
        self.assertEqual(self.get_json("/api/tasks?type=unassigned")["total"], 1)

    def test_type_progress_does_not_mark_its_questions(self):
        response = self.request("/api/marks", {"updates": [{"kind": "group", "id": "tasks:type:si-base-quantity",
            "status": "know_how", "notes": "Separate quantities from their units"}]})
        self.assertEqual(response[0], 200)
        base = next(item for item in self.get_json("/api/task-types")["types"] if item["id"] == "si-base-quantity")
        self.assertEqual(base["status"], "know_how")
        self.assertEqual(self.server.store.all()["task"], {})

    def test_type_corrections_survive_index_refresh_and_backup_restore(self):
        update = {"updates": [], "types": {self.keys[2]: ["potential-divider"]}}
        self.assertEqual(self.request("/api/marks", update)[0], 200)
        with sqlite3.connect(self.root / "tasks.sqlite3") as db:
            build_type_index(db)
        self.assertEqual(self.get_json("/api/tasks?type=potential-divider")["total"], 1)
        backup = self.get_json("/api/export")
        self.request("/api/marks", {"updates": [], "types": {self.keys[2]: []}})
        self.assertEqual(self.get_json("/api/tasks?type=potential-divider")["total"], 0)
        self.assertEqual(self.request("/api/import", backup)[0], 200)
        task = self.get_json("/api/tasks/" + self.keys[2])
        self.assertEqual(task["task_types"], ["potential-divider"])
        self.assertEqual(task["type_source"], "confirmed")

    def test_invalid_type_correction_cannot_partially_save_a_mark(self):
        code, body = self.request("/api/marks", {"updates": [{"kind": "task", "id": self.keys[0], "status": "solved"}],
            "types": {self.keys[0]: ["not-a-type"]}})
        self.assertEqual(code, 400)
        self.assertEqual(self.server.store.all()["task"], {})

    def test_structured_filter_matches_the_question_format(self):
        self.assertEqual(self.get_json("/api/tasks?type=si-base-quantity&structured=1")["total"], 2)
        self.assertEqual(self.get_json("/api/tasks?type=si-base-quantity&paper=1")["total"], 0)

    @unittest.skipUnless(shutil.which('convert') or shutil.which('magick'), 'Optional compact crop tool unavailable')
    def test_compact_reading_crop_keeps_the_full_original_available(self):
        _, original = self.request(f"/task-images/{self.keys[0]}/0.png")
        code, compact = self.request(f"/task-images/{self.keys[0]}/0.png?compact=1")
        self.assertEqual(code, 200)
        original_width, original_height = struct.unpack('>II', original[16:24])
        width, height = struct.unpack('>II', compact[16:24])
        self.assertLess(width, original_width)
        self.assertEqual(height, original_height)

    @unittest.skipUnless(shutil.which('convert') or shutil.which('magick'), 'Optional compact crop tool unavailable')
    def test_multiple_choice_crop_omits_unused_space_below_the_question(self):
        with sqlite3.connect(self.root / 'tasks.sqlite3') as db:
            db.execute("UPDATE documents SET component='1'")
        _, original = self.request(f"/task-images/{self.keys[0]}/0.png")
        code, compact = self.request(f"/task-images/{self.keys[0]}/0.png?compact=1")
        self.assertEqual(code, 200)
        _, original_height = struct.unpack('>II', original[16:24])
        width, height = struct.unpack('>II', compact[16:24])
        self.assertGreater(width, 100)
        self.assertLess(height, original_height)


if __name__ == "__main__":
    unittest.main()
