"""
CarDNA - data cleaning.

Turns raw source tables into ONE consistent table (one row = one vehicle
configuration) and is deliberately honest about what it does not know:

  * Missing values stay missing (NaN). Nothing is imputed.
  * Implausible values are set to NaN and flagged, never silently kept.
  * Values that were *inferred* (not stated by the source) are labelled with a
    "*_basis" column so the app can show how much to trust them.
  * Duplicate rows are merged; if the duplicates disagree the row is flagged.

Run the whole pipeline with:   python -m src.data_cleaning
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
IMPORT_DIR = RAW_DIR / "imports"
PROCESSED_DIR = ROOT / "data" / "processed"
DATASET_PATH = PROCESSED_DIR / "cardna_dataset.csv"
REPORT_PATH = PROCESSED_DIR / "build_report.json"

# --------------------------------------------------------------------------
# 1. Schema
# --------------------------------------------------------------------------
SCHEMA_COLUMNS = [
    "make", "model", "generation", "trim", "market", "production_year",
    "engine_code", "engine_layout", "cylinders", "displacement_cc", "aspiration",
    "horsepower_hp", "horsepower_rpm", "torque_nm", "torque_rpm", "drivetrain",
    "transmission", "gear_count", "weight_kg", "acceleration_0_100",
    "top_speed_kmh", "source_url", "source_name", "verification_status",
]
# Extra columns that explain *how much to trust* each row.
EXTRA_COLUMNS = [
    "config_id", "production_year_end", "body_type", "source_label",
    "aspiration_basis", "engine_layout_basis", "quality_flags", "n_source_rows",
]
ALL_COLUMNS = SCHEMA_COLUMNS + EXTRA_COLUMNS

NUMERIC_COLUMNS = [
    "production_year", "production_year_end", "cylinders", "displacement_cc",
    "horsepower_hp", "horsepower_rpm", "torque_nm", "torque_rpm", "gear_count",
    "weight_kg", "acceleration_0_100", "top_speed_kmh",
]

# --------------------------------------------------------------------------
# 2. Unit normalisation  (target units: kg, Nm, km/h, cc, metric hp)
# --------------------------------------------------------------------------
# horsepower_hp is METRIC horsepower (PS / CV / "hp" on most European spec
# sheets). 1 kW = 1.35962 PS, 1 SAE/bhp = 1.01387 PS.
UNIT_FACTORS = {
    "weight_kg": {"kg": 1.0, "lb": 0.45359237, "t": 1000.0},
    "torque_nm": {"nm": 1.0, "lb-ft": 1.3558179483, "kgm": 9.80665},
    "top_speed_kmh": {"kmh": 1.0, "mph": 1.609344},
    "displacement_cc": {"cc": 1.0, "l": 1000.0, "cu_in": 16.387064},
    "horsepower_hp": {"ps": 1.0, "hp": 1.0, "bhp": 1.01387, "sae_hp": 1.01387,
                      "kw": 1.359621617},
}


def convert_units(df: pd.DataFrame, units: dict[str, str] | None) -> pd.DataFrame:
    """Convert columns to CarDNA's standard units.

    `units` maps a column to the unit it is currently in, e.g.
    {"weight_kg": "lb", "torque_nm": "lb-ft", "horsepower_hp": "bhp"}.
    Columns not listed are assumed to already be in standard units.
    """
    out = df.copy()
    for col, unit in (units or {}).items():
        factors = UNIT_FACTORS.get(col)
        if factors is None:
            raise ValueError(f"No unit conversion defined for column '{col}'")
        key = unit.strip().lower()
        if key not in factors:
            raise ValueError(f"Unknown unit '{unit}' for {col}. Options: {list(factors)}")
        out[col] = pd.to_numeric(out[col], errors="coerce") * factors[key]
    return out


# --------------------------------------------------------------------------
# 3. Parsing helpers (turn free text labels into structured fields)
# --------------------------------------------------------------------------
MODEL_ALIASES = {
    "MX-5 / Miata": "MX-5 Miata",
    "3000 GT": "3000GT",
    "Impreza WRX STi": "Impreza WRX STI",
}

# Models that are ALWAYS turbocharged, so a missing "Turbo" in the label is not
# evidence of a naturally aspirated engine. (Domain knowledge, documented.)
ALWAYS_TURBO = {
    ("Mitsubishi", "Lancer Evolution"),
    ("Nissan", "GT-R"),
    ("Subaru", "Impreza WRX STI"),
}
ROTARY_MODELS = {("Mazda", "RX-7"), ("Mazda", "RX-8")}

_TURBO_WORDS = re.compile(r"twin[- ]?turbo|turbo|biturbo|\bWRX\b|\bSTI\b|mazdaspeed", re.I)
_TURBO_TOKENS = re.compile(r"\bTT?\b")           # case-sensitive: "T" or "TT"
_SUPERCHARGED = re.compile(r"supercharg|kompressor", re.I)


def parse_aspiration(label: str, make: str, model: str) -> tuple[str, str]:
    """Return (aspiration, basis).

    basis = "label"        -> the source text says so
            "model_rule"   -> the model is always turbocharged
            "assumed_na"   -> NO forced-induction marker found, so we ASSUME
                              naturally aspirated. This is an assumption.
    """
    label = label or ""
    if _SUPERCHARGED.search(label):
        return "Supercharged", "label"
    if _TURBO_WORDS.search(label) or _TURBO_TOKENS.search(label):
        return "Turbocharged", "label"
    if (make, model) in ALWAYS_TURBO:
        return "Turbocharged", "model_rule"
    return "Naturally aspirated", "assumed_na"


def parse_layout(label: str, make: str, model: str, cylinders: float) -> tuple[str, str]:
    """Return (engine_layout, basis). Layout is explicit only for V engines and
    rotaries; otherwise it is inferred (Subaru -> flat/boxer, others -> inline)."""
    label = label or ""
    if re.search(r"rotary", label, re.I) or (make, model) in ROTARY_MODELS:
        return "Rotary", "label_or_model_rule"
    v = re.search(r"\bV\s?(\d{1,2})\b", label)
    if v:
        return f"V{v.group(1)}", "label"
    if pd.isna(cylinders):
        return "Unknown", "unknown"
    n = int(cylinders)
    if make == "Subaru" and n in (4, 6):
        return f"Flat-{n}", "inferred_from_make"
    return f"Inline-{n}", "inferred_from_cylinders"


def parse_transmission(text: str, label: str = "") -> tuple[str | float, float]:
    """Return (type, gear_count) from texts like '5-speed manual', '4AT', 'CVT'."""
    for source in (text, label):
        if not isinstance(source, str) or not source.strip():
            continue
        s = source.lower()
        gears = re.search(r"(\d)\s*[- ]?\s*speed|speed[, ]+(\d)|\b(\d)\s?(mt|at)\b", s)
        n = np.nan
        if gears:
            n = float(next(g for g in gears.groups()[:3] if g))
        if "cvt" in s:
            return "CVT", n
        if "manual" in s or re.search(r"\d\s?mt\b", s):
            return "Manual", n
        if "auto" in s or re.search(r"\d\s?at\b", s):
            return "Automatic", n
    return np.nan, np.nan


_TRIMS = re.compile(r"\b(GS-R|VTi|WRX|STi|STI|Nismo|Spec[- ]?V|Type[- ]?R|GT-Four|RS|LS|GSX)\b", re.I)


def parse_trim(label: str) -> str | float:
    m = _TRIMS.search(label or "")
    return m.group(1) if m else np.nan


def parse_label_hp(label: str) -> float:
    """Pull '(280 HP)' out of a label so we can cross-check the numeric column."""
    m = re.search(r"(\d{2,4})\s*HP\b", label or "", re.I)
    return float(m.group(1)) if m else np.nan


def parse_label_litres(label: str) -> float:
    m = re.match(r"\s*(\d\.\d)\s*L?\b", label or "")
    return float(m.group(1)) if m else np.nan


# --------------------------------------------------------------------------
# 4. Mapping the gor3a/autoevolution table onto the CarDNA schema
# --------------------------------------------------------------------------
GOR3A_URL = "https://github.com/gor3a/vehicle-makes-models/blob/main/data/csv/engines.csv"
GOR3A_NAME = "gor3a/vehicle-makes-models (upstream: autoevolution.com)"


def map_gor3a_to_schema(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in raw.itertuples(index=False):
        make = r.make
        model = MODEL_ALIASES.get(r.model, r.model)
        label = r.engine_label if isinstance(r.engine_label, str) else ""
        aspiration, asp_basis = parse_aspiration(label, make, model)
        layout, lay_basis = parse_layout(label, make, model, r.cylinders)
        tx, gears = parse_transmission(r.transmission, label)
        is_rotary = layout == "Rotary"
        rows.append({
            "make": make, "model": model, "generation": r.generation,
            "trim": parse_trim(label),
            "market": "Unspecified",              # the source does not state it
            "production_year": r.gen_year_start,
            "production_year_end": r.gen_year_end,
            "engine_code": np.nan,                # not provided by this source
            "engine_layout": layout, "engine_layout_basis": lay_basis,
            # For rotaries the source 'cylinders' is the rotor count: not comparable.
            "cylinders": np.nan if is_rotary else r.cylinders,
            "displacement_cc": r.displacement_cc,
            "aspiration": aspiration, "aspiration_basis": asp_basis,
            "horsepower_hp": r.power_hp, "horsepower_rpm": np.nan,
            "torque_nm": r.torque_nm, "torque_rpm": np.nan,
            "drivetrain": r.drivetrain, "transmission": tx, "gear_count": gears,
            "weight_kg": r.curb_weight_kg,
            "acceleration_0_100": r.zero_to_100_s, "top_speed_kmh": r.top_speed_kmh,
            "body_type": r.body_type, "source_label": label,
            "source_url": GOR3A_URL, "source_name": GOR3A_NAME,
            "verification_status": np.nan,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 5. Plausibility checks  (flag, and blank out values that cannot be right)
# --------------------------------------------------------------------------
PLAUSIBLE_RANGES = {              # column: (min, max)  -- generous on purpose
    "horsepower_hp": (40, 800),
    "weight_kg": (600, 2500),
    "acceleration_0_100": (2.5, 20),
    "top_speed_kmh": (120, 400),
    "torque_nm": (60, 1200),
}
NOTE_ONLY_FLAGS = {"rotary_displacement_ambiguous"}   # information, not a problem


def add_plausibility_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Blank out impossible values (keeping the raw number in the flag text) and
    flag disagreements between a numeric column and the text label it came from."""
    out = df.copy()
    flags: list[list[str]] = [[] for _ in range(len(out))]
    pos = {idx: i for i, idx in enumerate(out.index)}

    for col, (lo, hi) in PLAUSIBLE_RANGES.items():
        bad = out[col].notna() & ((out[col] < lo) | (out[col] > hi))
        for idx in out.index[bad]:
            flags[pos[idx]].append(f"{col}_implausible({out.at[idx, col]:g})")
        out.loc[bad, col] = np.nan

    label_hp = out["source_label"].map(parse_label_hp)
    mismatch = label_hp.notna() & out["horsepower_hp"].notna() & (
        (label_hp - out["horsepower_hp"]).abs() / out["horsepower_hp"] > 0.08)
    for idx in out.index[mismatch]:
        flags[pos[idx]].append(
            f"label_hp_mismatch(label {label_hp[idx]:g} vs column {out.at[idx, 'horsepower_hp']:g})")

    label_l = out["source_label"].map(parse_label_litres)
    cc_l = out["displacement_cc"] / 1000
    disp_bad = (label_l.notna() & cc_l.notna() & ((label_l - cc_l).abs() / cc_l > 0.08)
                & (out["engine_layout"] != "Rotary"))
    for idx in out.index[disp_bad]:
        flags[pos[idx]].append(f"displacement_label_mismatch(label {label_l[idx]:g}L vs {cc_l[idx]:.2f}L)")

    for idx in out.index[out["engine_layout"] == "Rotary"]:
        flags[pos[idx]].append("rotary_displacement_ambiguous")

    existing = out["quality_flags"].fillna("") if "quality_flags" in out else ""
    out["quality_flags"] = [
        ";".join([f for f in ([e] if e else []) + new])
        for e, new in zip(existing if len(out) else [], flags)
    ] if len(out) else []
    return out


