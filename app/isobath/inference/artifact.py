"""Chart model artifacts: npz + json, no pickle (design D-5). Shared with the pipeline."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

STAGES = ["UNCHARTED", "PRE-CHART", "PROTO", "SEED", "CHART"]
ARRAYS = ["mu", "scale", "Lambda", "psi", "P", "c"]
GMM_ARRAYS = ["gmm_pi", "gmm_mean", "gmm_cov"]


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
        if self.stage not in STAGES:
            raise ValueError(f"unknown stage {self.stage}")
        self.index = {q: i for i, q in enumerate(self.question_ids)}

    def at_least(self, stage: str) -> bool:
        return STAGES.index(self.stage) >= STAGES.index(stage)

    @property
    def can_place(self) -> bool:
        return self.at_least("PROTO") and "Lambda" in self.arrays

    @property
    def has_regions(self) -> bool:
        return self.at_least("SEED") and "gmm_pi" in self.arrays


def save(model: Model, root: Path) -> Path:
    d = root / f"chart-{model.version}"
    d.mkdir(parents=True, exist_ok=True)
    if model.arrays:
        np.savez(d / "model.npz", **model.arrays)
    meta = {
        **model.meta,
        "version": model.version,
        "stage": model.stage,
        "item_set_version": model.item_set_version,
        "question_ids": model.question_ids,
        "regions": model.regions,
    }
    (d / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return d


def load(root: Path, version: str | None = None) -> Model:
    version = version or (root / "CURRENT").read_text("utf-8").strip()
    d = root / f"chart-{version}"
    meta = json.loads((d / "metadata.json").read_text("utf-8"))
    arrays = {}
    if (d / "model.npz").exists():
        with np.load(d / "model.npz", allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        missing = [k for k in ARRAYS if k not in arrays]
        if missing:
            raise ValueError(f"artifact {version} missing arrays {missing}")
    return Model(
        version=meta.pop("version"),
        stage=meta.pop("stage"),
        item_set_version=meta.pop("item_set_version"),
        question_ids=meta.pop("question_ids", []),
        regions=meta.pop("regions", []),
        arrays=arrays,
        meta=meta,
    )
