"""Fix missing values, units, and inconsistent formats before the app uses the data."""

from pathlib import Path

import pandas as pd

PROCESSED_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "cars.csv"

NUMERIC_COLUMNS = [
    "year",
    "displacement_cc",
    "horsepower_hp",
    "torque_nm",
    "weight_kg",
    "acceleration_0_100",
]


def load_processed() -> pd.DataFrame:
    """Load the cleaned dataset the app reads."""
    return clean(pd.read_csv(PROCESSED_PATH))


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    """Standardize a raw table into the processed schema."""
    cleaned = frame.copy()
    cleaned.columns = [column.strip().lower().replace(" ", "_") for column in cleaned.columns]

    for column in NUMERIC_COLUMNS:
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    for column in (
        "make",
        "model",
        "generation",
        "engine_code",
        "engine_layout",
        "aspiration",
        "drivetrain",
        "transmission",
        "source_url",
    ):
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].astype("string").str.strip()

    if "drivetrain" in cleaned.columns:
        cleaned["drivetrain"] = cleaned["drivetrain"].str.upper()

    cleaned = cleaned.dropna(subset=["year", "make", "model"])
    return cleaned.reset_index(drop=True)


def save_processed(frame: pd.DataFrame) -> Path:
    """Write the cleaned table to data/processed/cars.csv."""
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean(frame).to_csv(PROCESSED_PATH, index=False)
    return PROCESSED_PATH
