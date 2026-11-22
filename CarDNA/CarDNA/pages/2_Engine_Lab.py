"""Engine Lab - power density, torque, displacement, aspiration and architecture."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analysis, ui

ui.setup_page("Engine Lab")
df = ui.load_data()

ui.page_header("Engine Lab", "What makes the power",
               "How displacement, aspiration and engine architecture relate to output — "
               "with the sample size shown next to every comparison.")

st.sidebar.markdown("### Engine Lab options")
exclude_assumed = st.sidebar.checkbox(
    "Exclude assumed-NA rows", value=False,
    help="Rows whose aspiration is 'assumed naturally aspirated' because the source text has "
         "no turbo marker. Tick to compare only rows where aspiration is stated.")
exclude_flagged = st.sidebar.checkbox("Exclude flagged rows", value=True,
                                      help="Drops rows with conflicts or implausible values.")
data = df.copy()
if exclude_assumed:
    data = data[data["aspiration_basis"] != "assumed_na"]
if exclude_flagged:
    data = analysis.clean_rows(data)
st.sidebar.caption(f"{len(data)} of {len(df)} configurations in use.")

ASP = ui.ASPIRATION_COLORS


def with_fit(fig, x, y, frame, name):
    """Add a least-squares line (computed with numpy) and return the fit stats."""
    fit = analysis.linear_fit(frame[x], frame[y])
    if fit:
        xs = np.array([fit["x_min"], fit["x_max"]])
        fig.add_trace(go.Scatter(x=xs, y=fit["slope"] * xs + fit["intercept"], mode="lines",
                                 line=dict(color=ui.OFFWHITE, width=1, dash="dot"), name=name))
    return fit


tabs = st.tabs(["Power density", "Torque vs displacement", "Displacement", "Aspiration", "Architecture", "Weight vs power"])

with tabs[0]:
    sub, dropped = analysis.usable_rows(data, ["power_density_hp_per_l"])
    fig = px.strip(sub, x="make", y="power_density_hp_per_l", color="aspiration", color_discrete_map=ASP,
                   hover_name="vehicle_label", title="Horsepower per litre by manufacturer")
    fig.update_traces(marker=dict(size=9, line=dict(width=0)))
    fig.update_xaxes(title=None); fig.update_yaxes(title="hp per litre")
    st.plotly_chart(ui.style_fig(fig, 460), width="stretch")
    st.caption(f"{len(sub)} configurations plotted; {dropped} excluded (missing inputs, or rotary engines whose "
               "displacement is quoted inconsistently).")

with tabs[1]:
    sub, dropped = analysis.usable_rows(data, ["displacement_cc", "torque_nm"])
    fig = px.scatter(sub, x="displacement_cc", y="torque_nm", color="aspiration", color_discrete_map=ASP,
                     hover_name="vehicle_label", title="Torque versus displacement")
    fig.update_traces(marker=dict(size=9))
    fit = with_fit(fig, "displacement_cc", "torque_nm", sub, "Linear fit")
    fig.update_xaxes(title="Displacement (cc)"); fig.update_yaxes(title="Torque (Nm)")
    st.plotly_chart(ui.style_fig(fig, 460), width="stretch")
    if fit:
        st.caption(f"n = {fit['n']} · r = {fit['r']:.2f} · R² = {fit['r2']:.2f}. "
                   "Forced induction shifts torque far more than displacement does, so one line fits poorly.")
    st.caption(f"{dropped} configurations excluded for missing displacement or torque.")

with tabs[2]:
    sub, dropped = analysis.usable_rows(data, ["displacement_cc"])
    fig = px.histogram(sub, x="displacement_cc", nbins=14, color="aspiration", color_discrete_map=ASP,
                       title="Engine displacement distribution")
    fig.update_xaxes(title="Displacement (cc)"); fig.update_yaxes(title="Configurations")
    st.plotly_chart(ui.style_fig(fig, 420), width="stretch")
    st.caption(f"n = {len(sub)}; {dropped} excluded. Rotary displacement is the source's quoted figure and is not "
               "directly comparable to piston engines.")

with tabs[3]:
    metric_names = {"power_density_hp_per_l": "Power density (hp/L)", "horsepower_hp": "Horsepower",
                    "torque_nm": "Torque (Nm)", "power_to_weight_hp_per_t": "Power-to-weight (hp/t)"}
    metric = st.selectbox("Metric", list(metric_names), format_func=metric_names.get)
    stats = analysis.aspiration_comparison(data, metric)
    st.dataframe(stats.assign(mean=stats["mean"].round(1), median=stats["median"].round(1))
                 .rename(columns={"aspiration": "Aspiration", "n": "n"}),
                 hide_index=True, width="stretch")
    sub, dropped = analysis.usable_rows(data, [metric])
    fig = px.box(sub, x="aspiration", y=metric, color="aspiration", color_discrete_map=ASP, points="all",
                 hover_name="vehicle_label", title=f"{metric_names[metric]}: naturally aspirated vs forced induction")
    fig.update_xaxes(title=None); fig.update_yaxes(title=metric_names[metric]); fig.update_layout(showlegend=False)
    st.plotly_chart(ui.style_fig(fig, 440), width="stretch")
    n_assumed = int((sub["aspiration_basis"] == "assumed_na").sum())
    ui.note(f"{n_assumed} of {len(sub)} plotted rows are <b>assumed</b> naturally aspirated (no turbo marker in the "
            "source text). Use the sidebar option to exclude them. Groups with n &lt; "
            f"{analysis.MIN_GROUP_SIZE} are not reliable.")

with tabs[4]:
    layouts = ["Inline-4", "Inline-6", "V6", "V8"]
    available = [l for l in layouts if l in set(data["engine_layout"])]
    metric = st.selectbox("Metric ", list(metric_names), format_func=metric_names.get, key="arch_metric")
    stats = analysis.layout_comparison(data, metric, layouts)
    sub, dropped = analysis.usable_rows(data[data["engine_layout"].isin(layouts)], [metric])
    fig = px.box(sub, x="engine_layout", y=metric, color="engine_layout", points="all",
                 category_orders={"engine_layout": available}, hover_name="vehicle_label",
                 title=f"{metric_names[metric]} by engine architecture")
    fig.update_xaxes(title=None); fig.update_yaxes(title=metric_names[metric]); fig.update_layout(showlegend=False)
    st.plotly_chart(ui.style_fig(fig, 440), width="stretch")
    st.dataframe(stats.assign(mean=stats["mean"].round(1), median=stats["median"].round(1)),
                 hide_index=True, width="stretch")
    small = stats[~stats["reliable"]]["engine_layout"].tolist()
    if small:
        ui.note(f"Low sample size (n &lt; {analysis.MIN_GROUP_SIZE}) for: {', '.join(small)}. Do not generalise from these.")
    st.caption("Flat-4/Flat-6 (Subaru) and rotary engines are analysed on their own in the Explorer; this tab "
               "compares the four architectures asked for.")

with tabs[5]:
    sub, dropped = analysis.usable_rows(data, ["weight_kg", "horsepower_hp"])
    fig = px.scatter(sub, x="weight_kg", y="horsepower_hp", color="aspiration", color_discrete_map=ASP,
                     hover_name="vehicle_label", title="Horsepower versus weight")
    fig.update_traces(marker=dict(size=9))
    fit = with_fit(fig, "weight_kg", "horsepower_hp", sub, "Linear fit")
    fig.update_xaxes(title="Weight (kg)"); fig.update_yaxes(title="Horsepower")
    st.plotly_chart(ui.style_fig(fig, 460), width="stretch")
    if fit:
        st.caption(f"n = {fit['n']} · r = {fit['r']:.2f}. {dropped} excluded for missing or implausible weight. "
                   "The dataset is a hand-picked set of performance cars, so this is not a statement about cars in general.")
