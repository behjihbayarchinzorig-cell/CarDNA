"""Car Comparison - side-by-side specifications and charts for 2-6 configurations."""
import pandas as pd
import plotly.express as px
import streamlit as st

from src import analysis, ui

ui.setup_page("Car Comparison")
df = ui.load_data()

ui.page_header("Car Comparison", "Side by side",
               "Pick two to six configurations. Missing values are shown as — and are never filled in.")

labels = dict(zip(df["config_id"], df["vehicle_label"]))
default = (analysis.clean_rows(df).dropna(subset=["power_to_weight_hp_per_t"])
           .sort_values("power_to_weight_hp_per_t", ascending=False)
           .drop_duplicates(["make", "model"]).head(3)["config_id"].tolist())
picked = st.multiselect("Configurations to compare", list(labels), default=default,
                        format_func=labels.get, max_selections=6)
if len(picked) < 2:
    ui.note("Select at least two configurations to compare.")
    st.stop()

sel = df.set_index("config_id").loc[picked].reset_index()
sel["short"] = [f"{r.make} {r.model} {int(r.production_year)}" + (f" ({r.horsepower_hp:.0f} hp)" if pd.notna(r.horsepower_hp) else "")
                for r in sel.itertuples()]

st.markdown("## Specifications")
rows = [
    ("Production year", "production_year", "", 0), ("Engine layout", "engine_layout", "", 0),
    ("Displacement (cc)", "displacement_cc", "", 0), ("Aspiration", "aspiration", "", 0),
    ("Power (hp)", "horsepower_hp", "", 0), ("Torque (Nm)", "torque_nm", "", 0),
    ("Drivetrain", "drivetrain", "", 0), ("Transmission", "transmission", "", 0),
    ("Gears", "gear_count", "", 0), ("Weight (kg)", "weight_kg", "", 0),
    ("0–100 km/h (s)", "acceleration_0_100", "", 1), ("Top speed (km/h)", "top_speed_kmh", "", 0),
    ("Power density (hp/L)", "power_density_hp_per_l", "", 0),
    ("Power-to-weight (hp/t)", "power_to_weight_hp_per_t", "", 0),
    ("Torque per litre (Nm/L)", "torque_density_nm_per_l", "", 0),
    ("Verification", "verification_status", "", 0),
]
table = pd.DataFrame({r[0]: [ui.fmt(v, r[2], r[3]) for v in sel[r[1]]] for r in rows}, index=sel["short"]).T
st.dataframe(table, width="stretch")

flagged = sel[sel["quality_flags"].fillna("") != ""]
for r in flagged.itertuples():
    ui.note(f"<b>{r.short}</b> — {'; '.join(str(r.quality_flags).split(';'))}")

st.markdown("## Performance charts")
metrics = {"horsepower_hp": "Horsepower", "torque_nm": "Torque (Nm)", "weight_kg": "Weight (kg)",
           "power_to_weight_hp_per_t": "Power-to-weight (hp/t)", "power_density_hp_per_l": "Power density (hp/L)",
           "acceleration_0_100": "0–100 km/h (s)"}
chosen = st.multiselect("Metrics", list(metrics), default=list(metrics)[:4], format_func=metrics.get)
if chosen:
    long = sel.melt(id_vars=["short"], value_vars=chosen, var_name="metric", value_name="value")
    long["metric"] = long["metric"].map(metrics)
    missing = long[long["value"].isna()]
    plot = long.dropna(subset=["value"])
    fig = px.bar(plot, x="short", y="value", color="short", facet_col="metric", facet_col_wrap=2,
                 facet_col_spacing=0.08, facet_row_spacing=0.18, text_auto=".0f")
    fig.update_yaxes(matches=None, showticklabels=True, title=None)
    fig.update_xaxes(title=None, showticklabels=False)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=True, legend_title_text=None)
    st.plotly_chart(ui.style_fig(fig, 260 * ((len(chosen) + 1) // 2) + 120), width="stretch")
    if len(missing):
        ui.note("Not plotted because the value is missing: " +
                "; ".join(f"{r.short} — {r.metric}" for r in missing.itertuples()))

if sel[["weight_kg", "horsepower_hp"]].notna().all(axis=1).sum() >= 2:
    st.markdown("## Power against weight")
    sc = sel.dropna(subset=["weight_kg", "horsepower_hp"])
    fig = px.scatter(sc, x="weight_kg", y="horsepower_hp", color="short", size_max=16)
    fig.update_traces(marker=dict(size=14))
    fig.update_xaxes(title="Weight (kg)"); fig.update_yaxes(title="Horsepower")
    fig.update_layout(legend_title_text=None)
    st.plotly_chart(ui.style_fig(fig, 400), width="stretch")
