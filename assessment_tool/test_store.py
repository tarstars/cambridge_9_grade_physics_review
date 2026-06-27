import os
import tempfile
import unittest

import store

QUESTIONS = {
    "topics": [
        {
            "id": "forces",
            "name": "Forces",
            "subtopics": [
                {"id": "motion", "name": "Motion", "questions": [
                    {"id": "8Pf.01", "text": "speed?"},
                    {"id": "8Pf.02", "text": "graphs?"},
                ]},
            ],
        },
        {
            "id": "electricity",
            "name": "Electricity",
            "subtopics": [
                {"id": "circuits", "name": "Circuits", "questions": [
                    {"id": "7Pe.01", "text": "current?"},
                ]},
            ],
        },
    ]
}


class ValidQuestionIdsTests(unittest.TestCase):
    def test_collects_every_question_id_across_topics(self):
        self.assertEqual(
            store.valid_question_ids(QUESTIONS),
            {"8Pf.01", "8Pf.02", "7Pe.01"},
        )


class ValidateResultsTests(unittest.TestCase):
    def _results(self, answers):
        return {"sessions": [{"id": "2026-06-27", "label": "Week 0", "answers": answers}]}

    def test_accepts_marks_0_1_2_and_null_comment(self):
        data = self._results({
            "8Pf.01": {"mark": 0, "comment": ""},
            "8Pf.02": {"mark": 2, "comment": "solid"},
            "7Pe.01": {"mark": None, "comment": "not asked yet"},
        })
        self.assertEqual(store.validate_results(data, QUESTIONS), [])

    def test_rejects_mark_out_of_range(self):
        data = self._results({"8Pf.01": {"mark": 3, "comment": ""}})
        errors = store.validate_results(data, QUESTIONS)
        self.assertEqual(len(errors), 1)
        self.assertIn("8Pf.01", errors[0])

    def test_rejects_unknown_question_id(self):
        data = self._results({"9Zz.99": {"mark": 1, "comment": ""}})
        errors = store.validate_results(data, QUESTIONS)
        self.assertEqual(len(errors), 1)
        self.assertIn("9Zz.99", errors[0])


class SaveLoadTests(unittest.TestCase):
    def test_save_then_load_roundtrip(self):
        data = {"sessions": [{"id": "2026-06-27", "label": "Week 0",
                              "answers": {"8Pf.01": {"mark": 1, "comment": "ok"}}}]}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "results.json")
            store.save_results(path, data)
            self.assertEqual(store.load_results(path), data)

    def test_load_missing_file_returns_empty_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "does-not-exist.json")
            self.assertEqual(store.load_results(path), {"sessions": []})


class RollupTests(unittest.TestCase):
    def test_sums_marks_per_topic_for_a_session(self):
        data = {"sessions": [{"id": "s1", "label": "Week 0", "answers": {
            "8Pf.01": {"mark": 2, "comment": ""},
            "8Pf.02": {"mark": 1, "comment": ""},
            "7Pe.01": {"mark": None, "comment": ""},
        }}]}
        result = store.rollup(data, QUESTIONS, "s1")
        self.assertEqual(result["forces"], {"sum": 3, "max": 4, "answered": 2, "count": 2})
        self.assertEqual(result["electricity"], {"sum": 0, "max": 2, "answered": 0, "count": 1})


if __name__ == "__main__":
    unittest.main()
