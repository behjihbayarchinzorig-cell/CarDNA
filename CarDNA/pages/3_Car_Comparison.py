"""Car Comparison: pick two to four configurations and compare them side by side."""
import pandas as pd
import plotly.express as px
import streamlit as st

from src import ui

df = ui.load_data()
ui.page_header("Car Comparison", "Choose two to four configurations to see their specifications "
                                 "and performance side by side.")

labels = ui.vehicle_label_map(df)
picked = st.multiselect("Configurations", list(labels), format_func=labels.get, max_selections=4)
if len(picked) < 2:
    ui.empty_state("Pick at least two configurations to compare.")
    st.stop()

chosen = df.loc[picked].copy()
chosen["car"] = [labels[i] for i in picked]

st.markdown("## Specifications")
fields = {
    "engine_code": "Engine", "engine_layout": "Layout", "displacement_cc": "Displacement (cc)",
    "aspiration": "Aspiration", "horsepower_hp": "Power (hp)", "torque_nm": "Torque (Nm)",
    "drivetrain": "Drivetrain", "transmission": "Transmission", "weight_kg": "Weight (kg)",
    "power_density_hp_per_l": "Power per litre (hp/l)", "power_to_weight_hp_per_t": "Power to weight (hp/t)",
    "acceleration_0_100": "0 to 100 km/h (s)", "top_speed_kmh": "Top speed (km/h)",
    "verification_status": "Status",
}
side = chosen.set_index("car")[list(fields)].rename(columns=fields).T
side = side.apply(lambda col: col.map(lambda v: "not reported" if pd.isna(v) else
                                      (f"{v:,.1f}" if isinstance(v, float) else str(v))))
st.dataframe(side, width="stretch")

st.markdown("## Performance")
metrics = [("horsepower_hp", "Power (hp)"), ("torque_nm", "Torque (Nm)"), ("weight_kg", "Weight (kg)"),
           ("power_to_weight_hp_per_t", "Power to weight (hp per tonne)")]
cols = st.columns(2)
for slot, (column, title) in zip(cols * 2, metrics):
    with slot:
        data = chosen.dropna(subset=[column])
        if data.empty:
            st.caption(f"{title}: none of the selected configurations report this value.")
            continue
        fig = px.bar(data, x=column, y="car", orientation="h", title=title, text=column)
        fig.update_traces(marker_color=ui.RED, texttemplate="%{text:,.0f}", textposition="outside")
        fig.update_yaxes(title=None, autorange="reversed")
        fig.update_xaxes(title=None, range=[0, data[column].max() * 1.25])
        missing = len(chosen) - len(data)
        ui.show_chart(fig, "Longer bar means a higher value." +
                      (f" {missing} selected configuration(s) do not report this value." if missing else ""), 280)
