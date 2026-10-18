# Physics Review — foundation for grade 10

Reviewing physics to give a **solid basis entering grade 10**. The teacher flagged gaps in
earlier-year ("previous-class") physics, so the test covers the **physics program of grades
7–9** (everything below grade 10) — at the depth of a solid school course — to find what's
missing. It deliberately stops short of grade-10 content. The IGCSE 0625 syllabus and grade-10
books are kept as the **target/source** (for prerequisite-mapping and for when he reaches grade 10).

## What's here

```
docs/syllabus/   0625-IGCSE-Physics-2026-2028-syllabus.pdf  ← TARGET: grade-10 syllabus (61 pp)
                 Science_Curriculum_Framework_0893.pdf      ← foundation: Lower Secondary (Stages 7-9)
                 664565-/744626-...-syllabus.pdf            ← A Level 9702 (long-term horizon; you added these)
docs/COVERAGE.md                                            ← our materials mapped to the six 0625 topics + gaps
docs/textbook/   SOURCES.md                                 ← where to get textbooks (free set + Cambridge)
                 ncert-class9-physics/                      ← motion, forces, energy, sound
                 siyavula-natural-sciences/                 ← Gr 9 level: forces, energy, electricity, heat
                 siyavula-physical-sciences/                ← Gr 10: heat, electricity, magnetism, waves
                 ck12-physical-science/                     ← worksheets + quizzes/tests (with answers)
assessment_tool/                                            ← the diagnostic web app (run it; see its README)
past_papers/                                                ← Physics 9702 past-paper library + study tracker (see below)
review/          checklist.md, question-sheet.md            ← the quick Lower-Secondary (foundation) diagnostic
                 study-references.md                        ← where to read each weak topic (file + chapter/section + page)
                 weekly-plan.md                             ← 8-week plan, Strategy A: quick-wins first
                 plan-by-topic.md                           ← 8-week plan, Strategy B: clear the 0s by large topic
                 topics-to-master.pdf                       ← printable checklist of the weak topics (make-topics-pdf.py regenerates it)
                 lesson-notes/                              ← per-lesson notes PDFs (corrected & extended), e.g. Coulomb's law
                 problem-sets/                              ← printable problem sets (LaTeX), e.g. kinematics with a/v/x graphs
README.md        this file
```

**The diagnostic is a comprehensive grade-by-grade test of the physics taught below grade 10.**
The **web tool** (`assessment_tool/`) is the maintained version — **58 questions**: a
maths/practical-skills section plus full **Grade 7**, **Grade 8** and **Grade 9** physics
(mechanics, pressure, thermal, optics, quantitative electricity, waves, atomic basics). The
prerequisites are the foundational items within each grade. Grade-10 IGCSE/A-level content is
intentionally excluded — that's next year's learning. The markdown `review/checklist.md` is an
older, lighter version.

## The plan (~8 weeks, ~2 h/week)

**Week 0 — Diagnose.** Sit with your son and go through `review/checklist.md`, using the
read-aloud prompts in `review/question-sheet.md`. For each item, ask him to explain or solve
it, and mark **0 / 1 / 2**. Fill in the scoring summary at the bottom to see which of the
three areas (Forces & Energy / Light & Sound / Electricity & Magnetism) is weakest. That
ranking sets the order for the weeks that follow.

**Weeks 1–7 — Review loop.** Each week:
1. **Self-study (his week):** he reads the relevant textbook section and does a few Workbook
   exercises for the topics scored 0 or 1. Pick the next-weakest topics first.
2. **Discussion (your ~2 h together):** he explains what he learned; you probe the shaky
   spots, work a couple of problems, and **re-score** those items in the checklist. Watch
   0→1 and 1→2 movement — that's the progress signal.

Spend more weeks on low-scoring areas; skim or skip anything already at 2.

**Week 8 — Re-test & close gaps.** Re-run the full checklist. Anything still at 0/1 gets a
final focused session.

