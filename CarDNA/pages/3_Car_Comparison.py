import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import with_metrics
from src.data_cleaning import load_processed

st.set_page_config(page_title="Car Comparison", layout="wide")
st.title("Car Comparison")

cars = with_metrics(load_processed())
cars["label"] = cars["year"].astype(int).astype(str) + " " + cars["make"] + " " + cars["model"]

picked = st.multiselect("Cars", cars["label"].tolist(), default=list(cars["label"].head(2)))
selected = cars[cars["label"].isin(picked)]

metrics = [
    "horsepower_hp",
    "torque_nm",
    "weight_kg",
    "acceleration_0_100",
    "power_to_weight",
    "power_per_litre",
]
st.dataframe(
    selected.set_index("label")[metrics].T,
    use_container_width=True,
)
