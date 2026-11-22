"""Engine Lab: power density, torque, displacement, aspiration and engine layout."""
import plotly.express as px
import streamlit as st

from src import analysis, ui

df = ui.load_data()
clean = analysis.clean_rows(df).assign(car=lambda d: d.apply(analysis.car_label, axis=1))
ui.page_header("Engine Lab", "How much an engine makes for its size, and what separates turbocharged "
                             "from naturally aspirated and one layout from another.")
ui.note("Charts use configurations with no conflict or review flag, and only those that report the "
        "values the chart needs. The number of cars behind each chart is stated under it.")

power, torque, size, aspiration, layout = st.tabs(
    ["Power per litre", "Torque", "Displacement", "Aspiration", "Engine layout"])

with power:
    data = clean.dropna(subset=["power_density_hp_per_l"])
    if len(data):
        fig = px.strip(data, x="aspiration", y="power_density_hp_per_l", color="aspiration", hover_name="car",
                       color_discrete_map=ui.ASPIRATION_COLORS, title="Horsepower per litre of displacement")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title="hp per litre")
        fig.update_layout(showlegend=False)
        ui.show_chart(fig, f"Power density is horsepower divided by displacement in litres, so it compares "
                           f"engines of different sizes fairly. Each dot is one car ({len(data)} shown).")
    else:
        ui.empty_state("No configuration reports both power and displacement.")

with torque:
    data = clean.dropna(subset=["torque_nm", "displacement_cc"])
    if len(data):
        fig = px.scatter(data, x="displacement_cc", y="torque_nm", color="aspiration", hover_name="car",
                         color_discrete_map=ui.ASPIRATION_COLORS, title="Torque against displacement")
        fig.update_xaxes(title="Displacement (cc)")
        fig.update_yaxes(title="Torque (Nm)")
        fig.update_traces(marker=dict(size=11))
        corr = analysis.safe_corr(clean, "displacement_cc", "torque_nm")
        extra = (f" Correlation across these cars: {corr:.2f}." if corr is not None else
                 f" A correlation is not calculated below {analysis.MIN_CORRELATION_ROWS} cars.")
        ui.show_chart(fig, f"Each dot is one car ({len(data)} shown). Dots above the crowd get more torque "
                           f"from the same engine size, often through forced induction.{extra}")
    else:
        ui.empty_state("No configuration reports both torque and displacement.")

with size:
    data = clean.dropna(subset=["displacement_cc"])
    if len(data):
        fig = px.histogram(data, x="displacement_cc", nbins=12, title="How engine sizes are distributed")
        fig.update_traces(marker_color=ui.RED)
        fig.update_xaxes(title="Displacement (cc)")
        fig.update_yaxes(title="Configurations")
        ui.show_chart(fig, f"Each bar counts configurations in a size range ({len(data)} in total). "
                           "The tallest bars are the most common engine sizes.")
    else:
        ui.empty_state("No configuration reports displacement.")

with aspiration:
    summary = analysis.aspiration_summary(df)
    if len(summary):
        fig = px.bar(summary, x="aspiration", y="mean_hp_per_litre", color="aspiration", text="n",
                     color_discrete_map=ui.ASPIRATION_COLORS, title="Average horsepower per litre by aspiration")
        fig.update_traces(texttemplate="n=%{text}", textposition="outside")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title="hp per litre")
        fig.update_layout(showlegend=False)
        ui.show_chart(fig, f"Compares engines with and without forced induction. Groups with fewer than "
                           f"{analysis.MIN_GROUP_SIZE} cars are shown for completeness but are not conclusive.")
        st.dataframe(summary.round(1), hide_index=True, width="stretch")
    else:
        ui.empty_state("No configuration reports its aspiration.")

with layout:
    stats = analysis.layout_summary(df, analysis.MAIN_LAYOUTS)
    if len(stats):
        fig = px.bar(stats, x="engine_layout", y="mean", text="n", title="Power per litre by engine layout")
        fig.update_traces(marker_color=[ui.SILVER if r else ui.MUTED for r in stats["reliable"]],
                          texttemplate="n=%{text}", textposition="outside")
        fig.update_xaxes(title=None)
        fig.update_yaxes(title="average hp per litre")
        ui.show_chart(fig, "Compares inline-4, inline-6, V6 and V8 engines. Dark bars rest on fewer than "
                           f"{analysis.MIN_GROUP_SIZE} cars.")
    else:
        ui.empty_state("No configuration with an inline-4, inline-6, V6 or V8 reports power and displacement.")
