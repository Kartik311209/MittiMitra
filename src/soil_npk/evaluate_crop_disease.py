"""Evaluate a local crop-photo candidate on a held-out folder split."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from soil_npk.crop_disease import IMAGE_SUFFIXES, _image_features, _label_parts


def evaluate(model_path: Path, test_dir: Path) -> dict[str, object]:
    with np.load(model_path, allow_pickle=False) as saved:
        class_names = [str(value) for value in saved["class_names"]]
        mean = np.asarray(saved["feature_mean"], dtype=np.float32)
        scale = np.asarray(saved["feature_scale"], dtype=np.float32)
        centroids = np.asarray(saved["centroids"], dtype=np.float32)

    class_total: Counter[str] = Counter()
    class_correct: Counter[str] = Counter()
    crop_total: Counter[str] = Counter()
    crop_correct: Counter[str] = Counter()
    confusion: Counter[tuple[str, str]] = Counter()
    unreadable = 0

    for folder in sorted(test_dir.iterdir()):
        if not folder.is_dir():
            continue
        true_label = folder.name
        true_crop = _label_parts(true_label)[0]
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                features = _image_features(path)
            except ValueError:
                unreadable += 1
                continue
            distances = np.linalg.norm((features - mean) / scale - centroids, axis=1)
            predicted = class_names[int(np.argmin(distances))]
            predicted_crop = _label_parts(predicted)[0]
            class_total[true_label] += 1
            crop_total[true_crop] += 1
            class_correct[true_label] += predicted == true_label
            crop_correct[true_crop] += predicted_crop == true_crop
            if predicted != true_label:
                confusion[(true_label, predicted)] += 1

    total = sum(class_total.values())
    if total == 0:
        raise ValueError(f"No readable test images found under {test_dir}")
    per_class = {
        label: {"tested": count, "correct": class_correct[label], "recall": round(class_correct[label] / count, 4)}
        for label, count in sorted(class_total.items())
    }
    per_crop = {
        crop: {"tested": count, "correct": crop_correct[crop], "accuracy": round(crop_correct[crop] / count, 4)}
        for crop, count in sorted(crop_total.items())
    }
    return {
        "warning": "These splits are not independent farms/regions. Do not interpret this result as all-India field accuracy.",
        "test_images": total,
        "unreadable": unreadable,
        "class_top1_accuracy": round(sum(class_correct.values()) / total, 4),
        "macro_class_recall": round(sum(item["recall"] for item in per_class.values()) / len(per_class), 4),
        "crop_top1_accuracy": round(sum(crop_correct.values()) / total, 4),
        "per_crop": per_crop,
        "per_class": per_class,
        "top_confusions": [
            {"true": true, "predicted": predicted, "count": count}
            for (true, predicted), count in confusion.most_common(15)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a local crop-photo candidate model.")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--test-dir", type=Path, required=True)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()
    report = evaluate(args.model_path, args.test_dir)
    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Images: {report['test_images']}")
    print(f"Class accuracy: {report['class_top1_accuracy']:.1%}")
    print(f"Macro class recall: {report['macro_class_recall']:.1%}")
    print(f"Crop accuracy: {report['crop_top1_accuracy']:.1%}")
    if args.report_path is not None:
        print(f"Report: {args.report_path}")


if __name__ == "__main__":
    main()
