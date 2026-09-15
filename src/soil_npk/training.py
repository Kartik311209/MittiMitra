"""Train and evaluate the baseline while preserving the real-data CSV contract."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from .contracts import SYNTHETIC_TARGET_NAMES, TARGET_NAMES
from .features import extract_features
from .model import NPKRegressor


def load_labeled_images(labels_csv: Path) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    rows = list(csv.DictReader(labels_csv.open(encoding="utf-8")))
    if not rows:
        raise ValueError("The labels CSV is empty.")
    missing = [name for name in ("image_path", *TARGET_NAMES) if name not in rows[0]]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    root = labels_csv.parent
    features = np.vstack([extract_features(root / row["image_path"]) for row in rows])
    target_names = SYNTHETIC_TARGET_NAMES if "moisture_percent" in rows[0] else TARGET_NAMES
    targets = np.array([[float(row[name]) for name in target_names] for row in rows], dtype=np.float32)
    return features, targets, target_names


def train(labels_csv: Path, model_path: Path, seed: int = 42) -> dict[str, float]:
    features, targets, target_names = load_labeled_images(labels_csv)
    rng = np.random.default_rng(seed)
    indices = rng.permutation(len(features))
    split = max(1, int(len(indices) * 0.8))
    train_idx, test_idx = indices[:split], indices[split:]
    model = NPKRegressor().fit(features[train_idx], targets[train_idx], target_names)
    model.save(model_path)
    if len(test_idx) == 0:
        return {f"mae_{name}": float("nan") for name in target_names}
    errors = np.abs(model.predict(features[test_idx]) - targets[test_idx]).mean(axis=0)
    return {f"mae_{key}": round(float(value), 2) for key, value in zip(target_names, errors)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the synthetic NPK baseline.")
    parser.add_argument("--labels", type=Path, default=Path("data/synthetic/labels.csv"))
    parser.add_argument("--model", type=Path, default=Path("artifacts/npk_baseline.npz"))
    args = parser.parse_args()
    metrics = train(args.labels, args.model)
    print(f"Saved model to {args.model}")
    print("Holdout MAE by target:", metrics)


if __name__ == "__main__":
    main()
