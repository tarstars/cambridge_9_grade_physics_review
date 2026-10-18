"""Portable study progress: python3 -m past_papers.progress export|restore.

The tracked JSON snapshot is portable; SQLite, PDFs and caches stay machine-local.
Exports have stable ordering and preserve the original mark timestamps.
"""
import argparse
import json
from pathlib import Path

from .catalogue import BASE, atomic_json, build_tests, load_catalogue
from .store import Store
from .task_library import TaskLibrary

DEFAULT_SNAPSHOT = BASE / "progress.json"


def export_progress(data_dir=BASE / "data", destination=DEFAULT_SNAPSHOT):
    state = Store(Path(data_dir) / "progress.sqlite3").all()
    # Do not add an export timestamp: an unchanged export should have no diff.
    snapshot = {"version": 2, "marks": json.loads(json.dumps(state, sort_keys=True))}
    atomic_json(destination, snapshot)
    return snapshot


def restore_progress(source=DEFAULT_SNAPSHOT, data_dir=BASE / "data", catalogue_path=BASE / "catalogue.json",
                     only_if_empty=False):
    source, data_dir = Path(source), Path(data_dir)
    if source.stat().st_size > 20_000_000:
        raise ValueError("Progress backup must be under 20 MB")
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or snapshot.get("version") not in (1, 2) or not isinstance(snapshot.get("marks"), dict):
        raise ValueError("Unsupported progress backup")
    store = Store(data_dir / "progress.sqlite3")
    if only_if_empty and any(store.all().values()):
        return False
    updates = []
    marks = snapshot["marks"]
    for kind in ("test", "task", "group"):
        values = marks.get(kind, {})
        if not isinstance(values, dict):
            raise ValueError("Invalid progress backup")
        for key, value in values.items():
            if not isinstance(value, dict):
                raise ValueError("Invalid mark in backup")
            update = {"kind": kind, "id": key, "status": value.get("status"), "notes": value.get("notes", "")}
            if "updated_at" in value:
                update["updated_at"] = value["updated_at"]
            updates.append(update)
    topics, types = marks.get("topics", {}), marks.get("types", {})
    tests, _ = build_tests(load_catalogue(catalogue_path)["documents"])
    valid_tests = {test["id"] for test in tests}
    valid_groups = {group for test in tests for group in test["groups"]}
    valid_tasks, task_groups = TaskLibrary(data_dir).targets()
    if marks.get("task") and not valid_tasks:
        raise ValueError("Question index is missing. Run python3 -m past_papers.setup first.")
    if updates or topics or types:
        store.save(updates, valid_tests, valid_groups | task_groups, valid_tasks, topics, types,
                   preserve_timestamps=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "restore"))
    parser.add_argument("--data-dir", type=Path, default=BASE / "data")
    parser.add_argument("--catalogue", type=Path, default=BASE / "catalogue.json")
    parser.add_argument("--file", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--if-empty", action="store_true", help="Restore only if this machine has no study progress")
    args = parser.parse_args()
    try:
        if args.action == "export":
            snapshot = export_progress(args.data_dir, args.file)
            counts = {kind: len(values) for kind, values in snapshot["marks"].items()}
            print(f"Progress snapshot saved to {args.file}: {counts}")
        else:
            restored = restore_progress(args.file, args.data_dir, args.catalogue, args.if_empty)
            print("Progress restored; existing records absent from the snapshot were kept." if restored
                  else "Local progress already exists; nothing was replaced.")
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
