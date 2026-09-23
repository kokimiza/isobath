"""statistics.md §5.2: inherit identities only through shared current participants."""

import numpy as np

from pipeline.lineage import inherit_lineage


def test_jaccard_lineage_survives_label_permutation_and_records_new_region():
    regions = [
        {"index": 0, "lineage_id": "new-1"},
        {"index": 1, "lineage_id": "new-2"},
        {"index": 2, "lineage_id": "new-3"},
    ]
    old = [{"index": 0, "lineage_id": "A"}, {"index": 1, "lineage_id": "B"}]
    updated, events = inherit_lineage(
        ["a", "b", "c", "d", "e"],
        np.array([1, 1, 0, 0, 2]),
        regions,
        ["a", "b", "c", "d", "revoked"],
        np.array([0, 0, 1, 1, 0]),
        old,
    )
    assert updated[0]["lineage_id"] == "B"
    assert updated[1]["lineage_id"] == "A"
    assert updated[2]["lineage_id"] == "new-3"
    assert any(event["kind"] == "new" for event in events)
