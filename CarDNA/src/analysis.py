"""
Analysis functions for CarDNA.

Everything here takes a DataFrame and returns a DataFrame, a number or text.
No Streamlit code, so it can be tested on its own.

Safeguards against misleading statistics:
  * Rows flagged "conflict_flagged" or "needs_review" are left out of averages.
  * Missing values are dropped per calculation, and the number of rows used (n) is returned.
  * Groups smaller than MIN_GROUP_SIZE are marked unreliable instead of hidden.
"""
from __future__ import annotations

import pandas as pd

MIN_GROUP_SIZE = 5
MIN_CORRELATION_ROWS = 8
FLAGGED = ["conflict_flagged", "needs_review"]
MAIN_LAYOUTS = ["Inline-4", "Inline-6", "V6", "V8"]


def clean_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with no conflict or review flag. Used for averages and rankings."""
    return df[~df["verification_status"].isin(FLAGGED)]


def car_label(row) -> str:
    """Readable name, e.g. 'Toyota Supra A80 (JZA80) RZ, Japan 1993'."""
    parts = [row.get("make"), row.get("model"), row.get("generation"), row.get("trim")]
    name = " ".join(str(p) for p in parts if pd.notna(p))
    where = [str(int(row["production_year"])) if pd.notna(row.get("production_year")) else None,
             row.get("market") if pd.notna(row.get("market")) else None]
    where = [w for w in where if w]
    return f"{name}, {' '.join(where)}" if where else name


def group_stats(df: pd.DataFrame, by: str, value: str, min_n: int = MIN_GROUP_SIZE) -> pd.DataFrame:
    """Mean, median and count of `value` per `by`, with a `reliable` flag (n >= min_n)."""
    data = df.dropna(subset=[by, value])
    if data.empty:
        return pd.DataFrame(columns=[by, "n", "mean", "median", "reliable"])
    stats = data.groupby(by)[value].agg(n="count", mean="mean", median="median").reset_index()
    stats["reliable"] = stats["n"] >= min_n
    return stats.sort_values("mean", ascending=False).reset_index(drop=True)


def avg_hp_by_make(df: pd.DataFrame) -> pd.DataFrame:
    return group_stats(clean_rows(df), "make", "horsepower_hp")


def aspiration_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Naturally aspirated vs turbocharged etc.: count and mean of key metrics."""
    data = clean_rows(df).dropna(subset=["aspiration"])
    if data.empty:
        return pd.DataFrame()
    summary = data.groupby("aspiration").agg(
        n=("aspiration", "size"),
        mean_hp=("horsepower_hp", "mean"),
        mean_hp_per_litre=("power_density_hp_per_l", "mean"),
        mean_torque_nm=("torque_nm", "mean"),
        mean_hp_per_tonne=("power_to_weight_hp_per_t", "mean"),
    ).reset_index()
    summary["reliable"] = summary["n"] >= MIN_GROUP_SIZE
    return summary


def layout_summary(df: pd.DataFrame, layouts: list[str] | None = None) -> pd.DataFrame:
    """Mean power density per engine layout (Inline-4, Inline-6, V6, V8 by default)."""
    data = clean_rows(df)
    if layouts:
        data = data[data["engine_layout"].isin(layouts)]
    return group_stats(data, "engine_layout", "power_density_hp_per_l")


def safe_corr(df: pd.DataFrame, a: str, b: str):
    """Correlation of two columns, or None if there are too few complete rows to mean anything."""
    data = df[[a, b]].dropna()
    if len(data) < MIN_CORRELATION_ROWS or data[a].nunique() < 2 or data[b].nunique() < 2:
        return None
    return float(data[a].corr(data[b]))


def coverage(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """How many rows have a value in each column."""
    filled = [int(df[c].notna().sum()) for c in columns]
    return pd.DataFrame({"field": columns, "rows_filled": filled,
                         "share": [f"{f / len(df):.0%}" if len(df) else "-" for f in filled]})


def generation_table(df: pd.DataFrame, make: str, model: str) -> pd.DataFrame:
    """One row per generation of a model, summarising how the specs changed."""
    data = df[(df["make"] == make) & (df["model"] == model)].copy()
    if data.empty:
        return pd.DataFrame()
    data["generation"] = data["generation"].fillna("(not stated)")

    def span(s):
        s = s.dropna()
        if s.empty:
            return "-"
        lo, hi = s.min(), s.max()
        return f"{lo:.0f}" if lo == hi else f"{lo:.0f}-{hi:.0f}"

    table = data.groupby("generation").agg(
        configurations=("model", "size"),
        years=("production_year", span),
        horsepower_hp=("horsepower_hp", span),
        torque_nm=("torque_nm", span),
        displacement_cc=("displacement_cc", span),
        weight_kg=("weight_kg", span),
        drivetrain=("drivetrain", lambda s: ", ".join(sorted(s.dropna().unique())) or "-"),
    ).reset_index()
    first_year = data.groupby("generation")["production_year"].min()
    table["_order"] = table["generation"].map(first_year)
    return table.sort_values("_order", na_position="last").drop(columns="_order").reset_index(drop=True)


def dataset_findings(df: pd.DataFrame) -> list[str]:
    """Plain-language findings. Each one is only written when the data supports it."""
    findings = []
    clean = clean_rows(df)
    findings.append(f"The dataset holds {len(df)} configurations; {len(clean)} have no conflict or review flag "
                    "and are used for averages and rankings.")

    ptw = clean.dropna(subset=["power_to_weight_hp_per_t"])
    if len(ptw):
        best = ptw.sort_values("power_to_weight_hp_per_t", ascending=False).iloc[0]
        findings.append(f"Highest power-to-weight: {car_label(best)} at "
                        f"{best['power_to_weight_hp_per_t']:.0f} hp per tonne.")
    else:
        findings.append("Power-to-weight cannot be calculated yet: no configuration has both power and weight.")

    pd_rows = clean.dropna(subset=["aspiration", "power_density_hp_per_l"])
    groups = pd_rows.groupby("aspiration")["power_density_hp_per_l"].agg(["count", "mean"])
    if {"Naturally aspirated", "Turbocharged"} <= set(groups.index) and \
            groups.loc[["Naturally aspirated", "Turbocharged"], "count"].min() >= MIN_GROUP_SIZE:
        na, turbo = groups.loc["Naturally aspirated", "mean"], groups.loc["Turbocharged", "mean"]
        findings.append(f"Turbocharged engines average {turbo:.0f} hp per litre against {na:.0f} for "
                        "naturally aspirated engines.")
    else:
        findings.append(f"Naturally aspirated vs turbocharged is not compared yet: it needs at least "
                        f"{MIN_GROUP_SIZE} configurations of each with power and displacement.")

    corr = safe_corr(clean, "displacement_cc", "torque_nm")
    if corr is not None:
        findings.append(f"Torque and displacement have a correlation of {corr:.2f} "
                        f"across {clean[['displacement_cc', 'torque_nm']].dropna().shape[0]} configurations.")
    return findings
