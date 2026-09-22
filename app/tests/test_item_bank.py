import random
from collections import Counter
from pathlib import Path

from isobath import items
from isobath.survey import assign

ITEMS = Path(__file__).resolve().parents[1] / "items"
DRAFT = ITEMS / "drafts" / "items-0.2.csv"


def test_production_loader_does_not_include_unapproved_draft():
    production = items.read([ITEMS])
    assert {q["item_set_version"] for q in production} == {"0.1"}
    assert len(production) == 10
    assert items.check_ready(production, "0.1") == 1


def test_draft_structure_and_allocation():
    draft = items.read([DRAFT])
    assert len(draft) == 238
    assert len({q["id"] for q in draft}) == len(draft)
    assert len({q["code"] for q in draft}) == len(draft)
    assert not {q["id"] for q in draft} & {q["id"] for q in items.read([ITEMS])}
    anchors = [q for q in draft if q["anchor"]]
    assert len(anchors) == 30
    assert {q["domain"] for q in anchors} == {f"D{i:02}" for i in range(1, 17)}
    assert Counter(q["block_no"] for q in draft if q["block_no"] is not None) == dict.fromkeys(
        range(10), 20
    )
    for b in range(10):
        assert len({q["domain"] for q in draft if q["block_no"] == b}) == 16
    for d in {q["domain"] for q in anchors}:
        domain = [q for q in draft if q["domain"] == d]
        assert sum(q["keyed"] == -1 for q in domain) * 2 == len(domain)
    for q in draft:
        if q["quality_rule"] and q["quality_rule"]["type"] == "repeat":
            assert q["quality_rule"]["of"] in {a["code"] for a in anchors}
    for seed in range(120):
        assignment = assign.initial(draft, random.Random(seed))
        assert len(assignment.items) == len({q for q, _, _ in assignment.items}) == 98
        assert Counter(p for _, p, _ in assignment.items) == {
            "anchor": 30,
            "block": 60,
            "quality": 8,
        }


def test_check_source_never_opens_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("source checks must not connect to a database")

    monkeypatch.setattr(items.psycopg, "connect", forbidden)
    assert items.main(["--check-source", "--version", "0.2", str(DRAFT)]) == 0
    assert items.main(["--check-source", "--version", "0.1", str(ITEMS)]) == 1
