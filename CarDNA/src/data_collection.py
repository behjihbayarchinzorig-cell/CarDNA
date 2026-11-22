"""
Data collection for CarDNA.

Reads every CSV and JSON file in data/raw/, maps its column names onto the
CarDNA schema, hands the rows to data_cleaning, and writes the result to
data/processed/cardna.csv.

Run it from the project folder:
    python -m src.data_collection
    python -m src.data_collection --check-nhtsa     (optional name check, needs internet)

Adding a source
---------------
1. Put the file in data/raw/ (CSV, or JSON as a list of records).
2. Every row needs a source_url and source_name. Either include those columns,
   or add a small file next to it called <filename>.meta.json:
       {"source_name": "cardata.wiki", "source_url": "https://cardata.wiki/",
        "column_map": {"hp": "horsepower_hp", "kerb_weight": "weight_kg"}}
3. Run the command above and read the printed report.

Nothing here invents data. Rows missing a value keep it empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

from src import data_cleaning

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_PATH = ROOT / "data" / "processed" / "cardna.csv"

# Column names other sources commonly use -> the CarDNA column.
# Only unit-explicit names are listed, because a bare "torque" could be Nm or lb-ft.
COLUMN_ALIASES = {
    "make": ["make", "brand", "manufacturer"],
    "model": ["model", "model_name"],
    "generation": ["generation", "gen", "chassis", "chassis_code"],
    "trim": ["trim", "variant", "grade", "version"],
    "market": ["market", "region"],
    "production_year": ["production_year", "year", "model_year", "year_from", "start_year"],
    "engine_code": ["engine_code", "engine_model"],
    "engine_layout": ["engine_layout", "layout", "engine_configuration"],
    "cylinders": ["cylinders", "cylinder_count"],
    "displacement_cc": ["displacement_cc", "capacity_cc", "engine_size_cc", "displacement_cm3"],
    "displacement_l": ["displacement_l", "displacement_litres", "displacement_liters"],
    "aspiration": ["aspiration", "induction", "charger"],
    "horsepower_hp": ["horsepower_hp", "horsepower", "hp", "power_hp"],
    "horsepower_ps": ["horsepower_ps", "power_ps", "ps"],
    "horsepower_kw": ["horsepower_kw", "power_kw", "kw"],
    "horsepower_rpm": ["horsepower_rpm", "power_rpm", "hp_rpm"],
    "torque_nm": ["torque_nm"],
    "torque_lbft": ["torque_lbft", "torque_lb_ft"],
    "torque_rpm": ["torque_rpm"],
    "drivetrain": ["drivetrain", "drive", "drive_type"],
    "transmission": ["transmission", "gearbox"],
    "gear_count": ["gear_count", "gears"],
    "weight_kg": ["weight_kg", "curb_weight_kg", "kerb_weight_kg"],
    "weight_lb": ["weight_lb", "curb_weight_lb"],
    "acceleration_0_100": ["acceleration_0_100", "zero_to_100", "0_100_kmh"],
    "top_speed_kmh": ["top_speed_kmh", "max_speed_kmh"],
    "top_speed_mph": ["top_speed_mph"],
    "source_url": ["source_url", "url"],
    "source_name": ["source_name", "source"],
    "verification_status": ["verification_status"],
}


def read_table(path: Path) -> pd.DataFrame:
    """Read a CSV, or a JSON file holding a list of records (or a dict containing one)."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        data = lists[0] if lists else [data]
    return pd.json_normalize(data)


def apply_mapping(df: pd.DataFrame, column_map: dict | None = None) -> pd.DataFrame:
    """Rename source columns to CarDNA names: explicit column_map first, then known aliases."""
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    rename: dict[str, str] = {}
    for source_col, target in (column_map or {}).items():
        if source_col.lower() in out.columns:
            rename[source_col.lower()] = target
    for target, aliases in COLUMN_ALIASES.items():
        if target in out.columns or target in rename.values():
            continue
        for alias in aliases:
            if alias in out.columns and alias not in rename:
                rename[alias] = target
                break
    return out.rename(columns=rename)


def unmapped_columns(df: pd.DataFrame) -> list[str]:
    known = set(data_cleaning.SCHEMA) | set(data_cleaning.UNIT_INPUT_COLUMNS)
    return [c for c in df.columns if c not in known]


def load_raw_folder(raw_dir: Path = RAW_DIR, report: list[str] | None = None) -> list[pd.DataFrame]:
    """Load every raw file. Returns one DataFrame per file, with source columns filled in."""
    frames = []
    for path in sorted(raw_dir.rglob("*")):
        if path.suffix.lower() not in {".csv", ".json"} or path.name.endswith(".meta.json") or path.name.startswith("_"):
            continue
        meta_path = path.with_name(path.name + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        df = apply_mapping(read_table(path), meta.get("column_map"))
        for col in ("source_name", "source_url"):
            if col not in df.columns and meta.get(col):
                df[col] = meta[col]
        if "source_name" not in df.columns:
            df["source_name"] = path.name
        if report is not None:
            report.append(f"{path.name}: {len(df)} rows; unmapped columns ignored: {unmapped_columns(df) or 'none'}")
        frames.append(df)
    return frames


def run_pipeline(raw_dir: Path = RAW_DIR, out_path: Path = PROCESSED_PATH,
                 report: list[str] | None = None) -> pd.DataFrame:
    """Raw files -> cleaned, merged dataset saved to data/processed/cardna.csv."""
    frames = load_raw_folder(raw_dir, report)
    if not frames:
        return pd.DataFrame(columns=data_cleaning.OUTPUT_COLUMNS)
    dataset = data_cleaning.build_dataset(frames)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(out_path, index=False)
    return dataset


# --------------------------------------------------------------------------
# Optional: NHTSA vPIC name check
# --------------------------------------------------------------------------
NHTSA_MODELS_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}?format=json"


def fetch_nhtsa_models(make: str, timeout: int = 15) -> set[str]:
    """
    Model names NHTSA's public vPIC API lists for a make. vPIC covers vehicles sold in
    the United States and has no horsepower/torque/weight per configuration, so it is
    only useful for checking that make and model names exist, not for specifications.
    """
    response = requests.get(NHTSA_MODELS_URL.format(make=quote(make)), timeout=timeout)
    response.raise_for_status()
    return {item["Model_Name"].lower() for item in response.json().get("Results", [])}


def check_models_against_nhtsa(dataset: pd.DataFrame) -> pd.DataFrame:
    """Return make/model pairs that NHTSA does not list (expected for JDM-only models)."""
    rows = []
    for make, group in dataset.dropna(subset=["make", "model"]).groupby("make"):
        try:
            known = fetch_nhtsa_models(make)
        except (requests.RequestException, ValueError) as error:
            rows.append({"make": make, "model": "(lookup failed)", "note": str(error)})
            continue
        for model in sorted(group["model"].unique()):
            if model.lower() not in known:
                rows.append({"make": make, "model": model, "note": "not listed by NHTSA vPIC"})
    return pd.DataFrame(rows, columns=["make", "model", "note"])


def main() -> None:
    report: list[str] = []
    dataset = run_pipeline(report=report)
    print("\n".join(report) or f"No raw files found in {RAW_DIR}")
    if dataset.empty:
        return
    print(f"\nSaved {len(dataset)} configurations to {PROCESSED_PATH.relative_to(ROOT)}")
    print(dataset["verification_status"].value_counts().to_string())
    if "--check-nhtsa" in sys.argv:
        print("\nNHTSA name check:")
        print(check_models_against_nhtsa(dataset).to_string(index=False))


if __name__ == "__main__":
    main()
