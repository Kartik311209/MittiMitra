"""Image feature extraction shared by training and prediction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def extract_features(image_path: str | Path) -> np.ndarray:
    image = Image.open(image_path).convert("RGB").resize((96, 96))
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    channels = pixels.reshape(-1, 3)
    means = channels.mean(axis=0)
    stds = channels.std(axis=0)
    percentiles = np.percentile(channels, [10, 50, 90], axis=0).reshape(-1)
    # Adjacent-pixel variation captures coarse soil texture.
    texture = np.array([
        np.abs(np.diff(pixels, axis=0)).mean(),
        np.abs(np.diff(pixels, axis=1)).mean(),
    ])
    return np.concatenate([means, stds, percentiles, texture]).astype(np.float32)

