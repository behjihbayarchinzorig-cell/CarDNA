"""Evolution: how a model changed from one generation to the next."""
import plotly.express as px
import streamlit as st

from src import analysis, ui

df = ui.load_data()
ui.page_header("Evolution", "Pick a model to see how power, torque, engine size, weight and drivetrain "
                            "changed across its generations.")

make = st.selectbox("Manufacturer", sorted(df["make"].dropna().unique()))
models = sorted(df.loc[df["make"] == make, "model"].dropna().unique())
model = st.selectbox("Model", models)

data = df[(df["make"] == make) & (df["model"] == model)].copy()
table = analysis.generation_table(df, make, model)
if data["generation"].nunique() < 2 and len(data) < 2:
    ui.empty_state("This model has fewer than two configurations in the dataset, so there is nothing to compare yet.")

st.markdown("## Generations")
st.dataframe(table.rename(columns={
    "generation": "Generation", "configurations": "Configurations", "years": "Production years",
    "horsepower_hp": "Power (hp)", "torque_nm": "Torque (Nm)", "displacement_cc": "Displacement (cc)",
    "weight_kg": "Weight (kg)", "drivetrain": "Drivetrain"}), hide_index=True, width="stretch")
st.caption("A range such as 276-321 means the generation has several configurations. "
           "A dash means no configuration reports that value.")

st.markdown("## Changes over time")
data["car"] = data.apply(analysis.car_label, axis=1)
timeline = data.dropna(subset=["production_year"])
if timeline.empty:
    ui.empty_state("No configuration of this model reports a production year, so the timeline cannot be drawn.")
else:
    metrics = [("horsepower_hp", "Power (hp)"), ("torque_nm", "Torque (Nm)"),
               ("displacement_cc", "Displacement (cc)"), ("weight_kg", "Weight (kg)")]
    cols = st.columns(2)
    for slot, (column, title) in zip(cols * 2, metrics):
        with slot:
            points = timeline.dropna(subset=[column]).sort_values("production_year")
            if points.empty:
                st.caption(f"{title}: no values reported with a production year.")
                continue
            fig = px.line(points, x="production_year", y=column, markers=True, hover_name="car", title=title)
            fig.update_traces(line_color=ui.RED, marker=dict(size=10, color=ui.RED))
            fig.update_xaxes(title=None, dtick=1)
            fig.update_yaxes(title=None)
            ui.show_chart(fig, f"{len(points)} configuration(s) with this value and a production year.", 300)
