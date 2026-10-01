"""Prepare locally downloaded Indian field-photo datasets for evaluation.

This is a data preparation utility, not a claim that the crop-disease model is
clinically or agronomically validated. Source archives are never modified.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, UnidentifiedImageError


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIDE = 512


def _split_for(key: str) -> str:
    """Deterministic split for datasets without a published split."""
    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "val" if bucket < 85 else "test"


def _store_image(source: bytes | Path, destination: Path, box: tuple[float, ...] | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stream = io.BytesIO(source) if isinstance(source, bytes) else source
    with Image.open(stream) as image:
        image = image.convert("RGB")
        if box is not None:
            cx, cy, width, height = box
            margin = 1.15
            left = max(0, round((cx - width * margin / 2) * image.width))
            top = max(0, round((cy - height * margin / 2) * image.height))
            right = min(image.width, round((cx + width * margin / 2) * image.width))
            bottom = min(image.height, round((cy + height * margin / 2) * image.height))
            if right <= left or bottom <= top:
                raise ValueError("Invalid YOLO bounding box")
            image = image.crop((left, top, right, bottom))
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
        image.save(destination, "JPEG", quality=88, optimize=True)


def _destination(output: Path, split: str, label: str, source_name: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return output / split / label / f"{source_name}-{digest}.jpg"


def _record(
    counts: dict[str, Counter[str]],
    source_name: str,
    split: str,
    label: str,
) -> None:
    counts[source_name][f"{split}/{label}"] += 1


def _multicrop_label(raw_name: str) -> str:
    """Convert Roboflow names to the crop/finding format used by the app."""
    crop, separator, finding = raw_name.partition("_")
    if not separator or not finding:
        raise ValueError(f"Multi-Crop class has no crop prefix: {raw_name}")
    normalized_finding = re.sub(r"[\s_]+", "_", finding).strip("_").lower()
    return f"{crop.capitalize()}___{normalized_finding}"


def _prepare_multicrop(source: Path, output: Path, counts: dict[str, Counter[str]], skipped: Counter[str]) -> None:
    with ZipFile(source) as archive:
        entries = {entry.filename: entry for entry in archive.infolist() if not entry.is_dir()}
        yaml_path = next(name for name in entries if name.endswith("/data.yaml"))
        yaml_text = archive.read(yaml_path).decode("utf-8-sig")
        names_line = next(line for line in yaml_text.splitlines() if line.startswith("names:"))
        names = ast.literal_eval(names_line.partition(":")[2].strip())
        for label_path in sorted(name for name in entries if "/labels/" in name and name.endswith(".txt")):
            parts = label_path.split("/")
            split = next((part for part in parts if part in {"train", "valid", "test"}), None)
            if split is None:
                continue
            split = "val" if split == "valid" else split
            annotations = []
            for line in archive.read(label_path).decode("utf-8-sig").splitlines():
                fields = line.split()
                if len(fields) != 5:
                    continue
                try:
                    class_id = int(fields[0])
                    box = tuple(float(value) for value in fields[1:])
                except ValueError:
                    continue
                if 0 <= class_id < len(names):
                    annotations.append((class_id, box))
            distinct_classes = {class_id for class_id, _ in annotations}
            if len(distinct_classes) != 1:
                skipped["multicrop_empty_or_multiclass"] += 1
                continue
            image_path = label_path.replace("/labels/", "/images/").removesuffix(".txt") + ".jpg"
            if image_path not in entries:
                skipped["multicrop_missing_image"] += 1
                continue
            class_id = next(iter(distinct_classes))
            # Use the largest annotated region when an image contains repeated
            # boxes of the same class. This keeps the output single-label.
            box = max((box for _, box in annotations), key=lambda item: item[2] * item[3])
            label = _multicrop_label(names[class_id])
            destination = _destination(output, split, label, "multicrop", image_path)
            try:
                _store_image(archive.read(image_path), destination, box)
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                skipped["multicrop_unreadable"] += 1
                continue
            _record(counts, "multicrop", split, label)


def _prepare_wheat(source: Path, output: Path, counts: dict[str, Counter[str]], skipped: Counter[str]) -> None:
    for archive_name, finding in (("WheatLeafRust.zip", "leaf_rust"), ("Ndeficient.zip", "nitrogen_deficient")):
        with ZipFile(source / archive_name) as archive:
            for entry in archive.infolist():
                if entry.is_dir() or Path(entry.filename).suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                parts = entry.filename.split("/")
                if len(parts) != 4 or parts[1] not in {"train", "val", "test"}:
                    continue
                split = parts[1]
                label = "Wheat___healthy" if parts[2] == "control" else f"Wheat___{finding}"
                destination = _destination(output, split, label, archive_name, entry.filename)
                try:
                    _store_image(archive.read(entry), destination)
                except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                    skipped["wheat_unreadable"] += 1
                    continue
                _record(counts, "wheat", split, label)


def _prepare_extracted(
    root: Path,
    class_map: dict[str, str],
    source_name: str,
    output: Path,
    counts: dict[str, Counter[str]],
    skipped: Counter[str],
) -> None:
    if not root.is_dir():
        raise FileNotFoundError(f"Extracted {source_name} directory not found: {root}")
    for folder_name, label in class_map.items():
        folder = root / folder_name
        if not folder.is_dir():
            raise FileNotFoundError(f"Expected {source_name} class folder not found: {folder}")
        for image_path in sorted(folder.rglob("*")):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            key = f"{source_name}/{image_path.relative_to(root).as_posix()}"
            split = _split_for(key)
            destination = _destination(output, split, label, source_name, key)
            try:
                _store_image(image_path, destination)
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                skipped[f"{source_name}_unreadable"] += 1
                continue
            _record(counts, source_name, split, label)


def _prepare_soynet(source: Path, output: Path, counts: dict[str, Counter[str]], skipped: Counter[str]) -> None:
    with ZipFile(source) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or Path(entry.filename).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            # Deliberately skip the bundled RAR and all resized/greyscale
            # duplicates. Only the original raw field photos are used.
            if "/Raw_SoyNet_Data/" not in entry.filename:
                continue
            path = entry.filename.lower()
            if "/healthy pic/" in path:
                label = "Soybean___healthy"
            elif "/disease_pic/" in path or "/mobile click/" in path:
                label = "Soybean___diseased_unspecified"
            else:
                skipped["soynet_unknown_folder"] += 1
                continue
            split = _split_for(entry.filename)
            destination = _destination(output, split, label, "soynet", entry.filename)
            try:
                _store_image(archive.read(entry), destination)
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                skipped["soynet_unreadable"] += 1
                continue
            _record(counts, "soynet", split, label)


def prepare(source: Path, staging: Path, output: Path) -> dict[str, object]:
    expected = (
        "Multi-Crop Disease Dataset.zip",
        "Rice Leaf Disease Image Samples.zip",
        "Sugarcane Leaf Disease Dataset.zip",
        "th422bg4yd-1.zip",
    )
    missing = [name for name in expected if not (source / name).is_file()]
    soy_files = list(source.glob("SoyNet*.zip"))
    if missing or len(soy_files) != 1:
        raise FileNotFoundError(f"Missing archives: {missing}; SoyNet ZIP count: {len(soy_files)}")

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    skipped: Counter[str] = Counter()
    _prepare_multicrop(source / expected[0], output, counts, skipped)
    print("Prepared Multi-Crop", flush=True)
    _prepare_extracted(
        staging / "rice" / "Rice Leaf Disease Images",
        {"Bacterialblight": "Rice___bacterial_blight", "Blast": "Rice___blast", "Brownspot": "Rice___brown_spot", "Tungro": "Rice___tungro"},
        "rice", output, counts, skipped,
    )
    print("Prepared rice", flush=True)
    _prepare_extracted(
        staging / "sugarcane" / "Sugarcane Leaf Disease Dataset",
        {"Healthy": "Sugarcane___healthy", "Mosaic": "Sugarcane___mosaic", "RedRot": "Sugarcane___red_rot", "Rust": "Sugarcane___rust", "Yellow": "Sugarcane___yellow_disease"},
        "sugarcane", output, counts, skipped,
    )
    print("Prepared sugarcane", flush=True)
    _prepare_wheat(staging, output, counts, skipped)
    print("Prepared wheat", flush=True)
    _prepare_soynet(soy_files[0], output, counts, skipped)
    print("Prepared SoyNet originals", flush=True)

    manifest: dict[str, object] = {
        "purpose": "Research/evaluation only; not a validated all-India disease diagnosis model.",
        "image_size_max_side": MAX_IMAGE_SIDE,
        "source_counts": {source_name: dict(sorted(value.items())) for source_name, value in sorted(counts.items())},
        "skipped": dict(sorted(skipped.items())),
        "limitations": [
            "Public sources cover selected crops and regions, not all Indian agro-climatic zones.",
            "Multi-Crop Mendeley landing page says CC BY 4.0 but bundled Roboflow data.yaml says Private; resolve before redistribution or production use.",
            "Rice source has no healthy class; SoyNet has only healthy versus unspecified disease.",
            "Random deterministic splits for rice, sugarcane and SoyNet may contain similar photos across splits; field/farm-held-out evaluation is still required.",
            "Wheat nitrogen deficiency is nutrient stress, not a disease.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def migrate_multicrop_labels(output: Path) -> int:
    """Rename folders made by the early importer without touching images."""
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_counts = manifest["source_counts"]["multicrop"]
    moves: list[tuple[Path, Path]] = []
    updated_counts: dict[str, int] = {}
    root = output.resolve()
    for key, count in old_counts.items():
        split, old_label = key.split("/", 1)
        if "___" in old_label:
            updated_counts[key] = count
            continue
        new_label = _multicrop_label(old_label)
        source = output / split / old_label
        destination = output / split / new_label
        if not source.is_dir() or destination.exists():
            raise RuntimeError(f"Cannot safely rename {source} to {destination}")
        if not source.resolve().is_relative_to(root) or not destination.resolve().is_relative_to(root):
            raise RuntimeError("Prepared label migration escaped its output folder")
        moves.append((source, destination))
        updated_counts[f"{split}/{new_label}"] = count
    for source, destination in moves:
        source.rename(destination)
    manifest["source_counts"]["multicrop"] = dict(sorted(updated_counts.items()))
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(moves)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare five locally downloaded crop-photo datasets.")
    parser.add_argument("--source-dir", type=Path, default=Path("data/crop_disease/sources"))
    parser.add_argument("--staging-dir", type=Path, default=Path("data/crop_disease/staging"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/crop_disease/prepared"))
    parser.add_argument("--migrate-labels", action="store_true", help="Fix labels created by the early importer")
    args = parser.parse_args()
    if args.migrate_labels:
        print(f"Renamed {migrate_multicrop_labels(args.output_dir)} prepared class folders")
        return
    manifest = prepare(args.source_dir, args.staging_dir, args.output_dir)
    for source_name, class_counts in manifest["source_counts"].items():
        print(f"{source_name}: {sum(class_counts.values())} images")
    print(f"Manifest: {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
