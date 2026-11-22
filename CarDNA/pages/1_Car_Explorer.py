"""Car Explorer: search, filter and open the full specification of any configuration."""
import streamlit as st

from src import ui

df = ui.load_data()
ui.page_header("Car Explorer", "Search the dataset, narrow it with filters, then open any configuration "
                               "to see every specification and its sources.")

query = st.text_input("Search make, model or generation", placeholder="supra, a80, nsx")

c1, c2, c3, c4 = st.columns(4)
makes = c1.multiselect("Manufacturer", sorted(df["make"].dropna().unique()))
drivetrains = c2.multiselect("Drivetrain", sorted(df["drivetrain"].dropna().unique()))
layouts = c3.multiselect("Engine layout", sorted(df["engine_layout"].dropna().unique()))
aspirations = c4.multiselect("Aspiration", sorted(df["aspiration"].dropna().unique()))

years = df["production_year"].dropna()
year_range, include_unknown = None, True
if len(years) and years.min() < years.max():
    year_range = st.slider("Production year", int(years.min()), int(years.max()),
                           (int(years.min()), int(years.max())))
    include_unknown = st.checkbox("Include configurations with no production year", value=True)

found = df.copy()
if query:
    text = found[["make", "model", "generation", "trim"]].fillna("").agg(" ".join, axis=1).str.lower()
    for word in query.lower().split():
        found = found[text.loc[found.index].str.contains(word, regex=False)]
for column, chosen in [("make", makes), ("drivetrain", drivetrains),
                       ("engine_layout", layouts), ("aspiration", aspirations)]:
    if chosen:
        found = found[found[column].isin(chosen)]
if year_range:
    in_range = found["production_year"].between(*year_range)
    found = found[in_range | (found["production_year"].isna() & include_unknown)]

st.markdown(f"## {len(found)} of {len(df)} configurations")
if found.empty:
    ui.empty_state("Nothing matches these filters. Remove a filter or shorten the search text.")
    st.stop()

table = found[["make", "model", "generation", "trim", "market", "production_year", "engine_layout",
               "aspiration", "horsepower_hp", "torque_nm", "weight_kg", "drivetrain", "verification_status"]]
st.dataframe(table, hide_index=True, width="stretch")
st.download_button("Download these rows as CSV", found.to_csv(index=False).encode("utf-8"),
                   "cardna_filtered.csv", "text/csv")

st.markdown("## Full specification")
labels = ui.vehicle_label_map(found)
chosen = st.selectbox("Configuration", list(labels), format_func=labels.get)
row = found.loc[chosen]
left, right = st.columns([1, 1.4])
with left:
    ui.show_image_or_plate(row)
with right:
    st.markdown(ui.spec_panel(row), unsafe_allow_html=True)
