"""Retrieve car data from APIs or permitted sources and store it raw."""

from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def fetch_json(url: str, timeout: int = 30) -> dict | list:
    """Download JSON from a permitted API endpoint."""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def save_raw(frame: pd.DataFrame, filename: str) -> Path:
    """Write an untouched download into data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / filename
    frame.to_csv(path, index=False)
    return path
