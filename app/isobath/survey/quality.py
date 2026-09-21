"""Online response-quality flags (ST-QLT-01). Flags never change the position estimate."""

import statistics

SPEEDING_MEDIAN_MS = 1000  # tune with pilot data
STRAIGHTLINE_SHARE = 0.9
STRAIGHTLINE_MIN_ITEMS = 10
INCONSISTENT_GAP = 3
FLAG_PENALTY = 0.25


def compute(rows: list[dict]) -> tuple[dict, float]:
    """rows: answers of one session with question metadata:
    {question_id, code, value, response_ms, purpose, quality_rule}."""
    flags: dict[str, bool] = {}

    times = [r["response_ms"] for r in rows if r["response_ms"] is not None]
    if times and statistics.median(times) < SPEEDING_MEDIAN_MS:
        flags["speeding"] = True

    anchors = [r["value"] for r in rows if r["purpose"] == "anchor"]
    if len(anchors) >= STRAIGHTLINE_MIN_ITEMS:
        top = max(anchors.count(v) for v in set(anchors))
        if top / len(anchors) >= STRAIGHTLINE_SHARE:
            flags["straightline"] = True

    by_code = {r["code"]: r["value"] for r in rows}
    for r in rows:
        rule = r.get("quality_rule") or {}
        if rule.get("type") == "attention" and r["value"] != rule.get("expect"):
            flags["attention_fail"] = True
        if (
            rule.get("type") == "repeat"
            and rule.get("of") in by_code
            and abs(r["value"] - by_code[rule["of"]]) >= INCONSISTENT_GAP
        ):
            flags["inconsistent"] = True

    data_quality_score = max(0.0, 1.0 - FLAG_PENALTY * len(flags))
    return flags, data_quality_score
