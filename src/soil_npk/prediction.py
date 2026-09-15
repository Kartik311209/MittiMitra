"""Prediction service layer used by both FastAPI and Streamlit."""

from __future__ import annotations

from pathlib import Path

from .features import extract_features
from .model import NPKRegressor
from .recommendations import build_recommendation


def predict_image(image_path: str | Path, model_path: str | Path = "artifacts/npk_baseline.npz") -> dict[str, object]:
    features = extract_features(image_path)
    model = NPKRegressor.load(model_path)
    prediction = model.predict(features[None, :])[0]
    values = {name: max(0.0, float(value)) for name, value in zip(model.target_names, prediction)}
    n, p, k = (values[name] for name in ("nitrogen_kg_ha", "phosphorus_kg_ha", "potassium_kg_ha"))
    moisture = values.get("moisture_percent")
    return {
        "nitrogen_kg_ha": round(n, 2),
        "phosphorus_kg_ha": round(p, 2),
        "potassium_kg_ha": round(k, 2),
        "moisture_percent": round(moisture, 2) if moisture is not None else None,
        "recommendation": build_recommendation(n, p, k, moisture),
        "estimate_principle": {
            "model": "Multi-output ridge regression trained on synthetic soil images.",
            "signals": {
                "average_rgb": [round(float(value * 255), 1) for value in features[:3]],
                "texture_variation": round(float(features[-2:].mean()), 4),
            },
            "explanation": "The image is resized and its RGB colour distribution, brightness and texture variation are compared with patterns learned from the synthetic training set.",
        },
        "model_note": "Prediction produced by a model trained only on synthetic soil images.",
    }
