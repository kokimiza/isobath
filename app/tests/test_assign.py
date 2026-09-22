import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import combinations

import pytest

from isobath.survey import assign

N_BLOCKS = 10


def bank():
    qs, qid = [], 1
    for _ in range(30):
        qs.append({"id": qid, "kind": "personality", "anchor": True, "block_no": None})
        qid += 1
    for b in range(N_BLOCKS):
        for _ in range(20):
            qs.append({"id": qid, "kind": "personality", "anchor": False, "block_no": b})
            qid += 1
    for _ in range(8):
        qs.append({"id": qid, "kind": "quality", "anchor": False, "block_no": None})
        qid += 1
    return qs


def test_initial_composition():
    a = assign.initial(bank(), random.Random(0))
    purposes = Counter(p for _, p, _ in a.items)
    assert purposes == {"anchor": 30, "block": 60, "quality": 8}
    assert len({q for q, _, _ in a.items}) == len(a.items)
    assert len(a.blocks) == 3
    assert all(prob == 0.3 for _, p, prob in a.items if p == "block")


@pytest.mark.parametrize("missing", ["blocks", "anchors", "quality", "assignment"])
def test_initial_rejects_unfinished_bank(missing):
    questions = bank()
    if missing == "blocks":
        questions = [q for q in questions if q["block_no"] in (None, 0, 1)]
    elif missing == "anchors":
        questions = [q for q in questions if not q["anchor"]]
    elif missing == "quality":
        questions = [q for q in questions if q["kind"] != "quality"]
    else:
        questions.append({"id": 999, "kind": "personality", "anchor": False, "block_no": None})
    with pytest.raises(assign.ItemBankNotReadyError):
        assign.initial(questions, random.Random(0))


def test_block_pairs_are_balanced():
    rng, qs = random.Random(1), bank()
    pairs = Counter()
    n = 12000
    for _ in range(n):
        pairs.update(combinations(assign.initial(qs, rng).blocks, 2))
    expected = n * 3 * 2 / (N_BLOCKS * (N_BLOCKS - 1))  # 1/15 of respondents per block pair
    assert len(pairs) == 45
    assert all(abs(c - expected) / expected < 0.15 for c in pairs.values())


def test_order_is_shuffled():
    a = assign.initial(bank(), random.Random(2))
    assert [p for _, p, _ in a.items[:30]] != ["anchor"] * 30


def test_continuous_mixes_retest_and_unseen_block():
    qs = bank()
    now = datetime(2027, 1, 1, tzinfo=UTC)
    initial = assign.initial(qs, random.Random(3))
    old = {q: now - timedelta(days=20) for q, _, _ in initial.items}
    a = assign.continuous(qs, old, set(initial.blocks), now, random.Random(4))
    purposes = Counter(p for _, p, _ in a.items)
    assert purposes == {"retest": 3, "block": 12}
    assert a.blocks[0] not in initial.blocks


def test_continuous_respects_retest_gap():
    qs = bank()
    now = datetime(2027, 1, 1, tzinfo=UTC)
    recent = {1: now - timedelta(days=3)}
    a = assign.continuous(qs, recent, set(), now, random.Random(5))
    assert all(p != "retest" for _, p, _ in a.items)


def test_continuous_retest_only_when_all_blocks_seen():
    qs = bank()
    now = datetime(2027, 1, 1, tzinfo=UTC)
    old = {q["id"]: now - timedelta(days=30) for q in qs if q["kind"] == "personality"}
    a = assign.continuous(qs, old, set(range(N_BLOCKS)), now, random.Random(6))
    assert Counter(p for _, p, _ in a.items) == {"retest": 15}
