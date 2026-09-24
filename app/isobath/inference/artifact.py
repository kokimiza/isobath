"""Validated, immutable numeric artifacts. No pickle or executable deserialization (§7)."""

import json
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

STAGES = ["COLLECTING", "PRIOR", "CHARTED"]
ALIGNMENT_UNMATCHED, UNSEEN, PADDING = -1, -2, -3
ARRAYS = (
    "draws_tau",
    "draws_Lambda",
    "draws_w",
    "draws_m",
    "draws_Sigma",
    "draws_valid",
    "draws_occupied",
    "draws_K",
    "draws_T",
    "draws_component_to_region",
    "draws_core_z",
    "center_b",
    "scale_a",
    "P",
    "c",
    "T_support",
    "T_post",
    "K_support",
    "K_post",
)
MAX_ARCHIVE_BYTES = 2_000_000_000


def validate_version(version):
    if not isinstance(version, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", version
    ):
        raise ValueError("invalid artifact version")


@dataclass
class Model:
    version: str
    stage: str
    item_set_version: str
    meta: dict = field(default_factory=dict)
    question_ids: list[int] = field(default_factory=list)
    arrays: dict[str, np.ndarray] = field(default_factory=dict)
    regions: list[dict] = field(default_factory=list)

    def __post_init__(self):
        validate_version(self.version)
        # Read-only migration of the original, parameter-free collecting artifact.
        if self.stage == "UNCHARTED" and not self.arrays:
            self.stage = "COLLECTING"
        if self.stage not in STAGES:
            raise ValueError("unsupported artifact stage/schema; refit using statistics.md")
        self.index = {q: i for i, q in enumerate(self.question_ids)}
        if any(isinstance(q, bool) or not isinstance(q, int) or q < 1 for q in self.question_ids):
            raise ValueError("question identifiers must be positive integers")
        if len(self.index) != len(self.question_ids):
            raise ValueError("duplicate question identifiers")

    @property
    def can_place(self):
        return self.stage in ("PRIOR", "CHARTED") and bool(self.arrays)

    @property
    def has_regions(self):
        diagnostic = self.meta.get("diagnostics", {})
        return (
            self.stage == "CHARTED"
            and len(self.regions) >= 2
            and diagnostic.get("p_multiple", 0) > 0.5
        )


