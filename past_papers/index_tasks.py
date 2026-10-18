"""Build the numbered-question index: python3 -m past_papers.index_tasks."""
import argparse
import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

from .catalogue import BASE, build_tests, load_catalogue
from .questions import (pdf_pages, extract_questions, ocr_sparse_pages, ocr_executable,
                        recover_compilation_headers, recover_scanned_question_numbers, recover_question_text)
from .topics import classify
from .methods import build_type_index

INDEX_RULE_VERSION = 17

SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE documents (
    id TEXT PRIMARY KEY, filename TEXT NOT NULL, collection TEXT NOT NULL,
    year INTEGER, session TEXT, component TEXT, metadata TEXT NOT NULL,
    task_count INTEGER NOT NULL, state TEXT NOT NULL, note TEXT NOT NULL);
CREATE TABLE tasks (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
    number INTEGER NOT NULL, occurrence INTEGER NOT NULL,
    page INTEGER NOT NULL, end_page INTEGER NOT NULL, text TEXT NOT NULL,
    summary TEXT NOT NULL, regions TEXT NOT NULL, subparts TEXT NOT NULL,
    topics TEXT NOT NULL, confidence TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE INDEX task_document ON tasks(document_id,number,occurrence);
CREATE INDEX document_filters ON documents(collection,year,session,component);
CREATE TABLE task_type_suggestions (
    task_id TEXT NOT NULL, type_id TEXT NOT NULL, evidence TEXT NOT NULL,
    PRIMARY KEY(task_id,type_id));
CREATE INDEX suggestions_by_type ON task_type_suggestions(type_id,task_id);
"""


def summary(text):
    text = re.sub(r"^\d+\s*", "", text.strip())
    text = re.sub(r"\.{3,}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:260].rstrip() + ("…" if len(text) > 260 else "")


def process_document(doc, data_dir, use_ocr=True):
    path = data_dir / doc["local_path"]
    cache = data_dir / "task-cache" / (doc["id"] + ".json.gz")
    stamp = f"{INDEX_RULE_VERSION}:{path.stat().st_size}:{path.stat().st_mtime_ns}:{use_ocr}:{bool(ocr_executable(data_dir))}" if path.exists() else None
    if stamp and cache.exists():
        try:
            with gzip.open(cache, "rt", encoding="utf-8") as stream:
                saved = json.load(stream)
            if saved.pop("stamp") == stamp and saved.get("state") != "needs_review":
                return {**saved, "document": doc}
        except (OSError, ValueError, KeyError):
            pass
    result = extract_document(doc, data_dir, use_ocr)
    if stamp:
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_suffix(".tmp")
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=3) as stream:
            json.dump({"stamp": stamp, **{k: v for k, v in result.items() if k != "document"}}, stream)
        temporary.replace(cache)
    return result


def extract_document(doc, data_dir, use_ocr=True):
    path = data_dir / doc["local_path"]
    result = {"document": doc, "questions": [], "state": "indexed", "note": ""}
    if not path.exists():
        result.update(state="unavailable", note="Source PDF is unavailable")
        return result
    if "_et_" in doc["filename"]:
        result.update(state="reference", note="Erratum sheet; not a question paper")
        return result
    if doc["filename"] == "kinematics unit-2.pdf":
        result.update(state="reference", note="Teaching notes on equations of motion; not a numbered-question collection")
        return result
    if doc["filename"] == "Physics Topical Questions.pdf":
        result.update(state="needs_review", note="Mixed scanned compilation: question boundaries are unreliable. Use the individually indexed source papers; the full compilation remains in Full papers.")
        return result
    try:
        pages = pdf_pages(path, data_dir / "text-cache")
        image_only = sum(len(line["words"]) for page in pages for line in page["lines"]) < 50
        if use_ocr:
            pages = ocr_sparse_pages(path, pages, data_dir, skip_cover=doc["collection"] == "yearly")
            if doc["collection"] == "topical":
                pages = recover_compilation_headers(path, pages, data_dir)
            elif image_only:
                pages = recover_scanned_question_numbers(path, pages, data_dir)
        questions = extract_questions(pages, doc)
        for question in questions:
            if question.pop("needs_text_ocr", False):
                question["text"] = recover_question_text(question, path, data_dir) or f"Scanned question {question['number']} — open the original preview."
            question.update(classify(question["text"], doc["component"]))
            question["summary"] = summary(question["text"])
        result["questions"] = questions
        oversized = [q for q in questions if q["end_page"] - q["page"] > 8 and doc["component"] not in ("3", "5")]
        if oversized:
            result["questions"] = [q for q in questions if q not in oversized]
            result.update(state="needs_review", note=f"Omitted {len(oversized)} sections with uncertain question boundaries")
        if not questions:
            result.update(state="needs_review", note="No reliable numbered-question boundaries found")
        elif doc["collection"] == "yearly" and doc["component"] == "1" and len(questions) != 40:
            result.update(state="needs_review", note=f"Found {len(questions)} of the expected 40 multiple-choice questions")
        elif (doc["collection"] == "yearly" and doc["component"] in ("3", "5")
              and (doc["year"] or 0) >= 2007 and len(questions) != 2):
            result.update(state="needs_review", note=f"Found {len(questions)} of the expected 2 questions")
        if any(p.get("ocr") for p in pages):
            result["note"] = (result["note"] + "; " if result["note"] else "") + "Includes locally recognised scan text"
    except Exception as exc:
        result.update(state="needs_review", note=str(exc)[:400])
    return result


def build_index(data_dir=BASE / "data", catalogue_path=BASE / "catalogue.json", workers=4, use_ocr=True):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    catalogue = load_catalogue(catalogue_path)
    papers, _ = build_tests(catalogue["documents"])
    documents = [doc for doc in papers if doc["collection"] in ("yearly", "topical")]
    documents.sort(key=lambda d: (d["collection"] != "yearly", -(d["year"] or 0), d["filename"]))
    temporary = data_dir / "tasks.build.sqlite3"
    temporary.unlink(missing_ok=True)
    temporary.with_name(temporary.name + "-journal").unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    db.executescript(SCHEMA)
    counts = {"questions": 0, "documents": 0, "needs_review": 0}
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            jobs = {executor.submit(process_document, doc, data_dir, use_ocr): doc for doc in documents}
            for future in as_completed(jobs):
                result = future.result()
                doc, questions = result["document"], result["questions"]
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (doc["id"], doc["filename"], doc["collection"], doc["year"], doc["session"], doc["component"],
                            json.dumps(doc, ensure_ascii=False), len(questions), result["state"], result["note"]))
                for q in questions:
                    db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (q["id"], q["document_id"], q["number"], q["occurrence"], q["page"], q["end_page"],
                                q["text"], q["summary"], json.dumps(q["regions"]), json.dumps(q["subparts"]),
                                json.dumps(q["topics"]), q["confidence"], json.dumps(q["evidence"])))
                counts["questions"] += len(questions)
                counts["documents"] += 1
                counts["needs_review"] += result["state"] == "needs_review"
                print(f"{counts['documents']}/{len(documents)} {doc['filename']}: {len(questions)} questions"
                      f" · {result['state']} · {counts['questions']} total", flush=True)
        db.execute("INSERT INTO metadata VALUES('indexed_at',?)", (datetime.now(timezone.utc).isoformat(),))
        db.execute("INSERT INTO metadata VALUES('version','1')")
        build_type_index(db)
        db.commit()
        db.close()
        temporary.replace(data_dir / "tasks.sqlite3")
        print(json.dumps(counts), flush=True)
        return counts
    except BaseException:
        db.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=BASE / "data")
    parser.add_argument("--catalogue", type=Path, default=BASE / "catalogue.json")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--no-ocr", action="store_true", help="Extract selectable PDF text only")
    args = parser.parse_args()
    build_index(args.data_dir, args.catalogue, args.workers, not args.no_ocr)


if __name__ == "__main__":
    main()
