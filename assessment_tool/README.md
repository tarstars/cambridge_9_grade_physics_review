# Assessment tool

A tiny local web app for running the 0/1/2 physics diagnostic and storing the marks in this
repo. No dependencies — just Python 3.

## Run it

```bash
cd assessment_tool
python3 server.py            # then open http://127.0.0.1:8000
```

Score each question **0 / 1 / 2**, add a comment for anything to revisit, and click **Save**.
Clicking a selected mark again clears it. Your marks are written to `results.json` — commit
that file to keep the history.

## Sessions (Week 0 → Week 8)

Use the **Session** dropdown to switch between assessments, and **+ New** to start another
(e.g. the Week-8 re-test). Each session stores its own marks, so you can compare progress over
time. The app starts with one session, "Week 0 — diagnostic".

## Files

| File | What it is |
|---|---|
| `server.py` | stdlib HTTP server (serves the UI + JSON API) |
| `store.py` | load / save / validate / rollup logic (unit-tested) |
| `test_store.py` | tests for `store.py` — run `python3 -m unittest` |
| `questions.json` | the question bank: topics → subtopics → questions (37 items) |
| `results.json` | your marks & comments — **this is the data that's saved** |
| `index.html` | the single-page UI (vanilla JS) |

## API (if you want it)

- `GET /api/questions` — the question bank
- `GET /api/results` — saved marks
- `POST /api/results` — save marks (validates 0/1/2 and known question ids; rejects bad data without overwriting)
- `GET /api/summary` — per-topic score rollup for each session

## Tests

```bash
cd assessment_tool
python3 -m unittest -v
```

## Note on data

`results.json` is the source of truth and lives in the repo. The question bank mirrors
`review/checklist.md`; if you change one, update the other.
