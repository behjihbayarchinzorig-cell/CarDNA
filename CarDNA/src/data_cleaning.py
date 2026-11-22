"""
Data cleaning for CarDNA.

Takes rows from any source and turns them into one consistent table where
every row is one specific vehicle configuration.

Steps (each is a small function you can read on its own):
  1. standardize_columns  - make sure every schema column exists
  2. convert_units        - PS, kW, lb-ft, kgf-m, litres, lb, mph -> hp, Nm, cc, kg, km/h
  3. normalize_values     - consistent spelling for make, layout, aspiration, drivetrain
  4. check_plausibility   - flag values that are physically unlikely
  5. merge_duplicates     - combine rows describing the same configuration,
                            and flag sources that disagree
  6. add_metrics          - power density and power-to-weight (only when inputs exist)
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
SCHEMA = [
    "make", "model", "generation", "trim", "market", "production_year",
    "engine_code", "engine_layout", "cylinders", "displacement_cc", "aspiration",
    "horsepower_hp", "horsepower_rpm", "torque_nm", "torque_rpm",
    "drivetrain", "transmission", "gear_count", "weight_kg",
    "acceleration_0_100", "top_speed_kmh",
    "source_url", "source_name", "verification_status",
]
NUMERIC = [
    "production_year", "cylinders", "displacement_cc", "horsepower_hp", "horsepower_rpm",
    "torque_nm", "torque_rpm", "gear_count", "weight_kg", "acceleration_0_100", "top_speed_kmh",
]
TEXT = [
    "make", "model", "generation", "trim", "market", "engine_code", "engine_layout",
    "aspiration", "drivetrain", "transmission", "source_url", "source_name", "verification_status",
]

# (input column, target column, multiply-by factor). The target is only filled
# when it is empty, so a value a source reported directly is never overwritten.
UNIT_CONVERSIONS = [
    ("horsepower_ps", "horsepower_hp", 0.98632),    # metric horsepower (PS) -> mechanical hp
    ("horsepower_kw", "horsepower_hp", 1.34102),    # kilowatts -> hp
    ("torque_lbft", "torque_nm", 1.35582),          # pound-feet -> newton-metres
    ("torque_kgfm", "torque_nm", 9.80665),          # kilogram-force metres -> newton-metres
    ("displacement_l", "displacement_cc", 1000.0),  # litres -> cubic centimetres
    ("weight_lb", "weight_kg", 0.45359237),         # pounds -> kilograms
    ("top_speed_mph", "top_speed_kmh", 1.609344),   # mph -> km/h
]
UNIT_INPUT_COLUMNS = [c[0] for c in UNIT_CONVERSIONS]

VERIFICATION_STATUSES = [
    "manually_verified", "cross_checked", "source_reported", "needs_review", "conflict_flagged",
]

# Values outside these ranges are flagged for review (not deleted).
PLAUSIBLE = {
    "production_year": (1970, 2030), "cylinders": (1, 16), "displacement_cc": (400, 10000),
    "horsepower_hp": (20, 1500), "torque_nm": (20, 2000), "weight_kg": (400, 4000),
    "acceleration_0_100": (2, 30), "top_speed_kmh": (80, 450), "gear_count": (3, 10),
}

# Two sources disagree when the gap is bigger than this share of the larger value.
CONFLICT_TOLERANCE = {
    "horsepower_hp": 0.03, "torque_nm": 0.03, "displacement_cc": 0.01,
    "weight_kg": 0.03, "acceleration_0_100": 0.08, "top_speed_kmh": 0.03,
}

# Which source wins when two sources report different values (lower = more trusted).
# Add your own sources here. Unknown sources get the lowest priority.
SOURCE_PRIORITY = {"manual": 0, "cardata.wiki": 1, "autoseeker": 2, "gor3a": 3}

# Fields that identify "the same configuration" across sources.
KEY_FIELDS = ["make", "model", "generation", "trim", "market", "production_year",
              "engine_code", "transmission"]

KNOWN_MAKES = {m.lower(): m for m in [
    "Toyota", "Nissan", "Honda", "Mazda", "Subaru", "Mitsubishi", "Suzuki",
    "Lexus", "Infiniti", "Acura", "Datsun", "Isuzu", "Daihatsu",
]}


# --------------------------------------------------------------------------
# 1. Columns
# --------------------------------------------------------------------------
def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case the column names and add any schema column that is missing."""
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    for col in SCHEMA + UNIT_INPUT_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    for col in NUMERIC + UNIT_INPUT_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in TEXT:
        out[col] = out[col].astype("object").where(out[col].notna(), np.nan)
        out[col] = out[col].map(lambda v: re.sub(r"\s+", " ", str(v)).strip() if pd.notna(v) else np.nan)
        out[col] = out[col].replace("", np.nan)
    return out


