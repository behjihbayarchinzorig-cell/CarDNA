"""
CarDNA - data collection.

What this module does
  1. Downloads the public gor3a/vehicle-makes-models engines.csv (ODbL licence).
  2. Selects a small STARTER set of Japanese performance vehicles from it.
  3. Imports any other CSV/JSON dataset you have the right to use, mapping its
     columns onto the CarDNA schema (with unit conversion).

Why only one downloaded source?  See README "Data sources". In short:
  * cardata.wiki  - free CSV (CC BY 4.0) but could NOT be reached from the build
                    sandbox, so it was not used. Import it yourself with
                    `--import-file` (see README).
  * autoseeker.eu - open data, but only ~281 *current* EU models (mostly EVs). Not
                    relevant to 1980-2010 Japanese performance cars.
  * NHTSA vPIC    - make/model/VIN-decode API; not a source of hp/torque/weight
                    for classic cars, and was unreachable from the sandbox.
  * We never scrape websites.

Usage
    python -m src.data_collection --download
    python -m src.data_collection --import-file my.csv --source-name "My source" \
        --source-url "https://..." --column-map map.json --units units.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src.data_cleaning import (
    ALL_COLUMNS, GOR3A_NAME, GOR3A_URL, IMPORT_DIR, RAW_DIR, SCHEMA_COLUMNS,
    convert_units, map_gor3a_to_schema,
)

GOR3A_RAW_URL = ("https://raw.githubusercontent.com/gor3a/vehicle-makes-models/"
                 "main/data/csv/engines.csv")
GOR3A_RAW_PATH = RAW_DIR / "engines.csv"
GOR3A_IMPORT_PATH = IMPORT_DIR / "gor3a_starter.csv"

# --------------------------------------------------------------------------
# Starter selection: which models count as "Japanese performance/enthusiast".
# min_hp filters out the base engines of mass-market models (e.g. a 1.6 Civic).
# --------------------------------------------------------------------------
STARTER_RULES = [
    # (make, source model name, minimum hp)
    ("Toyota", "Supra", 0), ("Toyota", "MR2", 150), ("Toyota", "Celica", 190),
    ("Nissan", "GT-R", 0), ("Nissan", "Skyline", 260), ("Nissan", "350Z", 0),
    ("Honda", "NSX", 0), ("Acura", "NSX", 0), ("Honda", "S2000", 0),
    ("Acura", "Integra", 190), ("Honda", "Civic Type-R", 0), ("Honda", "Prelude", 195),
    ("Mazda", "RX-7", 140), ("Mazda", "RX-8", 0), ("Mazda", "MX-5 / Miata", 150),
    ("Mitsubishi", "Lancer Evolution", 0), ("Mitsubishi", "3000 GT", 250),
    ("Mitsubishi", "Starion", 0),
    ("Subaru", "Impreza", 210), ("Subaru", "Impreza WRX STi", 0), ("Subaru", "SVX", 230),
    ("Lexus", "SC", 250),
]
YEAR_MIN, YEAR_MAX = 1980, 2010
# Roadster/convertible variants share the powertrain: skip to avoid inflating counts.
EXCLUDE_BODY = re.compile(r"roadster|spyder|spider|convertible|cabriolet|cabrio|targa", re.I)


def select_starter_vehicles(raw: pd.DataFrame) -> pd.DataFrame:
    """Filter the big raw table down to the starter set (see STARTER_RULES)."""
    parts = []
    for make, model, min_hp in STARTER_RULES:
        part = raw[(raw["make"] == make) & (raw["model"] == model)
                   & (raw["power_hp"].fillna(0) >= min_hp)]
        parts.append(part)
    sel = pd.concat(parts)
    in_window = (sel["gen_year_start"] <= YEAR_MAX) & (sel["gen_year_end"].fillna(YEAR_MAX) >= YEAR_MIN)
    sel = sel[in_window & ~sel["generation"].str.contains(EXCLUDE_BODY, na=False)]
    return sel.reset_index(drop=True)


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------
def download_file(url: str, dest: Path, timeout: int = 90) -> Path:
    """Stream a file to disk. Raises a clear error on failure (never fakes data)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout,
                      headers={"User-Agent": "CarDNA-student-project"}) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
    return dest