def validate(model):
    a = model.arrays
    if model.stage == "COLLECTING":
        if a:
            raise ValueError("collecting artifact cannot contain parameters")
        return
    missing = set(ARRAYS) - a.keys()
    if missing:
        raise ValueError(f"artifact missing arrays: {sorted(missing)}")
    if model.meta.get("schema_version") != 3 or model.meta.get("inference_mode") != "cut":
        raise ValueError("unsupported schema or inference mode")
    for value in a.values():
        if value.dtype.kind not in "biuf" or not np.isfinite(value).all():
            raise ValueError("arrays must be finite numeric values")
    if a["draws_Lambda"].ndim != 3 or a["draws_w"].ndim != 2:
        raise ValueError("invalid array dimensions")
    s, j, d = a["draws_Lambda"].shape
    c = a["draws_w"].shape[1]
    shapes = {
        "draws_tau": (s, j, 4),
        "draws_w": (s, c),
        "draws_m": (s, c, d),
        "draws_Sigma": (s, c, d, d),
        "draws_valid": (s, c),
        "draws_occupied": (s, c),
        "draws_K": (s,),
        "draws_T": (s,),
        "draws_component_to_region": (s, c),
        "center_b": (s, d),
        "scale_a": (s, d),
        "P": (2, d),
        "c": (2,),
    }
    if (
        not s
        or not c
        or j != len(model.question_ids)
        or any(a[k].shape != v for k, v in shapes.items())
    ):
        raise ValueError("artifact shape mismatch")
    valid, occupied = a["draws_valid"], a["draws_occupied"]
    if valid.dtype.kind != "b" or occupied.dtype.kind != "b" or np.any(occupied & ~valid):
        raise ValueError("invalid component masks")
    if not np.array_equal(valid.sum(axis=1), a["draws_K"]) or not np.array_equal(
        occupied.sum(axis=1), a["draws_T"]
    ):
        raise ValueError("component counts disagree")
    if (
        np.any(a["draws_T"] < (0 if model.stage == "PRIOR" else 1))
        or np.any(np.diff(a["draws_tau"], axis=-1) <= 0)
        or np.any(a["scale_a"] <= 0)
    ):
        raise ValueError("invalid thresholds/counts/scales")
    if model.stage == "PRIOR" and (
        model.regions or np.any(a["draws_T"] != 0) or model.meta.get("n_observers") != 0
    ):
        raise ValueError("prior artifact cannot claim observed regions or participants")
    weights = a["draws_w"]
    if (
        np.any(weights < 0)
        or not np.allclose(weights.sum(axis=1), 1.0, atol=1e-10, rtol=0)
        or np.any(weights[~valid] != 0)
    ):
        raise ValueError("invalid mixture weights")
    covariance = a["draws_Sigma"][valid]
    if not np.allclose(covariance, covariance.swapaxes(-1, -2)):
        raise ValueError("non-symmetric covariance")
    try:
        np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("non-positive covariance") from exc
    mapping = a["draws_component_to_region"]
    region_ids = [r["index"] for r in model.regions]
    if (
        mapping.dtype.kind not in "iu"
        or not np.isin(mapping[occupied], [ALIGNMENT_UNMATCHED, *region_ids]).all()
    ):
        raise ValueError("invalid component mapping")
    if np.any(mapping[valid & ~occupied] != UNSEEN) or np.any(mapping[~valid] != PADDING):
        raise ValueError("unseen/padding mapping mismatch")
    for name in ("K", "T"):
        support, probability = a[f"{name}_support"], a[f"{name}_post"]
        if (
            support.ndim != 1
            or support.shape != probability.shape
            or np.any(np.diff(support) <= 0)
            or np.any(probability < 0)
            or not np.isclose(probability.sum(), 1)
        ):
            raise ValueError("invalid count distribution")
    if a["draws_core_z"].ndim != 2 or a["draws_core_z"].shape[0] != s:
        raise ValueError("invalid core membership shape")
    core = a["draws_core_z"]
    if core.dtype.kind not in "iu" or np.any(core < 0) or np.any(core >= a["draws_K"][:, None]):
        raise ValueError("invalid core component identifiers")
    expected = np.zeros((2, d))
    expected[0, 0], expected[1, min(3, d - 1)] = 1.0, 1.0
    if not np.array_equal(a["P"], expected) or np.any(a["c"] != 0):
        raise ValueError("projection does not match the fixed domain reference")


def save(model: Model, root: Path) -> Path:
    validate_version(model.version)
    validate(model)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"chart-{model.version}"
    if dest.exists():
        raise FileExistsError("artifact versions are immutable")
    with tempfile.TemporaryDirectory(prefix=".artifact-", dir=root) as work:
        draft = Path(work) / "chart"
        draft.mkdir()
        if model.arrays:
            np.savez(draft / "model.npz", **model.arrays)
        meta = {
            **model.meta,
            "version": model.version,
            "stage": model.stage,
            "item_set_version": model.item_set_version,
            "question_ids": model.question_ids,
            "regions": model.regions,
        }
        (draft / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        draft.rename(dest)
    return dest


def load(root: Path, version: str | None = None, *, metadata_only=False) -> Model:
    version = version or (root / "CURRENT").read_text(encoding="utf-8").strip()
    validate_version(version)
    directory = root / f"chart-{version}"
    if directory.resolve().parent != root.resolve():
        raise ValueError("artifact path escapes model root")
    metadata_path = directory / "metadata.json"
    if metadata_path.stat().st_size > 16_000_000:
        raise ValueError("metadata exceeds resource limit")
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    if meta.get("version") != version:
        raise ValueError("artifact version mismatch")
    arrays = {}
    if not metadata_only and (directory / "model.npz").exists():
        with zipfile.ZipFile(directory / "model.npz") as archive:
            if sum(v.file_size for v in archive.infolist()) > MAX_ARCHIVE_BYTES:
                raise ValueError("artifact exceeds resource limit")
        with np.load(directory / "model.npz", allow_pickle=False) as values:
            arrays = {k: values[k] for k in values.files}
    model = Model(
        version=meta.pop("version"),
        stage=meta.pop("stage"),
        item_set_version=meta.pop("item_set_version"),
        question_ids=meta.pop("question_ids", []),
        regions=meta.pop("regions", []),
        arrays=arrays,
        meta=meta,
    )
    if not metadata_only:
        validate(model)
    return model
