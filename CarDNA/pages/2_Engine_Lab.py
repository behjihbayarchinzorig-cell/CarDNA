import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import with_metrics
from src.data_cleaning import load_processed

st.set_page_config(page_title="Engine Lab", layout="wide")
st.title("Engine Lab")

cars = with_metrics(load_processed())
st.write("Horsepower against engine size. Electric cars sit at 0 L and are left out of the trend.")

petrol = cars[cars["displacement_cc"] > 0]
st.scatter_chart(
    petrol,
    x="displacement_cc",
    y="horsepower_hp",
    color="make",
    size="torque_nm",
)

st.subheader("Specific output")
st.dataframe(
    cars[["year", "make", "model", "displacement_cc", "horsepower_hp", "power_per_litre"]].sort_values(
        "power_per_litre", ascending=False
    ),
    use_container_width=True,
    hide_index=True,
)
