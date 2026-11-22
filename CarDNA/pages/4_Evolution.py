import streamlit as st

from src.analysis import by_year
from src.data_cleaning import load_processed

st.set_page_config(page_title="Evolution", layout="wide")
st.title("Evolution")
st.write("Average figures by model year in the processed dataset.")

trend = by_year(load_processed())
st.line_chart(trend, x="year", y=["avg_horsepower", "avg_weight_kg", "avg_acceleration_0_100"])
st.dataframe(trend, use_container_width=True, hide_index=True)