def collect_gor3a(force: bool = False) -> pd.DataFrame:
    """Download (if needed), select the starter set, map to schema, save import file."""
    if force or not GOR3A_RAW_PATH.exists():
        print(f"Downloading {GOR3A_RAW_URL}")
        download_file(GOR3A_RAW_URL, GOR3A_RAW_PATH)
    raw = pd.read_csv(GOR3A_RAW_PATH)
    starter = select_starter_vehicles(raw)
    mapped = map_gor3a_to_schema(starter)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    mapped.to_csv(GOR3A_IMPORT_PATH, index=False)
    print(f"gor3a: {len(raw):,} raw rows -> {len(mapped)} starter rows -> {GOR3A_IMPORT_PATH.name}")
    return mapped


# --------------------------------------------------------------------------
# Generic CSV / JSON import (for cardata.wiki downloads, your own research, ...)
# --------------------------------------------------------------------------
def read_table(path: str | Path) -> pd.DataFrame:
    """Read a .csv or .json file into a DataFrame (JSON: list of records, or
    a dict containing one list of records)."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            lists = [v for v in data.values() if isinstance(v, list)]
            if len(lists) != 1:
                raise ValueError("JSON object must contain exactly one list of records")
            data = lists[0]
        return pd.json_normalize(data)
    raise ValueError(f"Unsupported file type: {path.suffix} (use .csv or .json)")


def import_table(path: str | Path, source_name: str, source_url: str,
                 column_map: dict[str, str] | None = None,
                 units: dict[str, str] | None = None,
                 verification_status: str | None = None,
                 save_as: str | None = None) -> pd.DataFrame:
    """Import any CSV/JSON into the CarDNA schema.

    column_map : {their_column: our_column}. Unmapped columns are dropped.
    units      : {our_column: unit_it_is_in}, e.g. {"weight_kg": "lb"}.
    verification_status : set to "verified_manual" ONLY for rows you checked by
                 hand against a primary source.
    The standardised result is saved in data/raw/imports/ so that
    `python -m src.data_cleaning` picks it up automatically.
    """
    df = read_table(path)
    if column_map:
        df = df.rename(columns=column_map)
    unknown = [c for c in df.columns if c not in ALL_COLUMNS]
    df = df[[c for c in df.columns if c in ALL_COLUMNS]]
    for needed in ("make", "model"):
        if needed not in df.columns:
            raise ValueError(f"Column '{needed}' missing after mapping. "
                             f"Dropped unrecognised columns: {unknown}")
    df = convert_units(df, units)
    df["source_name"] = df.get("source_name", pd.Series(index=df.index, dtype=object)).fillna(source_name)
    df["source_url"] = df.get("source_url", pd.Series(index=df.index, dtype=object)).fillna(source_url)
    if verification_status:
        df["verification_status"] = verification_status
    for c in ALL_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[ALL_COLUMNS]
    # Free-text label is needed by some plausibility checks; fall back to blank.
    df["source_label"] = df["source_label"].fillna("")
    name = save_as or re.sub(r"[^a-z0-9]+", "_", source_name.lower()).strip("_") + ".csv"
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(IMPORT_DIR / name, index=False)
    print(f"Imported {len(df)} rows from {path} -> data/raw/imports/{name}"
          + (f" (ignored columns: {unknown})" if unknown else ""))
    return df


def write_manual_template(path: Path | None = None) -> Path:
    """Write an empty CSV with the CarDNA schema columns for manual data entry."""
    path = path or RAW_DIR / "manual_import_template.csv"
    pd.DataFrame(columns=SCHEMA_COLUMNS).to_csv(path, index=False)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="CarDNA data collection")
    p.add_argument("--download", action="store_true", help="download gor3a dataset and build starter import")
    p.add_argument("--force", action="store_true", help="re-download even if the file exists")
    p.add_argument("--import-file", help="CSV/JSON to import")
    p.add_argument("--source-name"); p.add_argument("--source-url")
    p.add_argument("--column-map", help="JSON file: {their_column: our_column}")
    p.add_argument("--units", help="JSON file: {our_column: unit}")
    p.add_argument("--verified", action="store_true", help="mark rows as verified_manual")
    p.add_argument("--template", action="store_true", help="write the manual-entry CSV template")
    a = p.parse_args()

    if a.template:
        print("Wrote", write_manual_template())
    if a.download:
        collect_gor3a(force=a.force)
    if a.import_file:
        if not (a.source_name and a.source_url):
            raise SystemExit("--source-name and --source-url are required (source URLs are preserved).")
        cmap = json.loads(Path(a.column_map).read_text()) if a.column_map else None
        units = json.loads(Path(a.units).read_text()) if a.units else None
        import_table(a.import_file, a.source_name, a.source_url, cmap, units,
                     "verified_manual" if a.verified else None)
    if not (a.download or a.import_file or a.template):
        p.print_help()


if __name__ == "__main__":
    main()