# --------------------------------------------------------------------------
# 2. Units
# --------------------------------------------------------------------------
def convert_units(df: pd.DataFrame) -> pd.DataFrame:
    """Fill hp, Nm, cc, kg and km/h from other units when the main column is empty."""
    out = df.copy()
    for source_col, target_col, factor in UNIT_CONVERSIONS:
        converted = out[source_col] * factor
        out[target_col] = out[target_col].fillna(converted)
    return out


# --------------------------------------------------------------------------
# 3. Text normalisation
# --------------------------------------------------------------------------
def normalize_make(value):
    if pd.isna(value):
        return np.nan
    return KNOWN_MAKES.get(str(value).strip().lower(), str(value).strip())


def normalize_aspiration(value):
    """Map many spellings to: Naturally aspirated, Turbocharged, Supercharged, Twin-charged."""
    if pd.isna(value):
        return np.nan
    s = str(value).lower()
    if "turbo" in s and ("super" in s or "twin-charg" in s or "twincharg" in s):
        return "Twin-charged"
    if "turbo" in s:
        return "Turbocharged"
    if "super" in s or "blower" in s:
        return "Supercharged"
    if s.strip() in {"na", "n/a", "n.a."} or "natural" in s or "atmospheric" in s:
        return "Naturally aspirated"
    return str(value).strip().capitalize()


def normalize_layout(layout, cylinders):
    """Return labels like Inline-4, Inline-6, V6, V8, Flat-4 or Rotary."""
    if pd.isna(layout):
        return np.nan
    s = str(layout).lower().strip()
    if "rotary" in s or "wankel" in s:
        return "Rotary"
    match = re.search(r"(\d+)", s)
    n = int(match.group(1)) if match else (int(cylinders) if pd.notna(cylinders) else None)
    if re.match(r"^v[-\s]?\d*$", s) or "v-type" in s or re.match(r"^v\d", s):
        kind = "V"
    elif any(k in s for k in ("flat", "boxer", "horizontally")) or re.match(r"^h[-\s]?\d", s):
        kind = "Flat"
    elif any(k in s for k in ("inline", "in-line", "straight")) or re.match(r"^[il][-\s]?\d", s):
        kind = "Inline"
    else:
        return str(layout).strip()
    if n is None:
        return kind
    return f"V{n}" if kind == "V" else f"{kind}-{n}"


def normalize_drivetrain(value):
    """Map to RWD, FWD or AWD."""
    if pd.isna(value):
        return np.nan
    s = str(value).lower()
    if any(k in s for k in ("awd", "4wd", "4x4", "all-wheel", "all wheel", "four-wheel", "four wheel")):
        return "AWD"
    if s.strip() in {"rwd", "rear"} or "rear-wheel" in s or "rear wheel" in s:
        return "RWD"
    if s.strip() in {"fwd", "front"} or "front-wheel" in s or "front wheel" in s:
        return "FWD"
    return str(value).strip()


