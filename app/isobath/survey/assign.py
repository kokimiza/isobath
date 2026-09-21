"""Question assignment, Phase 1 planned missing design (design §5.5, D-8).

Pure functions: questions in, (question_id, purpose, selection_prob) out.
Assignment never looks at the respondent's own answer values, so missingness stays MCAR.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

INITIAL_RULE = "bibd-uniform@1"
CONTINUOUS_RULE = "continuous-retest@1"
BLOCKS_PER_PERSON = 3
CONTINUOUS_SIZE = 15
RETEST_PER_SESSION = 3  # Q-09 initial value
RETEST_MIN_GAP = timedelta(days=14)  # FR-CON-03


@dataclass
class Assignment:
    rule: str
    blocks: list[int]
    items: list[tuple[int, str, float]]  # (question_id, purpose, selection_prob), in display order


def _blocks(questions: list[dict]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for q in questions:
        if q["kind"] == "personality" and q["block_no"] is not None:
            out.setdefault(q["block_no"], []).append(q["id"])
    return out


def initial(questions: list[dict], rng: random.Random) -> Assignment:
    blocks = _blocks(questions)
    if len(blocks) < BLOCKS_PER_PERSON:
        raise ValueError("not enough blocks")
    # uniform over all C(n,3) combinations -> equal pairwise co-response in expectation
    chosen = sorted(rng.sample(sorted(blocks), BLOCKS_PER_PERSON))
    p_block = BLOCKS_PER_PERSON / len(blocks)
    items = [
        (q["id"], "anchor", 1.0) for q in questions if q["kind"] == "personality" and q["anchor"]
    ]
    items += [(qid, "block", p_block) for b in chosen for qid in blocks[b]]
    items += [(q["id"], "quality", 1.0) for q in questions if q["kind"] == "quality"]
    rng.shuffle(items)  # FR-SUR-10
    return Assignment(INITIAL_RULE, chosen, items)


def continuous(
    questions: list[dict],
    last_answered: dict[int, datetime],
    seen_blocks: set[int],
    now: datetime,
    rng: random.Random,
) -> Assignment:
    """(a) items from one unseen block + (b) retest of items answered >= 14 days ago (FR-CON-02)."""
    personality = {q["id"] for q in questions if q["kind"] == "personality"}
    candidates = sorted(
        q for q, t in last_answered.items() if q in personality and now - t >= RETEST_MIN_GAP
    )
    unseen = sorted(set(_blocks(questions)) - seen_blocks)

    n_retest = min(RETEST_PER_SESSION if unseen else CONTINUOUS_SIZE, len(candidates))
    items = [(q, "retest", n_retest / len(candidates)) for q in rng.sample(candidates, n_retest)]
    chosen: list[int] = []
    if unseen:
        b = rng.choice(unseen)
        chosen = [b]
        pool = [q for q in _blocks(questions)[b] if q not in last_answered]
        m = min(CONTINUOUS_SIZE - n_retest, len(pool))
        p = (1 / len(unseen)) * (m / len(pool)) if pool else 1.0
        items += [(q, "block", p) for q in rng.sample(pool, m)]
    rng.shuffle(items)
    return Assignment(CONTINUOUS_RULE, chosen, items)
