"""statistics.md §0.3: prespecified study design and profile matching."""

import numpy as np

from pipeline.study import nested_design, profile_comparison


def test_nested_design_keeps_all_person_ids_out_of_other_roles():
    runs = nested_design(90, [5, 10, 20], np.random.default_rng(2))
    assert set(runs[0]["train"]).issubset(runs[1]["train"])
    assert set(runs[1]["train"]).issubset(runs[2]["train"])
    for run in runs:
        assert not set(run["train"]) & set(run["replicate"])
        assert not set(run["train"]) & set(run["holdout"])
        assert not set(run["replicate"]) & set(run["holdout"])


def test_profile_matching_reports_missing_mass_instead_of_forcing_matches():
    a, b = np.array([[0.0, 0.0], [5.0, 5.0]]), np.array([[5.0, 5.0]])
    distance, unmatched = profile_comparison(a, b, np.array([0.3, 0.7]), np.ones(1))
    assert distance == 0
    assert unmatched == 0.3