> Rule of thumb: don't try to cover everything evenly. The diagnostic exists so the limited
> 2 h/week goes to what he *doesn't* know, not what he already does.

## Getting the textbook

See `docs/textbook/SOURCES.md`. A **complete free, legal set is already downloaded**:
**NCERT** (motion, forces, energy, sound) + **Siyavula** (heat, electricity, magnetism,
waves) + **CK-12** (worksheets + quizzes/tests with answers). Together they cover the whole
checklist at no cost. If you prefer the actual Cambridge book, buy the **Learner's + Workbook
9** digital edition (the Workbook makes weekly self-study easy). The diagnostic is keyed to
the syllabus, so it works with any of these textbooks.

## Physics 9702 question bank

`past_papers/` is a local question bank and study dashboard for **Cambridge AS & A Level Physics
9702**, using papers from [PapaCambridge](https://pastpapers.papacambridge.com/papers/caie/as-and-a-level-physics-9702).
The backend runs on **Python 3.10+**, with no third-party Python dependencies or frontend
build step. Question extraction and previews use Poppler (`pdftotext`, `pdftoppm`). Scanned
pages use Tesseract OCR when available. These tools are already available on this laptop;
the project-local Tesseract binary and English model are in `past_papers/data/ocr-tools/`.
ImageMagick (`magick` or `convert`) optionally trims reading margins for the
inline cards; without it, cards use the original full-width crop. The full-width crop is always
available in the image viewer and no source PDF is modified.
Compact multiple-choice crops also omit unused blank space beneath the answer choices.

### Start from a fresh clone

The repository includes the application, source catalogue, task-type rules and a portable
snapshot of the saved study progress. Downloaded papers, generated indexes and OCR/image
caches are recreated locally. Allow about 2 GB for the downloaded archive, plus caches;
the initial download and indexing take time and require internet access.

Install Python 3.10+, Poppler and Tesseract with English language data. On Ubuntu/Debian
(including Ubuntu in WSL):

```sh
sudo apt-get update
sudo apt-get install python3 poppler-utils tesseract-ocr tesseract-ocr-eng imagemagick
git clone https://github.com/tarstars/cambridge_9_grade_physics_review.git
cd cambridge_9_grade_physics_review
python3 -m past_papers.setup
python3 -m past_papers.server
```

On macOS, the corresponding Homebrew packages are `python`, `poppler`, `tesseract` and
`imagemagick`. There are no pip/npm dependencies. Setup uses the saved source catalogue,
resumes completed downloads, builds the question index, and restores `past_papers/progress.json`
only if the local progress database is empty. Known unavailable source files are reported in
the application; the remaining library is usable. Re-running setup preserves existing marks.
If the whole `past_papers/data/` directory was copied from another machine, use
`python3 -m past_papers.setup --skip-download` to reuse it.

### Share progress through GitHub

The live app saves to the machine-local SQLite database. Before committing study work,
export its marks, notes, task-type progress and category corrections into the tracked snapshot:

```sh
python3 -m past_papers.progress export
git add past_papers/progress.json
git commit -m "Update study progress"
git push
```

After pulling that snapshot on an already configured machine, restore it explicitly:

```sh
git pull --ff-only
python3 -m past_papers.progress restore
```

Restore replaces matching records with the snapshot and keeps local records absent from it.
It preserves original mark timestamps. This is an explicit checkpoint workflow, not continuous
or simultaneous progress synchronisation: export and push before switching machines; pull
and restore before continuing. If both machines have new work, export both first and resolve
the JSON changes before restoring. The original diagnostic's progress remains tracked separately
in `assessment_tool/results.json`.

### Run the application

From this repository's root, start it with:

```sh
python3 -m past_papers.server
```

Open **http://127.0.0.1:8001**. Use `--port 8002` if the port is busy. Keep the terminal
running; press Ctrl-C to stop. The server binds to this laptop by default and has no login.

The default page is a **visual practice bank organised by specific task types**. For example,
“Identify an SI base quantity”, “Express a derived unit using base units”, “Propagate uncertainty
in a calculated result”, and “Predict a potential divider’s output” are separate types. Syllabus
topics form the higher navigation level. Each type card shows an original example; opening it
shows similar numbered questions from different papers **directly on the page**, with their
answer choices, equations, diagrams and continuation pages. Structured subparts stay together.

Use **My grasp of this approach** to mark a task type independently of its questions. Expand
**Shared approach** for a method hint, and keep your own approach notes. Each question has
its own status, notes and editable type assignments. Type corrections survive re-indexing and
are included in progress exports. Use the format filter for multiple choice or structured/practical
questions, and filter either types or individual questions by progress. Clicking a question image
opens the full-width original crop; source papers and matching marking schemes remain linked.
On desktop, **Compare** shows compact questions side by side; **Reading list** gives each
question the full reading width. Structured and practical questions use the full width.

Specific type assignments use explicit evidence in a question's own text. They are **automatic
suggestions, not a fully manually classified collection**. Unmatched questions remain in an
**Awaiting a task type** queue instead of being forced into a broad topic category. A structured
question can belong to several types because its numbered subparts are kept together.

The previous searchable question catalogue is at **http://127.0.0.1:8001/questions**. It supports
grouping by syllabus topic, source paper, paper type, year or session, and lists source coverage
exceptions. The original whole-document library remains at **http://127.0.0.1:8001/papers**.

Topics follow the 9702 syllabus, with additional categories for practical skills and historical
content. Suggestions use each question's extracted content; they are **automatic suggestions,
not a manually verified topic catalogue**. Multiple-choice distractors are excluded when
recognisable. You can correct or confirm the main topic and add additional topics. Corrections
are stored separately and survive re-indexing. “Topics needing review” finds weak suggestions;
the source coverage dialog lists documents with missing or uncertain question boundaries.

Each question, task type and group can be marked **To process**, **Know how to solve**, **Solved**, or
**Not marked**, with optional notes. **Group marks are independent of question marks**.
The “Mark all … questions” menu updates every question matching that group's current filters,
including results on other pages. Checkboxes let you update a smaller selection.

The original whole-document library is preserved at **http://127.0.0.1:8001/papers**. It includes
yearly exams, topical collections, worked solutions, and reference files from 2002–2026.
Existing paper marks and notes are preserved by the SQLite migration and remain separate
from question progress. A solved paper does not automatically mark its questions solved.

All downloaded PDFs and personal progress live in `past_papers/data/` (ignored by Git).
The backend saves marks transactionally in `progress.sqlite3`; refreshing the page or syncing
papers preserves them. **Export progress** downloads a JSON backup. **Restore** merges that
backup, replacing matching marks and keeping marks absent from the backup. Version 2 backups
include question marks, topic/type corrections and independent task-type marks; version 1 paper backups are still accepted. For a complete
filesystem backup, stop the server and copy the entire data directory, including SQLite files.

The generated question index is `data/tasks.sqlite3`; extracted text/OCR and per-document
question caches are in `data/text-cache/` and `data/task-cache/`. Preview images are cached in
`data/task-images/`. To rebuild after downloading more papers or changing extraction rules:

```sh
python3 -m past_papers.index_tasks
```

Indexing uses four workers, reuses cached extraction/OCR, and replaces the index atomically.
Progress and corrected topics live in a separate database and are never regenerated. Use
`--no-ocr` for a selectable-text-only index, or `--workers 2` to reduce CPU use. Restart an
already-running older server after updating the application.

To update task-type assignments alone, without extracting or OCRing the PDFs again:

```sh
python3 -m past_papers.index_types
```

The rules and shared-approach hints are in `past_papers/methods.py`. Startup refreshes derived
assignments automatically when their rule version changes. Learner type assignments are kept
separately in `progress.sqlite3` and take precedence over regenerated suggestions.

To update the catalogue and download new or missing PDFs:

```sh
python3 -m past_papers.sync
```

Discovery follows only Physics 9702 folders. Downloads use four workers, retry failures,
validate the PDF signature, end marker, and response length, and replace files atomically. Re-running
skips completed PDFs. Downloaded papers work offline; links labelled **online** use the original
source. Source failures appear in the dashboard and `data/download-report.json`; a sync with
failures exits with status 1. Two source links currently return webpages instead of PDFs:
`Physics P1 Topical Past Papers.pdf` and `9702_s03_ms_1 2 3 4 5 6.pdf`. The latter has a
working combined-scheme counterpart, `9702_s03_ms.pdf`, linked to the 2003 June papers.
Two older instruction sheets, `9702_w07_ir_32.pdf` and `9702_w08_ir_31.pdf`, are truncated at
the source. Rejected existing files are preserved with an `.invalid` suffix for inspection;
they are excluded from the offline library.
The source `9702_w07_qp_1.pdf` also has missing font resources on its final pages, preventing
reliable extraction of questions 33–40. Its extracted questions remain available and its
incomplete coverage is flagged in the question bank.
`Physics Topical Questions.pdf` is a mixed scanned compilation whose question boundaries
remain unreliable. It is kept under Full papers and flagged in index coverage; its sections
are excluded from question-level progress. The separately indexed exam papers remain available.
`kinematics unit-2.pdf` contains teaching notes and is also kept in the document library.

Useful options:

```sh
python3 -m past_papers.sync --download-only          # retry downloads using the saved catalogue
python3 -m past_papers.sync --index-only --refresh    # refresh listings without downloading PDFs
python3 -m past_papers.sync --download-only --years 2025 2026
python3 -m past_papers.sync --download-only --workers 8
python3 -m past_papers.index_tasks                  # extract and classify numbered questions
python3 -m past_papers.index_types                  # refresh only the specific task patterns
python3 -m unittest past_papers.test_app past_papers.test_tasks past_papers.test_types past_papers.test_progress -v
```

`--years` limits downloads only; the full catalogue stays available. The commands accept
`--data-dir PATH` and `--catalogue PATH` for an alternate library. The HTTP API exposes
`GET /api/task-types` (specific types, counts, progress and example crops),
`GET /api/tasks?type=si-base-quantity&group=type` (similar questions with inline image URLs),
`GET /api/tasks` (filters and pagination), `GET /api/tasks/<task-id>` (question content and
source links), `GET /task-images/<task-id>/<region-number>.png`, `GET /api/library` (whole
documents), `GET /api/state`, `POST /api/marks`, `POST /api/task-bulk`, `GET /api/export`,
`POST /api/import`, and `GET /files/<document-id>`. A question mark request looks like:

```json
{"updates": [{"kind": "task", "id": "task-id-from-the-index", "status": "solved", "notes": "Review vectors"}]}
```

`kind` accepts `task`, `group`, or `test` (the legacy whole-paper mark); statuses are `unmarked`,
`to_process`, `know_how`, and `solved`. Status and notes may be saved independently. An optional
`topics` object maps task IDs to ordered topic IDs; the first is the main topic. Setting a
task's topics to `null` restores the automatic suggestion. Invalid marks or topic corrections
leave the entire request unchanged. `POST /api/task-bulk` accepts `filters`, `group_id`, and
`status`, and applies to the entire matching group, across pagination. Tests use temporary
databases and do not modify your study progress.

An optional `types` object maps task IDs to lists of specific type IDs. `[]` deliberately
leaves a question unassigned; `null` restores automatic suggestions. Type group IDs use
`tasks:type:<type-id>` and have independent status and notes. Type corrections and marks in
one request are validated together and saved atomically. `/api/tasks` also accepts `paper=1`
for multiple choice or `structured=1` for the other formats. Add `?compact=1` to a task image
URL for the optional narrower reading crop.
