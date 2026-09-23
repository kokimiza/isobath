"""Research-only cut regression. Never imported by the API or position inference.

statistics.md §12.1 defines the estimand, proper priors and missing-data policy.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from scipy.linalg import solve_triangular

from .diagnostics import diagnose

TERMS = ["intercept", "age_per_decade_from_50", "male_vs_female", "neither_vs_female"]
GENDERS = {"male", "female", "neither", "prefer_not_to_say"}


def reference_date(cutoff: datetime) -> date:
    if cutoff.tzinfo is None:
        raise ValueError("cutoff must include a time zone")
    return cutoff.astimezone(ZoneInfo("Asia/Tokyo")).date().replace(day=1) - timedelta(days=1)


def age_at(year: int, month: int, reference: date) -> int:
    if type(year) is not int or type(month) is not int:
        raise ValueError("birth year/month must be integers")
    try:
        birth_month = date(year, month, 1)
    except ValueError:
        raise ValueError("invalid birth year/month") from None
    if birth_month > reference:
        raise ValueError("birth month is later than the age reference date")
    return reference.year - year - (reference.month < month)


def covariates(users, rows, consented, reference):
    """Align only current v2 grants to already consent/tombstone-filtered users."""
    result = np.full((len(users), len(TERMS)), np.nan)
    index = {str(uid): i for i, uid in enumerate(users)}
    allowed = set(map(str, consented))
    seen = set()
    for row in rows:
        uid = str(row["pseudo_id"])
        if uid not in index or uid not in allowed:
            continue
        if uid in seen:
            raise ValueError("duplicate research demographics")
        seen.add(uid)
        gender = row["gender"]
        if gender not in GENDERS:
            raise ValueError("invalid self-reported gender")
        age = age_at(row["birth_year"], row["birth_month"], reference)
        if gender != "prefer_not_to_say":
            result[index[uid]] = (1, (age - 50) / 10, gender == "male", gender == "neither")
    return result


class Regression:
    def __init__(self, design):
        design = np.asarray(design, dtype=float)
        if design.ndim != 2 or design.shape[1] != len(TERMS) or np.isinf(design).any():
            raise ValueError("invalid research design")
        self.included = np.isfinite(design).all(axis=1)
        self.x = design[self.included]
        self.count = len(self.x)
        self.rank = int(np.linalg.matrix_rank(self.x)) if self.count else 0
        self.prior_precision = np.diag([0.01, 1.0, 1.0, 1.0])
        precision = self.prior_precision + self.x.T @ self.x
        self.cholesky = np.linalg.cholesky(precision)

    def draw(self, factors, rng):
        if not self.count:
            raise ValueError("no complete cases")
        y = factors[self.included]
        information = self.x.T @ y
        mean = solve_triangular(
            self.cholesky.T,
            solve_triangular(self.cholesky, information, lower=True),
        )
        residual = y - self.x @ mean
        rate = (
            1
            + (np.sum(residual**2, axis=0) + np.sum(mean * (self.prior_precision @ mean), axis=0))
            / 2
        )
        variance = rate / rng.gamma(2 + self.count / 2, size=y.shape[1])
        noise = solve_triangular(self.cholesky.T, rng.normal(size=mean.shape))
        return mean + noise * np.sqrt(variance)


def report(data, result):
    if data.research_covariates is None:
        return {"status": "no_demographic_data", "public": False}
    regression = Regression(data.research_covariates)
    output = {
        "status": "estimated" if regression.count else "no_complete_cases",
        "public": False,
        "inference": "cut_auxiliary_regression",
        "age_reference_date": data.age_reference_date,
        "included": regression.count,
        "excluded": len(data.user_ids) - regression.count,
        "design_rank": regression.rank,
        "rank_deficient": regression.rank < len(TERMS),
        "terms": TERMS,
        "prior": {"variance_shape": 2, "variance_scale": 1, "coefficient_scale": [100, 1, 1, 1]},
        "limitations": [
            "complete_case_selection",
            "associational_not_causal",
            "not_for_publication",
        ],
    }
    if regression.count:
        draws = result.demographic_draws
        output["mean"] = draws.mean(axis=(0, 1)).tolist()
        output["equal_tail_95"] = np.quantile(draws, [0.025, 0.975], axis=(0, 1)).tolist()
        output["diagnostics"] = diagnose({"demographic_beta": draws})
    return output
