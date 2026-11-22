import streamlit as st

from src.analysis import with_metrics
from src.data_cleaning import load_processed

st.set_page_config(page_title="Car Explorer", layout="wide")
st.title("Car Explorer")

cars = with_metrics(load_processed())
makes = st.multiselect("Make", sorted(cars["make"].dropna().unique()))
drivetrains = st.multiselect("Drivetrain", sorted(cars["drivetrain"].dropna().unique()))

filtered = cars
if makes:
    filtered = filtered[filtered["make"].isin(makes)]
if drivetrains:
    filtered = filtered[filtered["drivetrain"].isin(drivetrains)]

st.dataframe(filtered, use_container_width=True, hide_index=True)
