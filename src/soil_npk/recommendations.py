"""Conservative, explainable demo recommendations—not agronomic prescriptions."""

from __future__ import annotations


def level(value: float, low: float, high: float) -> str:
    if value < low:
        return "Low"
    if value > high:
        return "High"
    return "Medium"


def moisture_band(moisture: float | None) -> str:
    if moisture is None:
        return "Not estimated"
    if moisture < 12:
        return "Dry"
    if moisture > 23:
        return "Moist"
    return "Balanced"


def crop_suggestions(moisture: float | None) -> list[str]:
    if moisture is None:
        return ["Use local weather, season and lab data to shortlist crops."]
    if moisture < 12:
        return ["Millet / bajra", "Chickpea", "Mustard"]
    if moisture > 23:
        return ["Paddy", "Fodder crops", "Sugarcane (where climate and irrigation allow)"]
    return ["Wheat", "Maize", "Groundnut"]


def build_recommendation(nitrogen: float, phosphorus: float, potassium: float, moisture: float | None = None) -> dict[str, object]:
    levels = {
        "nitrogen": level(nitrogen, 45, 100),
        "phosphorus": level(phosphorus, 25, 55),
        "potassium": level(potassium, 110, 190),
    }
    actions = []
    if levels["nitrogen"] == "Low":
        actions.append("Nitrogen appears low: confirm through a lab test before applying a nitrogen source.")
    if levels["phosphorus"] == "Low":
        actions.append("Phosphorus appears low: seek local agronomy guidance on a phosphorus source and dose.")
    if levels["potassium"] == "Low":
        actions.append("Potassium appears low: confirm with a soil lab before changing potassium application.")
    if not actions:
        actions.append("No obvious low nutrient flag in this prototype estimate; validate with a soil lab report.")
    return {
        "levels": levels,
        "water_status": moisture_band(moisture),
        "crop_suggestions": crop_suggestions(moisture),
        "actions": actions,
        "disclaimer": "Synthetic-model prototype. Do not use as the sole basis for fertilizer dosage or crop choice.",
    }