def normalize_values(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["make"] = out["make"].map(normalize_make)
    out["aspiration"] = out["aspiration"].map(normalize_aspiration)
    out["drivetrain"] = out["drivetrain"].map(normalize_drivetrain)
    out["engine_layout"] = [normalize_layout(l, c) for l, c in zip(out["engine_layout"], out["cylinders"])]
    # If the layout text carried a cylinder count (e.g. "V6") and cylinders is empty, use it.
    from_layout = out["engine_layout"].astype(str).str.extract(r"(\d+)$")[0].astype(float)
    out["cylinders"] = out["cylinders"].fillna(from_layout)
    return out


# --------------------------------------------------------------------------
# 4. Plausibility
# --------------------------------------------------------------------------
def check_plausibility(df: pd.DataFrame) -> pd.DataFrame:
    """Write human-readable problems to quality_notes and mark the row if any are found."""
    out = df.copy()
    notes = [[] for _ in range(len(out))]
    for field, (lo, hi) in PLAUSIBLE.items():
        values = out[field].to_numpy(dtype=float)
        for i, v in enumerate(values):
            if not np.isnan(v) and not (lo <= v <= hi):
                notes[i].append(f"{field} {v:g} is outside the plausible range {lo}-{hi}")
    for i, url in enumerate(out["source_url"].to_numpy()):
        if pd.isna(url):
            notes[i].append("no source URL recorded")
    out["quality_notes"] = ["; ".join(n) if n else np.nan for n in notes]
    out["_needs_review"] = [bool(n) for n in notes]
    return out


# --------------------------------------------------------------------------
# 5. Duplicates and conflicts
# --------------------------------------------------------------------------
def _join_unique(series: pd.Series, sep: str) -> str | float:
    parts = list(dict.fromkeys(str(v) for v in series.dropna() if str(v)))
    return sep.join(parts) if parts else np.nan


def _source_rank(name) -> int:
    if pd.isna(name):
        return 99
    lowered = str(name).lower()
    for key, rank in SOURCE_PRIORITY.items():
        if key in lowered:
            return rank
    return 99


def merge_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rows with the same KEY_FIELDS describe one configuration. They are merged into
    one row. Where sources report different numbers, the most trusted source's
    value is kept and the disagreement is written to conflict_note.
    """
    out = df.copy()
    out["_key"] = (out[KEY_FIELDS].astype(object).fillna("").astype(str)
                   .apply(lambda col: col.str.lower().str.strip()).apply("|".join, axis=1))
    out["_rank"] = out["source_name"].map(_source_rank)
    out = out.sort_values("_rank", kind="stable").reset_index(drop=True)

    conflicts: dict[str, str] = {}
    agreeing: set[str] = set()
    for key, group in out[out["_key"].duplicated(keep=False)].groupby("_key"):
        notes, compared = [], False
        for field, tol in CONFLICT_TOLERANCE.items():
            vals = group[["source_name", field]].dropna()
            if len(vals) < 2:
                continue
            compared = True
            lo, hi = vals[field].min(), vals[field].max()
            if hi > 0 and (hi - lo) / hi > tol:
                detail = ", ".join(f"{s}: {v:g}" for s, v in zip(vals["source_name"], vals[field]))
                notes.append(f"{field} differs between sources ({detail})")
        if notes:
            conflicts[key] = "; ".join(notes)
        elif compared:
            agreeing.add(key)

    special = {"source_name", "source_url", "quality_notes", "_needs_review", "_key"}
    agg = {c: "first" for c in out.columns if c not in special}
    agg.update({
        "source_name": lambda s: _join_unique(s, "; "),
        "source_url": lambda s: _join_unique(s, " | "),
        "quality_notes": lambda s: _join_unique(s, "; "),
        "_needs_review": "any",
    })
    merged = out.groupby("_key", sort=False).agg(agg).reset_index()

    merged["conflict_note"] = merged["_key"].map(conflicts)
    merged["n_sources"] = merged["_key"].map(out["_key"].value_counts())

    status = merged["verification_status"].where(
        merged["verification_status"].isin(VERIFICATION_STATUSES), "source_reported")
    status = status.mask(merged["_key"].isin(agreeing) & (status == "source_reported"), "cross_checked")
    status = status.mask(merged["_needs_review"], "needs_review")
    status = status.mask(merged["conflict_note"].notna(), "conflict_flagged")
    merged["verification_status"] = status
    return merged.drop(columns=["_key", "_rank", "_needs_review"])


# --------------------------------------------------------------------------
# 6. Derived metrics
# --------------------------------------------------------------------------
def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide, returning NaN (never infinity or a fake zero) when an input is missing or <= 0."""
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    return (num / den.where(den > 0)).replace([np.inf, -np.inf], np.nan)


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    power_density_hp_per_l   = horsepower / displacement in litres
    power_to_weight_hp_per_t = horsepower / weight in tonnes
    """
    out = df.copy()
    out["power_density_hp_per_l"] = safe_ratio(out["horsepower_hp"], out["displacement_cc"] / 1000)
    out["power_to_weight_hp_per_t"] = safe_ratio(out["horsepower_hp"], out["weight_kg"] / 1000)
    return out


# --------------------------------------------------------------------------
# Whole pipeline
# --------------------------------------------------------------------------
OUTPUT_COLUMNS = SCHEMA + [
    "power_density_hp_per_l", "power_to_weight_hp_per_t",
    "n_sources", "conflict_note", "quality_notes",
]


def build_dataset(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine raw frames from any number of sources into the final dataset."""
    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    combined = pd.concat([standardize_columns(f) for f in frames], ignore_index=True)
    combined = convert_units(combined)
    combined = normalize_values(combined)
    combined = check_plausibility(combined)
    combined = merge_duplicates(combined)
    combined = add_metrics(combined)
    combined = combined.sort_values(["make", "model", "production_year"], na_position="last")
    return combined[OUTPUT_COLUMNS].reset_index(drop=True)
