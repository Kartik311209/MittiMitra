"""Small dependency-free multi-output ridge regressor for the MVP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class NPKRegressor:
    feature_mean: np.ndarray | None = None
    feature_std: np.ndarray | None = None
    weights: np.ndarray | None = None
    target_names: tuple[str, ...] = ()

    def fit(self, features: np.ndarray, targets: np.ndarray, target_names: tuple[str, ...], alpha: float = 0.3) -> "NPKRegressor":
        self.feature_mean = features.mean(axis=0)
        self.feature_std = features.std(axis=0) + 1e-8
        x = (features - self.feature_mean) / self.feature_std
        x = np.c_[np.ones(len(x)), x]
        penalty = np.eye(x.shape[1]) * alpha
        penalty[0, 0] = 0.0
        self.weights = np.linalg.solve(x.T @ x + penalty, x.T @ targets)
        self.target_names = target_names
        return self

    def predict(self, features: np.ndarray) -> np.ndarray:
        if self.weights is None or self.feature_mean is None or self.feature_std is None:
            raise RuntimeError("Model has not been trained.")
        x = (features - self.feature_mean) / self.feature_std
        return np.c_[np.ones(len(x)), x] @ self.weights

    def save(self, path: str | Path) -> None:
        if self.weights is None or self.feature_mean is None or self.feature_std is None:
            raise RuntimeError("Model has not been trained.")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, feature_mean=self.feature_mean, feature_std=self.feature_std, weights=self.weights, target_names=np.array(self.target_names))

    @classmethod
    def load(cls, path: str | Path) -> "NPKRegressor":
        saved = np.load(path)
        names = tuple(str(value) for value in saved["target_names"]) if "target_names" in saved.files else ("nitrogen_kg_ha", "phosphorus_kg_ha", "potassium_kg_ha")
        return cls(saved["feature_mean"], saved["feature_std"], saved["weights"], names)
