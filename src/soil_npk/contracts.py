"""Stable contracts shared by synthetic and future lab-validated data."""

REQUIRED_REAL_DATA_COLUMNS = (
    "image_path",
    "nitrogen_kg_ha",
    "phosphorus_kg_ha",
    "potassium_kg_ha",
)

OPTIONAL_REAL_DATA_COLUMNS = (
    "sample_id",
    "soil_type",
    "ph",
    "moisture_percent",
    "district",
    "collection_date",
)

TARGET_NAMES = ("nitrogen_kg_ha", "phosphorus_kg_ha", "potassium_kg_ha")
SYNTHETIC_TARGET_NAMES = (*TARGET_NAMES, "moisture_percent")
