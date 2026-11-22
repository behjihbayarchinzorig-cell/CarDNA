"""Performance metrics derived from the cleaned car table."""

import pandas as pd


def with_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Add power-to-weight and specific output columns."""
    result = frame.copy()
    result["power_to_weight"] = result["horsepower_hp"] / (result["weight_kg"] / 1000)
    displacement_l = (result["displacement_cc"] / 1000).where(result["displacement_cc"] > 0)
    result["power_per_litre"] = result["horsepower_hp"] / displacement_l
    return result


def fastest(frame: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Return the n cars with the lowest 0–100 km/h time."""
    return with_metrics(frame).nsmallest(n, "acceleration_0_100")


def by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Average performance for each model year."""
    metrics = with_metrics(frame)
    return (
        metrics.groupby("year", as_index=False)
        .agg(
            cars=("model", "count"),
            avg_horsepower=("horsepower_hp", "mean"),
            avg_weight_kg=("weight_kg", "mean"),
            avg_acceleration_0_100=("acceleration_0_100", "mean"),
            avg_power_to_weight=("power_to_weight", "mean"),
        )
        .sort_values("year")
    )
