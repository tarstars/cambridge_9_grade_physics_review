"""Pure data logic for the assessment tool: load/save/validate/rollup.

Kept free of any HTTP concerns so it can be unit-tested directly.
"""
import json
import os
import tempfile

VALID_MARKS = {0, 1, 2, None}


def _questions_iter(questions):
    """Yield (topic, subtopic, question) for every question in the bank."""
    for topic in questions.get("topics", []):
        for subtopic in topic.get("subtopics", []):
            for question in subtopic.get("questions", []):
                yield topic, subtopic, question


def valid_question_ids(questions):
    """Set of every question id defined in the question bank."""
    return {q["id"] for _, _, q in _questions_iter(questions)}


def topic_of_question(questions):
    """Map each question id to the id of the topic it belongs to."""
    return {q["id"]: topic["id"] for topic, _, q in _questions_iter(questions)}


def validate_results(data, questions):
    """Return a list of human-readable error strings ([] means valid)."""
    errors = []
    known = valid_question_ids(questions)
    for session in data.get("sessions", []):
        sid = session.get("id", "?")
        for qid, answer in session.get("answers", {}).items():
            if qid not in known:
                errors.append(f"session {sid}: unknown question id {qid}")
                continue
            mark = answer.get("mark")
            if mark not in VALID_MARKS:
                errors.append(f"session {sid}: question {qid} has invalid mark {mark!r} (must be 0, 1, 2 or null)")
            comment = answer.get("comment", "")
            if not isinstance(comment, str):
                errors.append(f"session {sid}: question {qid} comment must be text")
    return errors


def load_results(path):
    """Load results.json, or an empty document if the file is absent."""
    if not os.path.exists(path):
        return {"sessions": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_results(path, data):
    """Write results atomically (temp file + replace) so a crash can't corrupt it."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def rollup(data, questions, session_id):
    """Per-topic score summary for one session.

    Returns {topic_id: {sum, max, answered, count}} where sum is the total of
    awarded marks, max is 2*count, answered counts non-null marks.
    """
    topic_ids = [t["id"] for t in questions.get("topics", [])]
    q_to_topic = topic_of_question(questions)
    counts = {tid: 0 for tid in topic_ids}
    for tid in q_to_topic.values():
        counts[tid] += 1

    result = {tid: {"sum": 0, "max": counts[tid] * 2, "answered": 0, "count": counts[tid]}
              for tid in topic_ids}

    session = next((s for s in data.get("sessions", []) if s.get("id") == session_id), None)
    if session is None:
        return result

    for qid, answer in session.get("answers", {}).items():
        mark = answer.get("mark")
        if qid not in q_to_topic or mark is None:
            continue
        tid = q_to_topic[qid]
        result[tid]["sum"] += mark
        result[tid]["answered"] += 1
    return result