# --------------------------------------------------------------------------
# 6. Duplicates and conflicts
# --------------------------------------------------------------------------
CONFLICT_TOLERANCE = {            # relative difference allowed before flagging
    "horsepower_hp": 0.03, "torque_nm": 0.03, "weight_kg": 0.03,
    "acceleration_0_100": 0.05, "top_speed_kmh": 0.05,
}
_BASE_KEY = ["make", "model", "generation", "displacement_cc", "aspiration",
             "transmission", "gear_count", "hp_bucket"]


def deduplicate_and_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Merge rows describing the same configuration.

    Two rows are 'the same configuration' when make, model, generation,
    displacement, aspiration, gearbox and power (rounded to 5 hp) agree.
    Within a group: blanks are filled from the other rows, and if the numbers
    disagree by more than CONFLICT_TOLERANCE the merged row is flagged.
    The same code also flags disagreements BETWEEN different sources.
    """
    work = df.copy()
    work["hp_bucket"] = (work["horsepower_hp"] / 5).round()

    # If the only difference is a blank drivetrain, fill it from the siblings.
    def _fill_drive(s: pd.Series):
        known = s.dropna().unique()
        return s.fillna(known[0]) if len(known) == 1 else s
    work["drivetrain"] = work.groupby(_BASE_KEY, dropna=False, sort=False)["drivetrain"].transform(_fill_drive)

    merged = []
    for _, g in work.groupby(_BASE_KEY + ["drivetrain"], dropna=False, sort=False):
        g = g.assign(_filled=g.notna().sum(axis=1)).sort_values("_filled", ascending=False)
        row = g.iloc[0].copy()
        for col in g.columns:                       # fill blanks from siblings
            if pd.isna(row[col]):
                vals = g[col].dropna()
                if len(vals):
                    row[col] = vals.iloc[0]
        flags = [f for f in g["quality_flags"].fillna("") if f]
        flag_set = list(dict.fromkeys(";".join(flags).split(";"))) if flags else []
        flag_set = [f for f in flag_set if f]
        for col, tol in CONFLICT_TOLERANCE.items():
            vals = g[col].dropna()
            if len(vals) > 1 and vals.max() > 0 and (vals.max() - vals.min()) / vals.max() > tol:
                flag_set.append(f"conflict_{col}({vals.min():g} vs {vals.max():g})")
        row["quality_flags"] = ";".join(flag_set)
        row["n_source_rows"] = len(g)
        row["source_name"] = "; ".join(sorted(g["source_name"].dropna().unique()))
        row["source_url"] = " | ".join(sorted(g["source_url"].dropna().unique()))
        statuses = set(g["verification_status"].dropna())
        row["verification_status"] = _status(flag_set, g["source_name"].nunique(), statuses)
        merged.append(row.drop(["_filled", "hp_bucket"]))
    return pd.DataFrame(merged).reset_index(drop=True)


def _status(flags: list[str], n_sources: int, manual_statuses: set) -> str:
    """verified_manual > conflict_flagged > needs_review > cross_checked > unverified_single_source"""
    if "verified_manual" in manual_statuses and not any(f.startswith("conflict_") for f in flags):
        return "verified_manual"
    if any(f.startswith("conflict_") for f in flags):
        return "conflict_flagged"
    if any(f.split("(")[0] not in NOTE_ONLY_FLAGS for f in flags):
        return "needs_review"
    return "cross_checked" if n_sources >= 2 else "unverified_single_source"


# --------------------------------------------------------------------------
# 7. Assemble everything
# --------------------------------------------------------------------------
def make_config_ids(df: pd.DataFrame) -> pd.Series:
    def slug(r) -> str:
        parts = [r.make, r.model, str(int(r.production_year)) if pd.notna(r.production_year) else "na",
                 f"{r.displacement_cc:.0f}cc" if pd.notna(r.displacement_cc) else "na",
                 f"{r.horsepower_hp:.0f}hp" if pd.notna(r.horsepower_hp) else "na",
                 str(r.transmission), str(r.drivetrain)]
        return re.sub(r"[^a-z0-9]+", "-", "-".join(parts).lower()).strip("-")
    ids = df.apply(slug, axis=1)
    return ids + ids.groupby(ids).cumcount().map(lambda n: "" if n == 0 else f"-{n + 1}")


def load_import_files() -> list[pd.DataFrame]:
    """Load every standardised CSV written by data_collection.import_table()."""
    frames = []
    for path in sorted(IMPORT_DIR.glob("*.csv")):
        frames.append(pd.read_csv(path))
    return frames


def build_dataset(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Full pipeline: combine -> flag -> deduplicate -> id -> save."""
    for f in frames:
        for c in ALL_COLUMNS:
            if c not in f.columns:
                f[c] = np.nan
    combined = pd.concat([f[ALL_COLUMNS] for f in frames], ignore_index=True)
    for c in NUMERIC_COLUMNS:
        combined[c] = pd.to_numeric(combined[c], errors="coerce")
    n_in = len(combined)

    flagged = add_plausibility_flags(combined)
    clean = deduplicate_and_flag(flagged)
    clean["config_id"] = make_config_ids(clean)
    clean = clean.sort_values(["make", "model", "production_year", "horsepower_hp"]).reset_index(drop=True)
    clean = clean[ALL_COLUMNS]

    report = {
        "rows_in": int(n_in),
        "rows_out": int(len(clean)),
        "duplicates_merged": int(n_in - len(clean)),
        "verification_status": clean["verification_status"].value_counts().to_dict(),
        "rows_with_flags": int((clean["quality_flags"].fillna("") != "").sum()),
        "missing_by_column": {c: int(clean[c].isna().sum()) for c in SCHEMA_COLUMNS},
        "sources": sorted(set("; ".join(clean["source_name"]).split("; "))),
    }
    return clean, report


def main() -> None:
    frames = load_import_files()
    if not frames:
        raise SystemExit("No standardised imports found in data/raw/imports/. "
                         "Run:  python -m src.data_collection --download")
    clean, report = build_dataset(frames)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(DATASET_PATH, index=False)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    print(f"\nSaved {len(clean)} rows -> {DATASET_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
