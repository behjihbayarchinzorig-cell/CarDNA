"""Evolution - how one model changed from generation to generation."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analysis, ui

ui.setup_page("Evolution")
df = ui.load_data()

ui.page_header("Evolution", "Generation by generation",
               "Choose a model and see how power, torque, displacement, weight and drivetrain changed.")

models = df.groupby(["make", "model"])["generation"].nunique().reset_index(name="generations")
models = models[models["generations"] >= 1].sort_values(["make", "model"])
options = [f"{r.make} {r.model}" for r in models.itertuples()]
pairs = {f"{r.make} {r.model}": (r.make, r.model) for r in models.itertuples()}
default_idx = max(range(len(models)), key=lambda i: models.iloc[i]["generations"])
choice = st.selectbox("Model", options, index=default_idx)
make, model = pairs[choice]

summary = analysis.generation_summary(df, make, model)
if len(summary) < 2:
    ui.note(f"{choice} has only {len(summary)} generation in the dataset, so there is no evolution to show. "
            "Pick a model with two or more generations.")

st.markdown("## Generations")
show = summary.rename(columns={
    "production_year": "Start year", "generation": "Generation", "configs": "Configs",
    "hp_max": "Max hp", "hp_median": "Median hp", "torque_max": "Max Nm", "torque_median": "Median Nm",
    "displacement_max_cc": "Max cc", "weight_median_kg": "Median kg", "power_to_weight_max": "Best hp/t",
    "drivetrains": "Drivetrains", "aspirations": "Aspiration"})
st.dataframe(show.round(0), hide_index=True, width="stretch")

if len(summary) >= 2:
    st.markdown("## Change, first to last generation")
    cols = {"hp_max": "Max power (hp)", "torque_max": "Max torque (Nm)",
            "displacement_max_cc": "Max displacement (cc)", "weight_median_kg": "Median weight (kg)"}
    changes = analysis.generation_changes(summary, list(cols))
    changes["metric"] = changes["metric"].map(cols)
    first, last = summary.iloc[0]["generation"], summary.iloc[-1]["generation"]
    st.caption(f"{first} → {last}. Blank = the data needed for a comparison is missing for at least one generation.")
    st.dataframe(changes.rename(columns={"metric": "Metric", "first": "First", "last": "Last",
                                         "change": "Change", "change_pct": "Change %"}).round(1),
                 hide_index=True, width="stretch")

    st.markdown("## Charts")
    tabs = st.tabs(["Power & torque", "Displacement & weight", "Drivetrain"])

    def line(columns: dict, title: str, ytitle: str):
        fig = go.Figure()
        for (col, name), colour in zip(columns.items(), [ui.RED, ui.SILVER, "#c9b48a"]):
            s = summary.dropna(subset=[col])
            if s.empty:
                continue
            fig.add_trace(go.Scatter(x=s["production_year"], y=s[col], mode="lines+markers", name=name,
                                     line=dict(color=colour, width=2), marker=dict(size=9),
                                     hovertext=s["generation"]))
        fig.update_layout(title=title)
        fig.update_xaxes(title="Generation start year", dtick=2); fig.update_yaxes(title=ytitle)
        return ui.style_fig(fig, 420)

    with tabs[0]:
        st.plotly_chart(line({"hp_max": "Max hp", "hp_median": "Median hp", "torque_max": "Max Nm"},
                             f"{choice}: power and torque", "hp / Nm"), width="stretch")
    with tabs[1]:
        st.plotly_chart(line({"displacement_max_cc": "Max displacement (cc)", "weight_median_kg": "Median weight (kg)"},
                             f"{choice}: displacement and weight", "cc / kg"), width="stretch")
        if summary["weight_median_kg"].isna().any():
            st.caption("Generations without a weight figure are left out of the weight line.")
    with tabs[2]:
        drive = (df[(df["make"] == make) & (df["model"] == model)]
                 .groupby(["production_year", "generation", "drivetrain"]).size().unstack(fill_value=0))
        st.dataframe(drive, width="stretch")
        st.caption("Number of configurations per drivetrain in each generation.")

st.markdown("## Configurations")
detail = df[(df["make"] == make) & (df["model"] == model)].sort_values(["production_year", "horsepower_hp"])
st.dataframe(detail[["generation", "engine_layout", "displacement_cc", "aspiration", "horsepower_hp", "torque_nm",
                     "drivetrain", "transmission", "weight_kg", "verification_status"]],
             hide_index=True, width="stretch")
st.caption("A 'generation' here is the source's own grouping (named by its start year). Chassis codes such as "
           "A80 or FD3S are not in the source and have not been added.")
