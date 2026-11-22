"""
CarDNA - analysis.

Pure pandas/numpy (no Streamlit), so every function can be tested on its own.

Golden rule: never calculate a statistic from missing data without saying so.
 * Metrics return NaN when an input is missing (never 0, never an average).
 * `grouped_stats` reports how many rows each number is based on (`n`) and marks
   groups with fewer than `min_n` rows as not reliable.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT / "data" / "processed" / "cardna_dataset.csv"

MIN_GROUP_SIZE = 3   # groups smaller than this are shown but marked "low n"


# --------------------------------------------------------------------------
# Loading and derived metrics
# --------------------------------------------------------------------------
def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Read the processed dataset and add the derived metrics."""
    df = pd.read_csv(path)
    return add_metrics(df)


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add the calculated columns.

    power_density_hp_per_l      = horsepower / displacement in litres
    torque_density_nm_per_l     = torque / displacement in litres
    power_to_weight_hp_per_t    = horsepower / weight in tonnes

    Any row with a missing or non-positive input gets NaN.
    Rotary engines get NaN for per-litre metrics: sources quote their
    displacement inconsistently (chamber volume vs. 'equivalent' x2), so a
    per-litre figure would be misleading.
    """
    out = df.copy()
    litres = (out["displacement_cc"] / 1000).where(out["displacement_cc"] > 0)
    tonnes = (out["weight_kg"] / 1000).where(out["weight_kg"] > 0)
    not_rotary = out["engine_layout"].ne("Rotary")
    out["power_density_hp_per_l"] = (out["horsepower_hp"] / litres).where(not_rotary)
    out["torque_density_nm_per_l"] = (out["torque_nm"] / litres).where(not_rotary)
    out["power_to_weight_hp_per_t"] = out["horsepower_hp"] / tonnes
    out["displacement_l"] = litres
    out["production_year_end_filled"] = out["production_year_end"].fillna(out["production_year"])
    out["vehicle_label"] = out.apply(vehicle_label, axis=1)
    return out


def vehicle_label(row: pd.Series) -> str:
    """Short human-readable name, e.g. 'Toyota Supra (1993) 3.0L Turbocharged 330 hp'."""
    litres = f"{row['displacement_cc'] / 1000:.1f}L" if pd.notna(row["displacement_cc"]) else "?L"
    asp = {"Turbocharged": " turbo", "Supercharged": " supercharged"}.get(row["aspiration"], "")
    hp = f"{row['horsepower_hp']:.0f} hp" if pd.notna(row["horsepower_hp"]) else "? hp"
    gen = row["generation"] if pd.notna(row["generation"]) else ""
    tx = ""
    if pd.notna(row["transmission"]):
        gears = f"{int(row['gear_count'])}-sp " if pd.notna(row["gear_count"]) else ""
        tx = f" {gears}{str(row['transmission']).lower()}"
    return f"{row['make']} {gen} · {litres}{asp} · {hp}{tx}"


# --------------------------------------------------------------------------
# Safe statistics
# --------------------------------------------------------------------------
def grouped_stats(df: pd.DataFrame, by: str | list[str], value: str,
                  min_n: int = MIN_GROUP_SIZE) -> pd.DataFrame:
    """Mean/median/min/max of `value` per group, ignoring missing values.

    Output columns: n (rows actually used), mean, median, min, max, reliable
    (True when n >= min_n). Rows with a missing `value` are NOT counted in n.
    """
    by = [by] if isinstance(by, str) else by
    valid = df.dropna(subset=by + [value])
    if valid.empty:
        return pd.DataFrame(columns=by + ["n", "mean", "median", "min", "max", "reliable"])
    stats = (valid.groupby(by)[value]
             .agg(n="count", mean="mean", median="median", min="min", max="max")
             .reset_index())
    stats["reliable"] = stats["n"] >= min_n
    return stats.sort_values("mean", ascending=False).reset_index(drop=True)


def usable_rows(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int]:
    """Rows where all `columns` are present, plus how many rows were excluded."""
    ok = df.dropna(subset=columns)
    return ok, len(df) - len(ok)


def linear_fit(x: pd.Series, y: pd.Series, min_n: int = 5) -> dict | None:
    """Least-squares line y = slope*x + intercept and Pearson r on rows where both
    values exist. Returns None if there are too few points to say anything."""
    ok = pd.concat([x, y], axis=1).dropna()
    if len(ok) < min_n or ok.iloc[:, 0].nunique() < 2:
        return None
    xv, yv = ok.iloc[:, 0].to_numpy(float), ok.iloc[:, 1].to_numpy(float)
    slope, intercept = np.polyfit(xv, yv, 1)
    r = float(np.corrcoef(xv, yv)[0, 1])
    return {"slope": float(slope), "intercept": float(intercept), "r": r,
            "r2": r * r, "n": int(len(ok)), "x_min": float(xv.min()), "x_max": float(xv.max())}


def coverage(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Percentage of rows that have each column filled in."""
    return pd.DataFrame({"column": columns,
                         "filled_pct": [round(100 * df[c].notna().mean(), 1) for c in columns],
                         "missing_rows": [int(df[c].isna().sum()) for c in columns]})


# --------------------------------------------------------------------------
# Specific analyses used by the pages
# --------------------------------------------------------------------------
def avg_hp_by_make(df: pd.DataFrame) -> pd.DataFrame:
    return grouped_stats(df, "make", "horsepower_hp")


