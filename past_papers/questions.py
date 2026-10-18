"""Extract numbered questions and their PDF regions with Poppler's text geometry."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from statistics import median
import xml.etree.ElementTree as ET

EXTRACTOR_VERSION = 1
OCR_SLOTS = threading.BoundedSemaphore(4)
NOISE = re.compile(r"(?:papacambridge|trace id:|licensed for hosting|re-uploading|downloaded from|"
                   r"do not write in this margin|examiner.?s|^Use$|©|\[turn over|9702/\d+/[A-Z/]+/\d+)", re.I)


def pdf_pages(path, cache_dir=None):
    path = Path(path)
    stamp = f"{EXTRACTOR_VERSION}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
    cache = Path(cache_dir) / (path.parent.name + ".json.gz") if cache_dir else None
    if cache and cache.exists():
        try:
            with gzip.open(cache, "rt", encoding="utf-8") as stream:
                saved = json.load(stream)
            if saved["stamp"] == stamp:
                return saved["pages"]
        except (OSError, ValueError):
            pass
    result = subprocess.run(["pdftotext", "-bbox-layout", str(path), "-"], capture_output=True, timeout=90)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace")[:300] or "PDF text extraction failed")
    xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", result.stdout.decode("utf-8", "replace"))
    root = ET.fromstring(xml)
    pages = []
    for element in root.findall(".//{*}page"):
        lines = []
        for line in element.findall(".//{*}line"):
            words = [[word.text or "", *[round(float(word.get(key)), 2)
                                       for key in ("xMin", "yMin", "xMax", "yMax")]]
                     for word in line.findall("{*}word")]
            if not words:
                continue
            lines.append({"text": " ".join(word[0] for word in words), "words": words,
                          "x": float(line.get("xMin")), "y": float(line.get("yMin")),
                          "bottom": float(line.get("yMax"))})
        pages.append({"width": float(element.get("width")), "height": float(element.get("height")),
                      "lines": sorted(lines, key=lambda line: (round(line["y"] / 2), line["x"]))})
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(cache.with_suffix(".tmp"), "wt", encoding="utf-8", compresslevel=3) as stream:
            json.dump({"stamp": stamp, "pages": pages}, stream)
        cache.with_suffix(".tmp").replace(cache)
    return pages


def body_lines(page, topical=False):
    return [line for line in page["lines"] if (23 if topical or page.get("ocr") else 50) < line["y"] < page["height"] * (.945 if topical else .91)
            and not NOISE.search(line["text"]) and re.search(r"[A-Za-z0-9]", line["text"])]


def candidates(pages, skip_cover=True):
    result = []
    for index, page in enumerate(pages):
        if index == 0 and skip_cover:
            continue  # examination cover, instructions, and page count
        lines = body_lines(page, topical=not skip_cover)
        words = [word for line in lines for word in line["words"]]
        for word in words:
            token = "5" if page.get("ocr") and word[0] == "§" else word[0]
            match = re.fullmatch(r"(\d{1,5})(?:[.,)]|\([a-z]\))?", token, re.I)
            if not match or not 1 <= int(match[1]) <= 99999 or not 18 < word[1] < page["width"] * (.15 if skip_cover else .28):
                continue
            if int(match[1]) > 99 and not word[0].endswith((".", ",")):
                continue
            same_line = [other for other in words if other[1] > word[3] + 2
                         and abs(other[2] - word[2]) < 8]
            context = " ".join(other[0] for other in sorted(same_line, key=lambda w: w[1]))
            if len(re.sub(r"[^A-Za-z]", "", context)) < 3:
                if skip_cover and not page.get("ocr"):
                    continue
                below = [line for line in lines if word[2] + 3 <= line["y"] <= word[2] + 45
                         and word[1] - 2 <= line["x"] <= word[1] + 65]
                context = " ".join(line["text"] for line in sorted(below, key=lambda line: line["y"])[:2])
                if len(re.sub(r"[^A-Za-z]", "", context)) < 8:
                    continue
            if len(re.sub(r"[^A-Za-z]", "", context)) < 3:
                continue
            heading_y = min([word[2]] + [line["y"] for line in lines
                            if word[1] - 1 <= line["x"] <= word[1] + 40
                            and abs(line["y"] - word[2]) < 10])
            result.append({"number": int(match[1]), "page": index + 1, "y": heading_y,
                           "x": word[1], "context": context, "enumerated": word[0].endswith((".", ","))})
    return sorted(result, key=lambda item: (item["page"], item["y"], item["x"]))


def question_starts(pages, yearly=True):
    recovered = [header for page in pages for header in page.get("question_headers", [])]
    if recovered:
        return sorted(recovered, key=lambda item: (item["page"], item["y"]))
    if not yearly:
        labelled = []
        for index, page in enumerate(pages):
            for line in page["lines"]:
                label = line["text"].strip()
                match = re.fullmatch(r"Q\.?\s*([0-9IiLl]{1,5})[.)]?", label, re.I)
                if match and ("." in label or ")" in label) and 23 < line["y"] < page["height"] * .9:
                    number = int(match[1].translate(str.maketrans({"I": "1", "i": "1", "l": "1", "L": "1"})))
                    labelled.append({"number": number, "page": index + 1, "y": line["y"],
                                     "x": line["x"], "context": label})
        if labelled:
            margin = median(item["x"] for item in labelled)
            heights = [line["bottom"] - line["y"] for page in pages for line in page["lines"]
                       if re.fullmatch(r"Q\.?\s*[0-9IiLl]{1,5}[.)]?", line["text"].strip(), re.I)]
            height = median(heights)
            occupied = {(item["page"], round(item["y"])) for item in labelled}
            for index, page in enumerate(pages):
                for line in page["lines"]:
                    if abs(line["x"] - margin) > 5 or not 23 < line["y"] < page["height"] * .9:
                        continue
                    if not height * .85 <= line["bottom"] - line["y"] <= height * 1.5:
                        continue
                    match = re.fullmatch(r"[Oo]?([0-9]{1,5})[.)]?", line["text"].strip())
                    if match and int(match[1]) and (index + 1, round(line["y"])) not in occupied:
                        labelled.append({"number": int(match[1]), "page": index + 1, "y": line["y"],
                                         "x": line["x"], "context": line["text"]})
            return sorted(labelled, key=lambda item: (item["page"], item["y"]))
        headers = []
        citation = re.compile(r"9702[_/]|(?:Nov|Oct|Jun|June|Mar|March|May)/\d{4}/Paper[_ ]", re.I)
        for index, page in enumerate(pages):
            for line in page["lines"]:
                if not 23 < line["y"] < page["height"] * .9 or line["x"] > page["width"] * .3:
                    continue
                if not citation.search(line["text"]):
                    continue
                local = re.match(r"^(\d{1,5})[.)]\s*", line["text"])
                original = re.search(r"No\.?\s*(\d{1,5})", line["text"], re.I)
                if local is None:
                    for other in page["lines"]:
                        if other["x"] < line["x"] and line["x"] - other["x"] < 55 and abs(other["y"] - line["y"]) < 7:
                            local = re.fullmatch(r"(\d{1,5})[.)]", other["text"].strip())
                            if local:
                                break
                if not local and not original:
                    continue
                number = int((local or original)[1])
                headers.append({"number": number, "page": index + 1, "y": line["y"],
                                "x": line["x"], "context": line["text"], "local_number": int(local[1]) if local else None})
        if headers:
            headers.sort(key=lambda item: (item["page"], item["y"]))
            offsets = Counter(item["local_number"] - i for i, item in enumerate(headers) if item["local_number"] is not None)
            offset = offsets.most_common(1)[0][0] if offsets else 1
            for i, item in enumerate(headers):
                if item["local_number"] is None:
                    item["number"] = max(1, offset + i)
            return headers
    possible = candidates(pages, skip_cover=yearly)
    if not possible:
        return []
    if yearly:
        # Printed question numbers form one sequence at a common left margin.
        best, chains = [], []
        tolerance = 30 if any(page.get("ocr") for page in pages) else 8
        for first in (item for item in possible if item["number"] == 1):
            chain, expected = [], 1
            for item in possible:
                if (item["page"], item["y"]) < (first["page"], first["y"]):
                    continue
                if abs(item["x"] - first["x"]) <= tolerance and item["number"] == expected:
                    chain.append(item)
                    expected += 1
            if len(chain) > len(best):
                best = chain
            if len(chain) >= 3:
                chains.append(chain)
        for chain in chains:
            if best and (chain[0]["page"], chain[0]["y"]) > (best[-1]["page"], best[-1]["y"]):
                best = best + chain
        return best
    # Compilations may repeat the original paper's numbering. Keep occurrences separate.
    enumerated = []
    for index, page in enumerate(pages):
        for line in body_lines(page, topical=True):
            match = re.fullmatch(r"(\d{1,5})[.,]", line["text"].strip())
            if match and 18 < line["x"] < page["width"] * .28:
                enumerated.append({"number": int(match[1]), "page": index + 1, "y": line["y"],
                                   "x": line["x"], "context": line["text"], "enumerated": True})
    if len(enumerated) >= 5:
        common = Counter(round(item["x"] / 6) for item in enumerated).most_common(1)[0][0] * 6
        enumerated = [item for item in enumerated if abs(item["x"] - common) <= 8]
    counts = Counter(round(item["x"] / 6) for item in possible)
    margin = counts.most_common(1)[0][0] * 6
    major = [item for item in possible if abs(item["x"] - margin) <= 8]
    if enumerated:
        annotated_pages = {item["page"] for item in enumerated}
        major = [item for item in major if item["page"] not in annotated_pages] + enumerated
        major.sort(key=lambda item: (item["page"], item["y"]))
    enumerated_pages = {item["page"] for item in major if item.get("enumerated")}
    return [item for item in major if item["page"] not in enumerated_pages or item.get("enumerated")]


def extract_questions(pages, document):
    yearly = document["collection"] == "yearly"
    starts = question_starts(pages, yearly)
    questions, occurrences = [], Counter()
    for position, start in enumerate(starts):
        following = starts[position + 1] if position + 1 < len(starts) else None
        stop_page = following["page"] if following else len(pages)
        if yearly and document.get("component") == "1" and following is None:
            # A damaged paper can lose later question text but retain unrelated diagrams.
            stop_page = start["page"]
        regions, text = [], []
        for page_number in range(start["page"], stop_page + 1):
            page = pages[page_number - 1]
            if page_number > start["page"]:
                heading = " ".join(line["text"] for line in body_lines(page))
                if re.search(r"READ THESE INSTRUCTIONS FIRST|Candidates answer on the Question Paper", heading):
                    break  # a second examination can be bundled in the same source PDF
            top = start["y"] - 3 if page_number == start["page"] else 25 if not yearly or page.get("ocr") else 52
            bottom = following["y"] - 7 if following and page_number == following["page"] else page["height"] * (.94 if not yearly else .905)
            if bottom <= top:
                continue
            lines = [line for line in body_lines(page, topical=not yearly) if top - 1 <= line["y"] < bottom]
            content = "\n".join(line["text"] for line in lines)
            recovered_start = page_number == start["page"] and bool(page.get("question_headers"))
            if (not content.strip() and not recovered_start) or re.fullmatch(r"\s*BLANK PAGE\s*", content, re.I):
                continue
            # Permission/acknowledgement pages follow the final question in some papers.
            if page_number > start["page"] and re.search(r"copyright acknowledgements|permission to reproduce|intentionally blank", content, re.I):
                break
            regions.append({"page": page_number, "top": round(max(0, top), 2),
                            "bottom": round(min(page["height"], bottom), 2),
                            "width": page["width"], "height": page["height"]})
            text.append(content)
        combined = "\n\n".join(text)
        combined = re.sub(r"(?m)^\s*\.{4,}.*$", "", combined)
        combined = re.sub(r"\n{3,}", "\n\n", combined).strip()
        needs_text_ocr = len(re.sub(r"[^A-Za-z]", "", combined)) < 8
        if not regions or (needs_text_ocr and not pages[start["page"] - 1].get("question_headers")):
            continue
        occurrences[start["number"]] += 1
        occurrence = occurrences[start["number"]]
        key = f"{document['id']}-q{start['number']}" + (f"-o{occurrence}" if occurrence > 1 else "")
        subparts = list(dict.fromkeys(re.findall(r"(?m)^\s*(?:\d+\s+)?\(([a-h])\)", combined)))
        questions.append({"id": key, "document_id": document["id"], "number": start["number"],
                          "occurrence": occurrence, "text": combined, "regions": regions,
                          "page": regions[0]["page"], "end_page": regions[-1]["page"],
                          "subparts": subparts, "needs_text_ocr": needs_text_ocr})
    return questions


def ocr_executable(data_dir):
    local = Path(data_dir) / "ocr-tools" / "usr" / "bin" / "tesseract"
    return str(local) if local.exists() else shutil.which("tesseract")


def ocr_page(path, page_number, page, data_dir):
    """OCR stays local. Convert pixel coordinates back to PDF points for previews."""
    cache = Path(data_dir) / "text-cache" / f"{Path(path).parent.name}-ocr-{page_number}.json.gz"
    stamp = f"{Path(path).stat().st_size}:{Path(path).stat().st_mtime_ns}:150:tsv2"
    if cache.exists():
        with gzip.open(cache, "rt", encoding="utf-8") as stream:
            saved = json.load(stream)
        if saved["stamp"] == stamp:
            return saved["page"]
    binary = ocr_executable(data_dir)
    if not binary:
        return page
    with OCR_SLOTS, tempfile.TemporaryDirectory(prefix="physics-ocr-") as temporary:
        prefix = Path(temporary) / "page"
        subprocess.run(["pdftoppm", "-f", str(page_number), "-l", str(page_number), "-r", "150",
                        "-singlefile", "-png", str(path), str(prefix)], check=True, capture_output=True, timeout=60)
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        models = Path(data_dir) / "ocr-tools" / "usr/share/tesseract-ocr/4.00/tessdata"
        if models.exists():
            env["TESSDATA_PREFIX"] = str(models)
        result = subprocess.run([binary, str(prefix) + ".png", "stdout", "-l", "eng", "-c", "tessedit_create_tsv=1"],
                                env=env, capture_output=True, check=True, timeout=90)
    words_by_line = {}
    if not result.stdout.startswith(b"level\t"):
        raise ValueError("OCR did not return word coordinates")
    for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8", "replace")), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") != "5" or not (row.get("text") or "").strip():
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        left, top, width, height = (float(row[x]) * 72 / 150 for x in ("left", "top", "width", "height"))
        words_by_line.setdefault(key, []).append([row["text"], left, top, left + width, top + height])
    lines = []
    for words in words_by_line.values():
        lines.append({"text": " ".join(w[0] for w in words), "words": words,
                      "x": min(w[1] for w in words), "y": min(w[2] for w in words),
                      "bottom": max(w[4] for w in words)})
    converted = {**page, "lines": sorted(lines, key=lambda line: (round(line["y"] / 2), line["x"])), "ocr": True}
    cache.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(cache, "wt", encoding="utf-8") as stream:
        json.dump({"stamp": stamp, "page": converted}, stream)
    return converted


def ocr_sparse_pages(path, pages, data_dir, skip_cover=True):
    if not ocr_executable(data_dir):
        return pages
    result = list(pages)
    pending = []
    for i, page in enumerate(pages):
        text = " ".join(line["text"] for line in body_lines(page))
        sparse = len(re.sub(r"[^A-Za-z]", "", text)) < 35
        if not skip_cover and sum(len(line["words"]) for line in body_lines(page)) < 45:
            sparse = True
        if ((i or not skip_cover) and sparse
                and not re.search(r"blank page|copyright acknowledg|permission to reproduce", text, re.I)):
            pending.append(i)
    def read(index):
        return index, ocr_page(path, index + 1, pages[index], data_dir)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for index, converted in executor.map(read, pending):
            result[index] = converted
    return result


def recover_compilation_headers(path, pages, data_dir):
    """Read the narrow Q1./Q2. label column separately from noisy scanned problems."""
    labels = [(line, page) for page in pages for line in page["lines"]
              if re.match(r"^Q\s*[0-9IiLlSs?]+[.)]", line["text"], re.I)
              and 23 < line["y"] < page["height"] * .9]
    if len(labels) < 2 or not ocr_executable(data_dir):
        return pages
    margin = median(line["x"] for line, _ in labels)
    left = max(0, margin - 10)
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    models = Path(data_dir) / "ocr-tools/usr/share/tesseract-ocr/4.00/tessdata"
    if models.exists():
        env["TESSDATA_PREFIX"] = str(models)
    headers = []
    stamp = f"{Path(path).stat().st_size}:{Path(path).stat().st_mtime_ns}:{left}:300:1"
    for index, page in enumerate(pages):
        cache = Path(data_dir) / "text-cache" / f"{Path(path).parent.name}-labels-{index + 1}.json.gz"
        saved = None
        if cache.exists():
            with gzip.open(cache, "rt", encoding="utf-8") as stream:
                value = json.load(stream)
            if value.get("stamp") == stamp:
                saved = value["headers"]
        if saved is None:
            with OCR_SLOTS, tempfile.TemporaryDirectory(prefix="physics-label-") as temporary:
                prefix = Path(temporary) / "labels"
                subprocess.run(["pdftoppm", "-f", str(index + 1), "-l", str(index + 1), "-r", "300",
                                "-x", str(int(left * 300 / 72)), "-W", str(int(46 * 300 / 72)),
                                "-singlefile", "-png", str(path), str(prefix)],
                               capture_output=True, check=True, timeout=60)
                result = subprocess.run([ocr_executable(data_dir), str(prefix) + ".png", "stdout", "-l", "eng",
                                         "--psm", "6", "-c", "tessedit_create_tsv=1"],
                                        capture_output=True, check=True, timeout=45, env=env)
            saved = []
            for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8", "replace")), delimiter="\t", quoting=csv.QUOTE_NONE):
                word = row.get("text", "").strip()
                match = re.fullmatch(r"Q\.?([0-9IiLlSs?]{1,5})[.,)]?", word, re.I)
                if row.get("level") != "5" or not match or not word.endswith((".", ",", ")")):
                    continue
                top = float(row["top"]) * 72 / 300
                if not 23 < top < page["height"] * .9:
                    continue
                number = match[1].translate(str.maketrans({"I":"1","i":"1","l":"1","L":"1","s":"5","S":"5"}))
                saved.append({"number": int(number) if number.isdigit() else None, "page": index + 1,
                              "y": top, "x": left + float(row["left"]) * 72 / 300, "context": word})
            with gzip.open(cache, "wt", encoding="utf-8") as stream:
                json.dump({"stamp": stamp, "headers": saved}, stream)
        headers.extend(header for header in saved if header["context"].endswith((".", ",", ")")))
    for page_number, page in enumerate(pages, 1):
        for line in page["lines"]:
            match = re.match(r"^Q\s*([0-9IiLlSs?]+)[.)]", line["text"], re.I)
            if not match or not 23 < line["y"] < page["height"] * .9:
                continue
            label_word = next((word for word in line["words"] if re.match(r"^Q[0-9IiLlSs?]+[.)]", word[0], re.I)), None)
            label_y = label_word[2] if label_word else line["y"]
            if any(header["page"] == page_number and abs(header["y"] - label_y) < 18 for header in headers):
                continue
            number = match[1].translate(str.maketrans({"I":"1","i":"1","l":"1","L":"1","s":"5","S":"5"}))
            headers.append({"number": int(number) if number.isdigit() else None, "page": page_number,
                            "y": label_y, "x": line["x"], "context": line["text"]})
    headers.sort(key=lambda item: (item["page"], item["y"]))
    offsets = Counter(item["number"] - i for i, item in enumerate(headers) if item["number"] is not None)
    offset = offsets.most_common(1)[0][0] if offsets else 1
    for i, header in enumerate(headers):
        if header["number"] is None:
            header["number"] = max(1, offset + i)
    # These compilation templates run from Q1 through QN. Agreement at both ends
    # lets position resolve isolated OCR mistakes such as Q19 being read as Qi19.
    if headers and headers[0]["number"] == 1 and headers[-1]["number"] == len(headers):
        for i, header in enumerate(headers):
            header["number"] = i + 1
    result = [{**page, "question_headers": [h for h in headers if h["page"] == i + 1]}
              for i, page in enumerate(pages)]
    return result


def recover_scanned_question_numbers(path, pages, data_dir):
    """Recover isolated left-margin numbers that whole-page OCR often drops."""
    first = next((item for item in candidates(pages) if item["number"] == 1), None)
    if first is None or not ocr_executable(data_dir):
        return pages
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    models = Path(data_dir) / "ocr-tools/usr/share/tesseract-ocr/4.00/tessdata"
    if models.exists():
        env["TESSDATA_PREFIX"] = str(models)
    found = []
    for index, page in enumerate(pages):
        if index + 1 < first["page"]:
            continue
        left, width = page["width"] * .06, page["width"] * .08
        stamp = f"{Path(path).stat().st_size}:{Path(path).stat().st_mtime_ns}:300"
        cache = Path(data_dir) / "text-cache" / f"{Path(path).parent.name}-numbers-{index + 1}.json.gz"
        saved = None
        if cache.exists():
            with gzip.open(cache, "rt", encoding="utf-8") as stream:
                value = json.load(stream)
            if value["stamp"] == stamp:
                saved = value["numbers"]
        if saved is None:
            with OCR_SLOTS, tempfile.TemporaryDirectory(prefix="physics-number-") as temporary:
                prefix = Path(temporary) / "numbers"
                subprocess.run(["pdftoppm", "-f", str(index + 1), "-l", str(index + 1), "-r", "300",
                                "-x", str(int(left * 300 / 72)), "-W", str(int(width * 300 / 72)),
                                "-singlefile", "-png", str(path), str(prefix)], capture_output=True, check=True, timeout=60)
                result = subprocess.run([ocr_executable(data_dir), str(prefix) + ".png", "stdout", "--psm", "6",
                                         "-c", "tessedit_create_tsv=1"], env=env, capture_output=True, check=True, timeout=45)
            saved = []
            for row in csv.DictReader(io.StringIO(result.stdout.decode("utf-8", "replace")), delimiter="\t", quoting=csv.QUOTE_NONE):
                token = row.get("text", "").strip().strip(".,)")
                if row.get("level") != "5" or not token.isdigit() or not 1 <= int(token) <= 30:
                    continue
                top = float(row["top"]) * 72 / 300
                if float(row["height"]) * 72 / 300 < 6 or not 23 < top < page["height"] * .9:
                    continue
                saved.append({"number": int(token), "page": index + 1, "y": top,
                              "x": left + float(row["left"]) * 72 / 300, "context": token})
            with gzip.open(cache, "wt", encoding="utf-8") as stream:
                json.dump({"stamp": stamp, "numbers": saved}, stream)
        found.extend(saved)
    combined = sorted(found + candidates(pages), key=lambda item: (item["page"], item["y"]))
    chain = [first]
    for item in combined:
        if (item["page"], item["y"]) <= (chain[-1]["page"], chain[-1]["y"] + 10):
            continue
        if item["number"] == len(chain) + 1:
            chain.append(item)
    return [{**page, "question_headers": [item for item in chain if item["page"] == index + 1]}
            for index, page in enumerate(pages)]


def recover_question_text(question, path, data_dir):
    if not ocr_executable(data_dir):
        return ""
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    models = Path(data_dir) / "ocr-tools/usr/share/tesseract-ocr/4.00/tessdata"
    if models.exists():
        env["TESSDATA_PREFIX"] = str(models)
    text = []
    for region in question["regions"]:
        with OCR_SLOTS, tempfile.TemporaryDirectory(prefix="physics-question-text-") as temporary:
            prefix = Path(temporary) / "question"
            subprocess.run(["pdftoppm", "-f", str(region["page"]), "-l", str(region["page"]), "-r", "300",
                            "-y", str(int(region["top"] * 300 / 72)),
                            "-H", str(max(1, int((region["bottom"] - region["top"]) * 300 / 72))),
                            "-singlefile", "-png", str(path), str(prefix)], capture_output=True, check=True, timeout=60)
            result = subprocess.run([ocr_executable(data_dir), str(prefix) + ".png", "stdout", "-l", "eng", "--psm", "6"],
                                    env=env, capture_output=True, check=True, timeout=45)
        text.append(result.stdout.decode("utf-8", "replace"))
    return "\n".join(text).strip()
