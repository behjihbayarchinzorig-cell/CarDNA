from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="CarDNA",
    page_icon="🏎️",
    layout="wide"
)

st.title("CarDNA")
st.caption("Automotive Engineering & Data Exploration")

# Load dataset
DATA_PATH = Path(__file__).resolve().parent / "data" / "processed" / "cars.csv"
cars = pd.read_csv(DATA_PATH)

if cars.empty:
    st.warning("Our vehicle database is empty.")
    st.stop()

# Calculate additional metrics
cars["power_per_litre"] = (
    cars["horsepower_hp"] / (cars["displacement_cc"] / 1000)
)

cars["power_to_weight"] = (
    cars["horsepower_hp"] / (cars["weight_kg"] / 1000)
)

# Sidebar
st.sidebar.header("Filters")

makes = st.sidebar.multiselect(
    "Manufacturer",
    options=sorted(cars["make"].dropna().unique())
)

if makes:
    filtered_cars = cars[cars["make"].isin(makes)]
else:
    filtered_cars = cars.copy()

# Main metrics
col1, col2, col3 = st.columns(3)

col1.metric("Vehicles", len(filtered_cars))

col2.metric(
    "Manufacturers",
    filtered_cars["make"].nunique()
)

col3.metric(
    "Average horsepower",
    round(filtered_cars["horsepower_hp"].mean(), 1)
)

st.divider()

# Power comparison
st.subheader("Horsepower by Vehicle")

fig = px.bar(
    filtered_cars,
    x="model",
    y="horsepower_hp",
    color="make",
    title="Engine Output Comparison"
)

st.plotly_chart(fig, use_container_width=True)

# Vehicle database
st.subheader("Vehicle Database")

st.dataframe(
    filtered_cars,
    use_container_width=True
)
