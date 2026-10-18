"""Render exact question regions; the source PDF remains the authoritative content."""
import hashlib
from pathlib import Path
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

from .questions import pdf_pages


def render_question(task, region_number, pdf_path, data_dir, index_stamp, compact=False):
    if not 0 <= region_number < len(task["regions"]):
        raise ValueError("Unknown question page")
    region = task["regions"][region_number]
    folder = Path(data_dir) / "task-images"
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{task['id']}:{region_number}:{index_stamp}:3:{compact}".encode()).hexdigest()[:24]
    output = folder / (key + ".png")
    if output.exists():
        return output
    ratio = 1000 / region["width"]
    top = max(0, int(region["top"] * ratio))
    height = max(1, int((region["bottom"] - region["top"]) * ratio))
    prefix = folder / (key + ".tmp")
    subprocess.run(["pdftoppm", "-f", str(region["page"]), "-l", str(region["page"]),
                    "-singlefile", "-scale-to-x", "1000", "-scale-to-y", "-1", "-x", "0",
                    "-y", str(top), "-W", "1000", "-H", str(height), "-png", str(pdf_path), str(prefix)],
                   check=True, capture_output=True, timeout=45)
    rendered = Path(str(prefix) + ".png")
    if compact:
        trim_reading_margins(rendered, trim_vertical=task.get("component") == "1")
    rendered.replace(output)
    return output


def trim_reading_margins(path, trim_vertical=False):
    """Make small questions readable; retain full-resolution originals separately.

    Determine bounds using dark content so pale publisher watermarks
    do not preserve a whole empty page width. Crop the original colour pixels,
    with generous padding; do not threshold or rewrite the displayed question.
    Only MCQs omit unused vertical space. ImageMagick is optional, and any
    failure leaves the original crop intact.
    """
    converter = shutil.which("magick") or shutil.which("convert")
    if not converter:
        return
    temporary = path.with_name(path.stem + ".trim.png")
    try:
        result = subprocess.run([converter, str(path), "-colorspace", "Gray", "-threshold", "85%",
                                 "-format", "%@", "info:"], capture_output=True, text=True, check=True, timeout=15)
        match = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", result.stdout.strip())
        if not match:
            return
        width, height, left, top = map(int, match.groups())
        if width <= 0 or height <= 0:
            return
        with path.open('rb') as stream:
            header = stream.read(24)
        canvas_width, canvas_height = struct.unpack('>II', header[16:24])
        right = min(1000, left + width + 28)
        left = max(0, left - 28)
        bottom = min(canvas_height, top + height + 14) if trim_vertical else canvas_height
        top = max(0, top - 14) if trim_vertical else 0
        if right - left >= canvas_width - 40 and bottom - top >= canvas_height - 20:
            return
        subprocess.run([converter, str(path), "-crop", f"{right-left}x{bottom-top}+{left}+{top}", "+repage", str(temporary)],
                       check=True, capture_output=True, timeout=15)
        temporary.replace(path)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        temporary.unlink(missing_ok=True)


def answer_page(path, number, cache_dir, multiple_choice=False):
    """Locate the question's first rubric row, without guessing an answer."""
    try:
        pages = pdf_pages(path, cache_dir)
    except (ValueError, OSError, subprocess.SubprocessError, ET.ParseError):
        return None
    for page_number, page in enumerate(pages, 1):
        if page_number == 1 and len(pages) > 1:
            continue
        rubric = {line["text"].strip().lower() for line in page["lines"]}
        if multiple_choice:
            words = [word for line in page["lines"] for word in line["words"]
                     if 55 < line["y"] < page["height"] * .91]
            for word in words:
                if word[0] == str(number) and word[1] < page["width"] * .65:
                    if any(other[0] in ("A", "B", "C", "D") and other[1] > word[3] + 5
                           and abs(other[2] - word[2]) < 5 for other in words):
                        return page_number
        for line in page["lines"]:
            if not 50 < line["y"] < page["height"] * .91:
                continue
            if multiple_choice:
                if re.search(rf"(?:^|\s){number}\s+[A-D](?:\s|$)", line["text"]):
                    return page_number
            elif line["x"] < page["width"] * .27 and re.match(
                    rf"^{number}(?:\s*\([a-zivx]+\)|\s+[A-Za-z])", line["text"]):
                return page_number
            elif not multiple_choice and {"question", "answer", "marks"} <= rubric:
                if line["x"] < page["width"] * .27 and line["text"].strip() == str(number):
                    return page_number
    return None