def aspiration_comparison(df: pd.DataFrame, value: str = "power_density_hp_per_l") -> pd.DataFrame:
    return grouped_stats(df, "aspiration", value)


def layout_comparison(df: pd.DataFrame, value: str = "horsepower_hp",
                      layouts: list[str] | None = None) -> pd.DataFrame:
    sub = df if layouts is None else df[df["engine_layout"].isin(layouts)]
    return grouped_stats(sub, "engine_layout", value)


def generation_summary(df: pd.DataFrame, make: str, model: str) -> pd.DataFrame:
    """One row per generation of a model, with its strongest and median figures.

    Generations are ordered by start year. 'configs' = how many engine
    configurations are in the dataset for that generation.
    """
    sub = df[(df["make"] == make) & (df["model"] == model)]
    if sub.empty:
        return pd.DataFrame()
    g = sub.groupby(["production_year", "generation"], dropna=False)
    summary = g.agg(
        configs=("config_id", "count"),
        hp_max=("horsepower_hp", "max"), hp_median=("horsepower_hp", "median"),
        torque_max=("torque_nm", "max"), torque_median=("torque_nm", "median"),
        displacement_max_cc=("displacement_cc", "max"),
        weight_median_kg=("weight_kg", "median"),
        power_to_weight_max=("power_to_weight_hp_per_t", "max"),
        drivetrains=("drivetrain", lambda s: ", ".join(sorted(s.dropna().unique())) or "—"),
        aspirations=("aspiration", lambda s: ", ".join(sorted(s.dropna().unique())) or "—"),
    ).reset_index().sort_values("production_year").reset_index(drop=True)
    return summary


def generation_changes(summary: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Change from the first to the last generation for each column (abs and %).
    Columns missing in either end are reported as NaN rather than guessed."""
    rows = []
    for c in cols:
        vals = summary[c].dropna()
        if len(vals) < 2:
            rows.append({"metric": c, "first": np.nan, "last": np.nan, "change": np.nan, "change_pct": np.nan})
            continue
        first, last = vals.iloc[0], vals.iloc[-1]
        rows.append({"metric": c, "first": first, "last": last, "change": last - first,
                     "change_pct": 100 * (last - first) / first if first else np.nan})
    return pd.DataFrame(rows)


def clean_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows without conflict/needs-review problems (used for 'featured' picks)."""
    return df[~df["verification_status"].isin(["conflict_flagged", "needs_review"])]


def dataset_findings(df: pd.DataFrame) -> list[str]:
    """Findings computed from the data. Every sentence states its sample size.
    Nothing here is hard-coded: change the data and the findings change."""
    findings: list[str] = []
    ok = clean_rows(df)

    pd_rows = ok.dropna(subset=["power_density_hp_per_l"])
    if len(pd_rows):
        top = pd_rows.loc[pd_rows["power_density_hp_per_l"].idxmax()]
        findings.append(
            f"Highest power density: **{top['make']} {top['generation']}** "
            f"({top['engine_layout']}, {top['aspiration'].lower()}) at "
            f"**{top['power_density_hp_per_l']:.0f} hp/L** "
            f"(of {len(pd_rows)} configurations with the needed data; rotaries excluded).")

    pw = ok.dropna(subset=["power_to_weight_hp_per_t"])
    if len(pw):
        top = pw.loc[pw["power_to_weight_hp_per_t"].idxmax()]
        findings.append(
            f"Best power-to-weight: **{top['make']} {top['generation']}** at "
            f"**{top['power_to_weight_hp_per_t']:.0f} hp/tonne** (n = {len(pw)}).")

    asp = aspiration_comparison(df)
    na = asp[asp["aspiration"] == "Naturally aspirated"]
    forced = asp[asp["aspiration"].isin(["Turbocharged", "Supercharged"])]
    if len(na) and len(forced) and na["reliable"].all() and forced["reliable"].all():
        na_med = float(na["median"].iloc[0])
        f_n = int(forced["n"].sum())
        f_med = float(df[df["aspiration"].isin(["Turbocharged", "Supercharged"])]["power_density_hp_per_l"].median())
        findings.append(
            f"Median power density: forced induction **{f_med:.0f} hp/L** (n = {f_n}) vs. "
            f"naturally aspirated **{na_med:.0f} hp/L** (n = {int(na['n'].iloc[0])}). "
            f"Note: {int((df['aspiration_basis'] == 'assumed_na').sum())} rows are *assumed* NA "
            f"because no turbo marker was found in the source text.")

    fit = linear_fit(df["weight_kg"], df["horsepower_hp"])
    if fit:
        findings.append(
            f"Weight vs. horsepower correlation in this dataset: r = **{fit['r']:.2f}** "
            f"(n = {fit['n']}). Heavier cars here tend to make "
            f"{'more' if fit['slope'] > 0 else 'less'} power; this is a property of the selected "
            f"models, not a general law.")

    flagged = int(df["verification_status"].isin(["conflict_flagged", "needs_review"]).sum())
    if flagged:
        findings.append(f"**{flagged}** of {len(df)} configurations carry data-quality flags "
                        f"(conflicts, implausible values or label mismatches) — see the data quality panel.")
    return findings
