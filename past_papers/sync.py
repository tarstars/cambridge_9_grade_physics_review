"""Discover and resumably download the Physics 9702 archive.

Run from the repository root: python3 -m past_papers.sync
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

from .catalogue import BASE, SOURCE, atomic_json, document, identifier, load_catalogue, parse_page

HEADERS = {"User-Agent": "PhysicsStudyLibrary/1.0 (personal exam preparation)",
           "Referer": SOURCE}


def fetch(url, attempts=3):
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=45) as response:
                return response.read()
        except (OSError, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(1 + attempt)


def discover(data_dir, workers=4, refresh=False):
    pending = {SOURCE: ("Physics 9702", [])}
    seen, docs, errors = set(), {}, []
    cache = data_dir / "pages"
    cache.mkdir(parents=True, exist_ok=True)

    def page(url):
        path = cache / (identifier(url) + ".html")
        if not refresh and path.exists() and time.time() - path.stat().st_mtime < 86400:
            return path.read_text(encoding="utf-8")
        html = fetch(url).decode("utf-8", errors="replace")
        path.write_text(html, encoding="utf-8")
        return html

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while pending:
            batch, pending = pending, {}
            futures = {executor.submit(page, url): (url, name, parents)
                       for url, (name, parents) in batch.items() if url not in seen}
            for future in as_completed(futures):
                url, name, parents = futures[future]
                seen.add(url)
                try:
                    folders, files = parse_page(future.result(), url)
                except Exception as exc:
                    errors.append({"url": url, "error": str(exc)})
                    print(f"Folder unavailable: {url}: {exc}", flush=True)
                    continue
                path = parents + [name] if url != SOURCE else []
                for child, title in folders.items():
                    if child not in seen:
                        pending[child] = (title, path)
                for file_url, filename in files.items():
                    docs.setdefault(file_url, document(file_url, filename, url, name, path))
                print(f"Indexed {name}: {len(files)} files ({len(docs)} total)", flush=True)
    return list(docs.values()), errors, len(seen)


def valid_pdf(path):
    try:
        with path.open("rb") as stream:
            size = path.stat().st_size
            signature = b"%PDF-" in stream.read(1024)
            stream.seek(max(0, size - 4096))
            return signature and size > 100 and b"%%EOF" in stream.read()
    except OSError:
        return False


def download(doc, data_dir):
    path = data_dir / doc["local_path"]
    if valid_pdf(path):
        return "cached", path.stat().st_size
    if path.exists():
        # Preserve an invalid source file for inspection, but never advertise it as usable.
        path.replace(path.with_suffix(path.suffix + ".invalid"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    for attempt in range(3):
        try:
            with urlopen(Request(doc["url"], headers=HEADERS), timeout=60) as response:
                expected = response.headers.get("Content-Length")
                size = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(262144):
                        output.write(chunk)
                        size += len(chunk)
                if expected and size != int(expected):
                    raise ValueError("Incomplete response")
            if not valid_pdf(temporary):
                raise ValueError("Source returned a non-PDF or truncated PDF")
            temporary.replace(path)
            return "downloaded", size
        except (OSError, ValueError) as exc:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                return "failed", str(exc)
            time.sleep(1 + attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=BASE / "data")
    parser.add_argument("--catalogue", type=Path, default=BASE / "catalogue.json")
    parser.add_argument("--index-only", action="store_true", help="Discover PDFs without downloading")
    parser.add_argument("--download-only", action="store_true", help="Use the existing catalogue")
    parser.add_argument("--refresh", action="store_true", help="Bypass the one-day HTML cache")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--years", type=int, nargs="+", help="Limit downloads (not discovery) to these years")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    catalogue = load_catalogue(args.catalogue)
    if not args.download_only:
        docs, errors, folders = discover(args.data_dir, args.workers, args.refresh)
        # Keep previously indexed files if a source folder is temporarily unavailable.
        new_urls = {doc["url"] for doc in docs}
        docs.extend(doc for doc in catalogue["documents"] if doc["url"] not in new_urls)
        if not docs:
            raise SystemExit("No PDFs discovered; previous catalogue was left untouched.")
        catalogue = {"version": 1, "source": SOURCE,
                     "synced_at": datetime.now(timezone.utc).isoformat(),
                     "folders_scanned": folders, "errors": errors,
                     "documents": sorted(docs, key=lambda d: d["url"])}
        atomic_json(args.catalogue, catalogue)
        print(f"Catalogue saved: {len(docs)} PDFs, {len(errors)} folder errors", flush=True)
    if args.index_only:
        return
    documents = [d for d in catalogue["documents"] if not args.years or d["year"] in args.years]
    # Recent exams first; topical resources next; older sessions afterwards.
    documents.sort(key=lambda d: (-(d["year"] or 2020), d["kind"] != "qp", d["filename"]))
    counts = {"downloaded": 0, "cached": 0, "failed": 0}
    errors, total_bytes = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download, doc, args.data_dir): doc for doc in documents}
        for future in as_completed(futures):
            doc = futures[future]
            state, result = future.result()
            counts[state] += 1
            if state == "failed":
                errors.append({"id": doc["id"], "url": doc["url"], "error": result})
                print(f"Unavailable: {doc['filename']}: {result}", flush=True)
            else:
                total_bytes += result
            finished = sum(counts.values())
            if finished % 25 == 0 or finished == len(documents):
                print(f"{finished}/{len(documents)} PDFs | {counts} | {total_bytes / 1048576:.1f} MiB", flush=True)
    report = {"finished_at": datetime.now(timezone.utc).isoformat(), "counts": counts,
              "bytes": total_bytes, "errors": errors, "years": args.years}
    atomic_json(args.data_dir / "download-report.json", report)
    print(json.dumps(report["counts"]), flush=True)
    if errors or catalogue.get("errors"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
