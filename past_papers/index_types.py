"""Refresh task-type assignments without re-extracting PDFs or touching progress."""
import argparse
from pathlib import Path
import sqlite3

from .catalogue import BASE
from .methods import build_type_index


def index_types(path):
    path = Path(path)
    if not path.exists():
        raise ValueError("Run python3 -m past_papers.index_tasks first")
    temporary = path.with_name("task-types.build.sqlite3")
    temporary.unlink(missing_ok=True)
    try:
        with sqlite3.connect(path) as source, sqlite3.connect(temporary) as target:
            source.backup(target)
            count, assignments = build_type_index(target)
            target.commit()
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"classified_questions": count, "assignments": assignments}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=BASE / "data")
    args = parser.parse_args()
    print(index_types(args.data_dir / "tasks.sqlite3"))


if __name__ == "__main__":
    main()
