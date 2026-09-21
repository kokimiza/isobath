from isobath.survey.quality import compute


def row(code, value, ms=3000, purpose="anchor", rule=None):
    return {
        "code": code,
        "value": value,
        "response_ms": ms,
        "purpose": purpose,
        "quality_rule": rule,
    }


def test_clean_session():
    rows = [row(f"A{i}", 1 + i % 5) for i in range(20)]
    assert compute(rows) == ({}, 1.0)


def test_flags():
    rows = [row(f"A{i}", 3, ms=400) for i in range(20)]
    rows.append(row("Q1", 1, purpose="quality", rule={"type": "attention", "expect": 4}))
    rows.append(row("Q2", 5, purpose="quality", rule={"type": "repeat", "of": "A0"}))
    rows[0]["value"] = 1
    flags, reliability = compute(rows)
    assert set(flags) == {"speeding", "straightline", "attention_fail", "inconsistent"}
    assert reliability == 0.0
