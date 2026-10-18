"""PapaCambridge catalogue parsing. Uses only the Python standard library."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlunsplit

BASE = Path(__file__).resolve().parent
SOURCE = "https://pastpapers.papacambridge.com/papers/caie/as-and-a-level-physics-9702"
ORIGIN = "https://pastpapers.papacambridge.com/"
PAPERS = {
    "1": "Multiple choice", "2": "AS structured questions",
    "3": "Advanced practical skills", "4": "A Level structured questions",
    "5": "Planning, analysis and evaluation", "6": "Legacy paper 6",
}
SESSIONS = {"m": "February / March", "s": "May / June", "w": "October / November"}
KINDS = {"qp": "Question paper", "ms": "Mark scheme", "ci": "Practical instructions",
         "in": "Insert", "ir": "Practical instructions", "er": "Examiner report", "gt": "Grade thresholds"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join(" ".join(self.label).split())))
            self.href = None


def identifier(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def normalize_url(value):
    parts = urlsplit(urljoin(ORIGIN, value))
    if parts.scheme != "https" or parts.netloc != urlsplit(ORIGIN).netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe="/"), "", ""))


def parse_page(html, page_url):
    parser = Links()
    parser.feed(html)
    folders, files = {}, {}
    for href, label in parser.links:
        if "download_file.php?" in href:
            query = urlsplit(href).query
            values = parse_qs(query).get("files", [])
            href = values[0] if values else ""
            # Some source links put a literal ampersand inside an unescaped filename.
            if not href.lower().endswith(".pdf") and query.startswith("files="):
                full_value = unquote(query[len("files="):])
                if full_value.lower().endswith(".pdf"):
                    href = full_value
        url = normalize_url(href)
        if not url:
            continue
        if url.lower().endswith(".pdf") and urlsplit(url).path.startswith("/directories/"):
            files[url] = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
        elif (not urlsplit(href).fragment and url.startswith(page_url + "-")
              and url.startswith(SOURCE + "-")):
            folders[url] = label
    return folders, files


def document(url, filename, folder_url, folder_name, folder_path):
    collection = ("topical" if "-topical-past-papers" in folder_url else
                  "solutions" if "-solved-past-papers" in folder_url else "yearly")
    match = re.match(r"9702_([msw])(\d{2})_([a-z]+)(?:_(\d{1,2}))?(?:_.*)?\.pdf$", filename, re.I)
    data = {"id": identifier(url), "url": url, "filename": filename,
            "folder_url": folder_url, "folder": folder_name, "folder_path": folder_path,
            "collection": collection, "year": None, "session": None,
            "component": None, "variant": None, "kind": "resource"}
    if match:
        session, year, kind, variant = match.groups()
        if not variant:
            extra_variant = re.search(r"_et_(\d{1,2})\.pdf$", filename, re.I)
            if extra_variant:
                variant = extra_variant[1]
        year_num = int(year)
        year_num += 2000 if year_num < 80 else 1900
        data.update(year=year_num, session=session.lower(), kind=kind.lower(), variant=variant,
                    component=variant[0] if variant else None)
        data["title"] = (f"Paper {variant}" if variant else KINDS.get(kind.lower(), kind))
    else:
        title = re.sub(r"[_]+", " ", Path(filename).stem)
        data["title"] = title
        component = re.search(r"\b(?:paper\s*|p)([1-6])\b", title, re.I)
        if not component:
            for ancestor in reversed(folder_path):
                component = re.search(r"\b(?:paper\s*|p)([1-6])\b", ancestor, re.I)
                if component:
                    break
        if component:
            data["component"] = component[1]
        if collection == "topical" and re.search(
                r"(?:[,_\s-]ms|\s*-\s*answers(?:\s*\(all topics\))?)\s*$", Path(filename).stem, re.I):
            data["kind"] = "ms"
        if collection == "yearly":
            data["kind"] = "resource"
    safe_name = re.sub(r"[^\w.() -]", "_", filename)[:180]
    data["local_path"] = f"papers/{data['id']}/{safe_name}"
    return data


def load_catalogue(path=None):
    path = Path(path or BASE / "catalogue.json")
    if not path.exists():
        return {"source": SOURCE, "synced_at": None, "documents": [], "errors": []}
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_tests(documents):
    """Pair real question papers with resources; never manufacture missing files."""
    matching = {}
    topical_answers = {}
    for doc in documents:
        if doc["year"]:
            key = (doc["year"], doc["session"], doc["variant"], doc["kind"])
            matching.setdefault(key, doc)
        if doc["collection"] == "topical" and doc["kind"] == "ms":
            topical_answers[(doc["folder_url"], doc["component"], topical_key(doc))] = doc
    tests, resources = [], []
    for doc in documents:
        if (doc["collection"] == "yearly" and doc["kind"] != "qp") or doc["kind"] == "ms":
            resources.append(doc)
            continue
        test = dict(doc)
        attachments = []
        if doc["kind"] == "qp":
            for kind in ("ms", "ci", "in", "ir", "er", "gt"):
                variant = None if kind in ("er", "gt") else doc["variant"]
                other = matching.get((doc["year"], doc["session"], variant, kind))
                if other is None and kind == "ms":
                    other = matching.get((doc["year"], doc["session"], None, kind))
                if other:
                    attachments.append({"id": other["id"], "kind": kind,
                                        "label": KINDS[kind], "filename": other["filename"]})
        elif doc["collection"] == "topical":
            other = topical_answers.get((doc["folder_url"], doc["component"], topical_key(doc)))
            if other is None:
                other = next((answer for answer in documents
                              if answer["folder_url"] == doc["folder_url"]
                              and answer["component"] == doc["component"]
                              and answer["kind"] == "ms" and "(all topics)" in answer["filename"].lower()), None)
            if other:
                attachments.append({"id": other["id"], "kind": "ms",
                                    "label": "Answer key", "filename": other["filename"]})
        test["attachments"] = attachments
        test["groups"] = groups_for(test)
        tests.append(test)
    return tests, resources


def topical_key(doc):
    stem = Path(doc["filename"]).stem
    stem = re.sub(r"(?:[_ ,\-]+(?:qp|ms)|\s*-\s*answers(?:\s*\(all topics\))?)\s*$", "", stem, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", stem.lower())


def groups_for(test):
    result = [f"collection:{test['collection']}", f"folder:{identifier(test['folder_url'])}"]
    if test.get("year"):
        result.extend([f"year:{test['year']}", f"session:{test['year']}:{test['session']}"])
    if test.get("component"):
        result.append(f"paper:{test['component']}")
    return result
