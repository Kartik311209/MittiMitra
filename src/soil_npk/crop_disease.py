"""Crop-disease baseline training and inference.

This module intentionally keeps the first implementation transparent and
dependency-light.  It learns visual similarity to labelled image folders; it
is not a clinical or agronomic diagnosis engine and never returns pesticide
dosage.  A model is only available after a reviewed, labelled dataset has
been placed locally and trained by the project owner.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_MODEL_PATH = Path(os.getenv("CROP_DISEASE_MODEL_PATH", "artifacts/crop_disease_baseline.npz"))
MIN_SAMPLES_PER_CLASS = 3


def _image_features(image_path: str | Path) -> np.ndarray:
    """Extract colour, vegetation and texture signals from a crop photo."""
    try:
        with Image.open(image_path) as source:
            rgb_image = source.convert("RGB").resize((128, 128))
            hsv_image = rgb_image.convert("HSV")
            rgb = np.asarray(rgb_image, dtype=np.float32) / 255.0
            hsv = np.asarray(hsv_image, dtype=np.float32) / 255.0
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError("The uploaded file is not a readable crop image.") from error

    pixels = rgb.reshape(-1, 3)
    means = pixels.mean(axis=0)
    deviations = pixels.std(axis=0)
    percentiles = np.percentile(pixels, [10, 50, 90], axis=0).reshape(-1)
    rgb_histograms = np.concatenate(
        [np.histogram(rgb[..., channel], bins=12, range=(0.0, 1.0), density=True)[0] for channel in range(3)]
    )
    saturation_value_histograms = np.concatenate(
        [np.histogram(hsv[..., channel], bins=8, range=(0.0, 1.0), density=True)[0] for channel in (1, 2)]
    )
    red, green, blue = (rgb[..., channel] for channel in range(3))
    vegetation_fraction = np.array([
        np.mean((green > red * 1.04) & (green > blue * 1.04)),
        np.mean((red > green * 1.06) & (red > blue * 1.02)),
    ])
    edge_density = np.array([
        np.abs(np.diff(rgb, axis=0)).mean(),
        np.abs(np.diff(rgb, axis=1)).mean(),
    ])
    return np.concatenate(
        [means, deviations, percentiles, rgb_histograms, saturation_value_histograms, vegetation_fraction, edge_density]
    ).astype(np.float32)


def _class_folders(dataset_dir: Path) -> list[Path]:
    """Accept either a class-folder root or a common dataset/train root."""
    root = dataset_dir / "train" if (dataset_dir / "train").is_dir() else dataset_dir
    return sorted(folder for folder in root.iterdir() if folder.is_dir()) if root.is_dir() else []


def _display_label(raw_label: str) -> str:
    return raw_label.replace("___", " - ").replace("_", " ").strip()


def _label_parts(raw_label: str) -> tuple[str, str, bool]:
    parts = raw_label.replace("___", "|", 1).split("|", 1)
    crop = parts[0].replace("_", " ").strip()
    finding = (parts[1] if len(parts) > 1 else raw_label).replace("_", " ").strip()
    healthy = "healthy" in raw_label.lower()
    return crop, finding, healthy


def train_crop_disease_classifier(
    dataset_dir: str | Path,
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> dict[str, object]:
    """Train a nearest-centroid baseline from ``class_name/image.jpg`` folders."""
    dataset_path = Path(dataset_dir)
    class_folders = _class_folders(dataset_path)
    if not class_folders:
        raise ValueError(
            "No class folders found. Put labelled images in data/crop_disease/raw/<crop-and-disease-class>/"
        )

    feature_rows: list[np.ndarray] = []
    labels: list[str] = []
    skipped_files = 0
    class_counts: dict[str, int] = {}
    for folder in class_folders:
        image_paths = [path for path in sorted(folder.rglob("*")) if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES]
        if len(image_paths) < MIN_SAMPLES_PER_CLASS:
            continue
        class_features: list[np.ndarray] = []
        for image_path in image_paths:
            try:
                class_features.append(_image_features(image_path))
            except ValueError:
                skipped_files += 1
        if len(class_features) >= MIN_SAMPLES_PER_CLASS:
            feature_rows.extend(class_features)
            labels.extend([folder.name] * len(class_features))
            class_counts[folder.name] = len(class_features)

    if len(class_counts) < 2:
        raise ValueError(
            f"At least two readable classes with {MIN_SAMPLES_PER_CLASS} images each are required."
        )

    features = np.vstack(feature_rows)
    feature_mean = features.mean(axis=0)
    feature_scale = np.maximum(features.std(axis=0), 1e-6)
    scaled_features = (features - feature_mean) / feature_scale
    class_names = np.array(sorted(class_counts), dtype=str)
    centroids = np.vstack([scaled_features[np.array(labels) == class_name].mean(axis=0) for class_name in class_names])

    destination = Path(model_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        model_format=np.array(["mittimitra-crop-disease-centroid-v1"]),
        created_at=np.array([datetime.now(UTC).isoformat()]),
        class_names=class_names,
        class_counts=np.array([class_counts[str(name)] for name in class_names], dtype=np.int32),
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        centroids=centroids,
    )
    return {
        "model_path": str(destination),
        "class_count": int(len(class_names)),
        "image_count": int(len(labels)),
        "class_counts": class_counts,
        "skipped_files": skipped_files,
    }


def crop_disease_model_status(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, object]:
    """Return safe model metadata without exposing training images or paths to users."""
    path = Path(model_path)
    if not path.exists():
        return {
            "ready": False,
            "message": "Crop-disease model is not trained yet. Add a reviewed labelled dataset and train it first.",
        }
    try:
        with np.load(path, allow_pickle=False) as saved:
            class_names = [str(value) for value in saved["class_names"]]
            class_counts = [int(value) for value in saved["class_counts"]]
            created_at = str(saved["created_at"][0])
    except (OSError, KeyError, ValueError) as error:
        return {"ready": False, "message": f"Crop-disease model could not be loaded: {error}"}
    return {
        "ready": True,
        "class_count": len(class_names),
        "image_count": sum(class_counts),
        "trained_at": created_at,
        "model_type": "labelled-image similarity baseline",
    }


def predict_crop_disease(
    image_path: str | Path,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    minimum_confidence: int | None = None,
) -> dict[str, object]:
    """Return a confidence-aware preliminary image classification."""
    status = crop_disease_model_status(model_path)
    if not status.get("ready"):
        raise RuntimeError(str(status["message"]))
    with np.load(Path(model_path), allow_pickle=False) as saved:
        class_names = np.asarray(saved["class_names"], dtype=str)
        feature_mean = np.asarray(saved["feature_mean"], dtype=np.float32)
        feature_scale = np.asarray(saved["feature_scale"], dtype=np.float32)
        centroids = np.asarray(saved["centroids"], dtype=np.float32)
    features = _image_features(image_path)
    distances = np.linalg.norm((features - feature_mean) / feature_scale - centroids, axis=1)
    distance_scale = max(float(np.median(distances)), 1e-6)
    scores = -distances / distance_scale
    probabilities = np.exp(scores - scores.max())
    probabilities /= probabilities.sum()
    index = int(np.argmax(probabilities))
    raw_label = str(class_names[index])
    crop, finding, healthy = _label_parts(raw_label)
    confidence = round(float(probabilities[index] * 100), 1)
    confidence_floor = minimum_confidence or int(os.getenv("CROP_DISEASE_MIN_CONFIDENCE", "65"))
    needs_review = confidence < confidence_floor or not healthy
    next_step = (
        "No disease is confirmed by this photo. Keep monitoring the crop and repeat the photo in good daylight if symptoms change."
        if healthy
        else "This is only an early visual indication. Do not choose a pesticide or dosage from this result alone; show the crop and photo to a KVK, agriculture officer, or qualified agronomist."
    )
    return {
        "label": _display_label(raw_label),
        "crop": crop,
        "finding": finding,
        "healthy": healthy,
        "confidence_percent": confidence,
        "needs_expert_review": needs_review,
        "minimum_confidence_percent": confidence_floor,
        "next_step": next_step,
        "model_note": "Preliminary visual classification from a locally trained labelled-image baseline; it is not a confirmed diagnosis.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MittiMitra's labelled crop-disease image baseline.")
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/crop_disease/raw"))
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    summary = train_crop_disease_classifier(args.dataset_dir, args.model_path)
    print(f"Saved crop-disease model to {summary['model_path']}")
    print(f"Classes: {summary['class_count']} | labelled images: {summary['image_count']} | skipped: {summary['skipped_files']}")


if __name__ == "__main__":
    main()
