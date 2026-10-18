"""Prepare a fresh clone: download source PDFs, index questions, restore progress."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import shutil

from .catalogue import BASE, atomic_json, load_catalogue
from .index_tasks import build_index
from .progress import DEFAULT_SNAPSHOT, restore_progress
from .questions import ocr_executable
from .sync import download


def prepare(data_dir=BASE / "data", catalogue_path=BASE / "catalogue.json", snapshot=DEFAULT_SNAPSHOT,
            workers=4, skip_download=False, reindex=False, use_ocr=True):
    data_dir, catalogue_path, snapshot = Path(data_dir), Path(catalogue_path), Path(snapshot)
    for executable in ("pdftotext", "pdftoppm"):
        if not shutil.which(executable):
            raise ValueError(f"{executable} is missing. Install Poppler; see the fresh-clone instructions in README.md.")
    if use_ocr and not ocr_executable(data_dir):
        raise ValueError("Tesseract is missing. Install tesseract-ocr and English language data, or explicitly use --no-ocr.")
    documents = load_catalogue(catalogue_path)["documents"]
    if not documents:
        raise ValueError("The saved source catalogue is empty. Run python3 -m past_papers.sync first.")
    data_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    if not skip_download:
        counts = {"cached": 0, "downloaded": 0, "failed": 0}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            jobs = {executor.submit(download, doc, data_dir): doc for doc in documents}
            for finished, job in enumerate(as_completed(jobs), 1):
                doc = jobs[job]
                status, value = job.result()
                counts[status] += 1
                if status == "failed":
                    failures.append({"id": doc["id"], "url": doc["url"], "error": value})
                    print(f"Source unavailable: {doc['filename']}: {value}", flush=True)
                if finished % 25 == 0 or finished == len(jobs):
                    print(f"{finished}/{len(jobs)} PDFs: {counts}", flush=True)
        atomic_json(data_dir / "download-report.json", {"counts": counts, "errors": failures})
    if reindex or not (data_dir / "tasks.sqlite3").exists():
        print("Building the question and task-type index…", flush=True)
        build_index(data_dir, catalogue_path, workers, use_ocr)
    if snapshot.exists():
        restored = restore_progress(snapshot, data_dir, catalogue_path, only_if_empty=True)
        print("Repository progress restored." if restored else "Existing local progress preserved.", flush=True)
    if failures:
        print(f"{len(failures)} source files remain unavailable; coverage details are in the app.", flush=True)
    print("Ready. Run python3 -m past_papers.server", flush=True)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=BASE / "data")
    parser.add_argument("--catalogue", type=Path, default=BASE / "catalogue.json")
    parser.add_argument("--progress-file", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--skip-download", action="store_true", help="Use PDFs already copied to the data directory")
    parser.add_argument("--reindex", action="store_true", help="Rebuild even if a question index already exists")
    parser.add_argument("--no-ocr", action="store_true", help="Explicitly omit OCR for scanned pages")
    args = parser.parse_args()
    try:
        prepare(args.data_dir, args.catalogue, args.progress_file, args.workers,
                args.skip_download, args.reindex, not args.no_ocr)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
