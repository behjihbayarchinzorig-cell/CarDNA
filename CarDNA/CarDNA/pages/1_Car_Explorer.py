"""Car Explorer - search, filter and inspect complete specifications."""
import pandas as pd
import streamlit as st

from src import ui

ui.setup_page("Car Explorer")
df = ui.load_data()

ui.page_header("Car Explorer", "Find a configuration",
               "Search and filter the dataset, then open any configuration for its full specification sheet.")


def multiselect_filter(label: str, column: str):
    """Sidebar multiselect. Selecting everything means 'no filter' so rows with a
    missing value in that column are not silently dropped."""
    options = sorted(df[column].dropna().unique())
    chosen = st.sidebar.multiselect(label, options, default=options)
    return column, chosen, len(chosen) < len(options)


st.sidebar.markdown("### Filters")
query = st.sidebar.text_input("Search", placeholder="e.g. Supra, RB26, turbo, Honda")
y_min, y_max = int(df["production_year"].min()), int(df["production_year_end_filled"].max())
years = st.sidebar.slider("Production years", y_min, y_max, (y_min, y_max),
                          help="Keeps generations whose production span overlaps this range.")
filters = [multiselect_filter("Manufacturer", "make"), multiselect_filter("Drivetrain", "drivetrain"),
           multiselect_filter("Engine layout", "engine_layout"), multiselect_filter("Aspiration", "aspiration")]

mask = (df["production_year"] <= years[1]) & (df["production_year_end_filled"] >= years[0])
for column, chosen, active in filters:
    if active:
        mask &= df[column].isin(chosen)
if query.strip():
    q = query.strip().lower()
    haystack = (df[["make", "model", "generation", "trim", "engine_layout", "aspiration", "source_label"]]
                .fillna("").astype(str).agg(" ".join, axis=1).str.lower())
    mask &= haystack.str.contains(q, regex=False)
view = df[mask].reset_index(drop=True)

st.markdown(f"**{len(view)}** of {len(df)} configurations match.")
if view.empty:
    ui.note("No configurations match these filters. Widen the year range or clear the search.")
    st.stop()

table = view[["make", "model", "generation", "production_year", "engine_layout", "displacement_cc",
              "aspiration", "horsepower_hp", "torque_nm", "drivetrain", "transmission", "weight_kg",
              "power_density_hp_per_l", "power_to_weight_hp_per_t", "verification_status"]]
st.dataframe(
    table, hide_index=True, width="stretch", height=360,
    column_config={
        "make": "Make", "model": "Model", "generation": "Generation",
        "production_year": st.column_config.NumberColumn("Year", format="%d"),
        "engine_layout": "Layout",
        "displacement_cc": st.column_config.NumberColumn("cc", format="%d"),
        "aspiration": "Aspiration",
        "horsepower_hp": st.column_config.NumberColumn("hp", format="%d"),
        "torque_nm": st.column_config.NumberColumn("Nm", format="%d"),
        "drivetrain": "Drive", "transmission": "Gearbox",
        "weight_kg": st.column_config.NumberColumn("kg", format="%d"),
        "power_density_hp_per_l": st.column_config.NumberColumn("hp/L", format="%.0f"),
        "power_to_weight_hp_per_t": st.column_config.NumberColumn("hp/t", format="%.0f"),
        "verification_status": "Status",
    })
st.download_button("Download filtered data (CSV)", view.to_csv(index=False).encode("utf-8"),
                   file_name="cardna_filtered.csv", mime="text/csv")

st.markdown("## Specification sheet")
labels = dict(zip(view["config_id"], view["vehicle_label"]))
chosen_id = st.selectbox("Open a configuration", list(labels), format_func=labels.get)
row = view[view["config_id"] == chosen_id].iloc[0]

left, right = st.columns([1, 1.3])
with left:
    ui.show_image_or_plate(row)
    st.markdown(ui.status_badges(row), unsafe_allow_html=True)
    st.markdown("###### Provenance")
    st.markdown(f"**Source:** {row['source_name']}")
    urls = [u.strip() for u in str(row["source_url"]).split("|") if u.strip()]
    for u in urls:
        st.markdown(f"[{u}]({u})")
    if pd.notna(row["source_label"]) and row["source_label"]:
        st.caption(f"Original source label: “{row['source_label']}”")
    if pd.notna(row["quality_flags"]) and row["quality_flags"]:
        ui.note("<b>Data-quality flags:</b> " + "; ".join(str(row["quality_flags"]).split(";")))
with right:
    st.markdown(ui.spec_panel(row), unsafe_allow_html=True)
    if row["aspiration_basis"] == "assumed_na":
        st.caption("Aspiration is assumed naturally aspirated: the source text has no forced-induction marker.")
    if row["engine_layout"] == "Rotary":
        st.caption("Per-litre metrics are not calculated for rotary engines (displacement is quoted inconsistently).")
