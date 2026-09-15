"""Create a reproducible synthetic soil-image dataset for an MVP only.

The generated visual relationships are intentionally learnable.  They are not
evidence that RGB camera images can accurately measure real soil nutrients.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


SOIL_BASES = {
    "alluvial": np.array([137, 103, 69]),
    "black": np.array([63, 55, 46]),
    "red": np.array([145, 67, 43]),
    "sandy": np.array([178, 145, 95]),
}


def _make_soil_image(rng: np.random.Generator, n: float, p: float, k: float, soil_type: str, moisture: float) -> Image.Image:
    """Make one textured soil tile with controlled nutrient-linked cues."""
    height = width = 128
    base = SOIL_BASES[soil_type].astype(float)
    # Deliberately synthetic signal: organic darkness (N), warm/red cast (P),
    # and mineral lightness (K). Real-world models must learn from lab labels.
    base += np.array([-0.22 * n, 0.28 * p, 0.20 * k])
    base -= (moisture - 15) * np.array([0.55, 0.48, 0.35])
    noise = rng.normal(0, 18, size=(height, width, 1))
    grain = rng.normal(0, 8, size=(height, width, 3))
    pixels = np.clip(base + noise + grain, 0, 255).astype(np.uint8)

    # Sparse particles form visual texture independent of the labels.
    for _ in range(rng.integers(35, 90)):
        y, x = rng.integers(0, height), rng.integers(0, width)
        radius = rng.integers(1, 5)
        color = np.clip(base + rng.normal(0, 35, 3), 0, 255).astype(np.uint8)
        yy, xx = np.ogrid[:height, :width]
        mask = (yy - y) ** 2 + (xx - x) ** 2 <= radius**2
        pixels[mask] = color

    image = Image.fromarray(pixels, "RGB")
    image = ImageEnhance.Brightness(image).enhance(float(rng.uniform(0.78, 1.22)))
    image = ImageEnhance.Contrast(image).enhance(float(rng.uniform(0.78, 1.24)))
    if rng.random() < 0.28:
        image = image.filter(ImageFilter.GaussianBlur(radius=float(rng.uniform(0.2, 0.9))))
    return image


def generate_dataset(output_dir: Path, samples: int, seed: int = 42) -> Path:
    """Write images and a CSV compatible with future real-data training."""
    rng = np.random.default_rng(seed)
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    soil_types = tuple(SOIL_BASES)

    for index in range(samples):
        soil_type = str(rng.choice(soil_types))
        nitrogen = float(rng.uniform(15, 140))
        phosphorus = float(rng.uniform(8, 85))
        potassium = float(rng.uniform(45, 260))
        moisture = float(rng.uniform(5, 32))
        ph = float(rng.uniform(5.2, 8.3))
        filename = f"soil_{index:05d}.png"
        _make_soil_image(rng, nitrogen, phosphorus, potassium, soil_type, moisture).save(image_dir / filename)
        records.append({
            "sample_id": f"SYN-{index:05d}",
            "image_path": str(Path("images") / filename),
            "nitrogen_kg_ha": round(nitrogen, 2),
            "phosphorus_kg_ha": round(phosphorus, 2),
            "potassium_kg_ha": round(potassium, 2),
            "soil_type": soil_type,
            "ph": round(ph, 2),
            "moisture_percent": round(moisture, 2),
            "data_source": "synthetic",
        })

    csv_path = output_dir / "labels.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic soil NPK training data.")
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--samples", type=int, default=800)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    path = generate_dataset(args.output, args.samples, args.seed)
    print(f"Created {args.samples} synthetic samples: {path}")


if __name__ == "__main__":
    main()

