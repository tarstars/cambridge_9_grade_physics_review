"""A fresh checkout must recover marks, notes and corrections without local files."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .catalogue import SOURCE, atomic_json
from .progress import export_progress, restore_progress
from .setup import prepare
from .store import Store
from .test_tasks import seed_index


class PortableProgressTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original = self.root / 'original'
        self.clone = self.root / 'clone'
        self.original.mkdir(); self.clone.mkdir()
        self.doc = seed_index(self.original)
        seed_index(self.clone)
        self.catalogue = self.root / 'catalogue.json'
        atomic_json(self.catalogue, {'source': SOURCE, 'documents': [self.doc]})
        self.key = self.doc['id'] + '-q1'
        self.snapshot = self.root / 'progress.json'
        self.store = Store(self.original / 'progress.sqlite3')
        self.store.save([
            {'kind': 'task', 'id': self.key, 'status': 'solved', 'notes': 'Keep this approach'},
            {'kind': 'group', 'id': 'tasks:type:si-base-quantity', 'status': 'know_how', 'notes': 'Quantity versus unit'},
        ], set(), {'tasks:type:si-base-quantity'}, {self.key},
            {self.key: ['units']}, {self.key: ['si-base-quantity']})

    def tearDown(self):
        self.temporary.cleanup()

    def test_fresh_clone_recovers_all_progress_and_original_timestamps(self):
        export_progress(self.original, self.snapshot)
        restore_progress(self.snapshot, self.clone, self.catalogue)
        self.assertEqual(Store(self.clone / 'progress.sqlite3').all(), self.store.all())

    def test_unchanged_export_has_no_git_diff(self):
        export_progress(self.original, self.snapshot)
        first = self.snapshot.read_bytes()
        export_progress(self.original, self.snapshot)
        self.assertEqual(first, self.snapshot.read_bytes())

    def test_setup_does_not_overwrite_progress_already_on_the_other_machine(self):
        export_progress(self.original, self.snapshot)
        store = Store(self.clone / 'progress.sqlite3')
        store.save([{'kind': 'task', 'id': self.key, 'status': 'to_process', 'notes': 'My local work'}], set(), set(), {self.key})
        with patch('past_papers.setup.shutil.which', return_value='/usr/bin/tool'), \
                patch('past_papers.setup.ocr_executable', return_value='/usr/bin/tesseract'), \
                patch('past_papers.setup.build_index') as build, contextlib.redirect_stdout(io.StringIO()):
            prepare(self.clone, self.catalogue, self.snapshot, skip_download=True)
        build.assert_not_called()
        self.assertEqual(store.all()['task'][self.key]['notes'], 'My local work')

    def test_unknown_saved_question_does_not_partially_restore_other_marks(self):
        snapshot = export_progress(self.original, self.snapshot)
        snapshot['marks']['task']['missing-q99'] = {'status': 'solved', 'notes': ''}
        atomic_json(self.snapshot, snapshot)
        with self.assertRaises(ValueError):
            restore_progress(self.snapshot, self.clone, self.catalogue)
        self.assertEqual(Store(self.clone / 'progress.sqlite3').all()['group'], {})

    def test_invalid_timestamp_does_not_partially_restore(self):
        snapshot = export_progress(self.original, self.snapshot)
        snapshot['marks']['task'][self.key]['updated_at'] = 'not-a-date'
        atomic_json(self.snapshot, snapshot)
        with self.assertRaises(ValueError):
            restore_progress(self.snapshot, self.clone, self.catalogue)
        self.assertEqual(Store(self.clone / 'progress.sqlite3').all()['task'], {})

    def test_setup_restores_progress_when_machine_has_no_marks(self):
        export_progress(self.original, self.snapshot)
        with patch('past_papers.setup.shutil.which', return_value='/usr/bin/tool'), \
                patch('past_papers.setup.ocr_executable', return_value='/usr/bin/tesseract'), \
                contextlib.redirect_stdout(io.StringIO()):
            prepare(self.clone, self.catalogue, self.snapshot, skip_download=True)
        self.assertEqual(Store(self.clone / 'progress.sqlite3').all(), self.store.all())


if __name__ == '__main__':
    unittest.main()
