"""
CarDNA - entry point and Overview page.

Run locally:   streamlit run app.py
The other four pages live in pages/ and are registered with st.navigation,
so the first tab is called "Overview" instead of "app".
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analysis, ui

ui.configure()  # must run before any other Streamlit call

REFERENCES = [
    ("gor3a/vehicle-makes-models",
     "Open dataset of makes, models, generations and engine specifications, compiled from autoevolution.com "
     "and licensed under the Open Database License 1.0.",
     "https://github.com/gor3a/vehicle-makes-models"),
    ("Open Database License 1.0",
     "Terms for the dataset above: credit the source, and share any derived database under the same license.",
     "https://opendatacommons.org/licenses/odbl/1-0/"),
    ("NHTSA vPIC API",
     "US government vehicle product information catalog. Used only to check that make and model names exist.",
     "https://vpic.nhtsa.dot.gov/api/"),
]


def overview() -> None:
    df = ui.load_data()
    clean = analysis.clean_rows(df)

    ui.page_header("What makes Japanese performance cars fast",
                   "Power, torque, engine size, weight and layout for enthusiast cars from 1980 to 2010, "
                   "with the source and verification status of every number.")

    flagged = int(df["verification_status"].isin(analysis.FLAGGED).sum())
    ui.note(f"<b>Data status.</b> {len(df)} configurations loaded. "
            f"{int((df['verification_status'] == 'manually_verified').sum())} are manually verified, "
            f"{flagged} are flagged for conflicts or review. Everything else is reported by its source and "
            "not independently checked. Empty fields mean the source did not report that value.")

    hp = clean["horsepower_hp"].dropna()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Configurations", f"{len(df)}")
    c2.metric("Manufacturers", f"{df['make'].nunique()}")
    c3.metric("Average power", f"{hp.mean():.0f} hp" if len(hp) else "no data",
              help=f"Mean of {len(hp)} unflagged configurations with a power figure.")
    n_pw = int(df["power_to_weight_hp_per_t"].notna().sum())
    c4.metric("With power-to-weight", f"{n_pw}",
              help="Configurations with both power and weight, the only ones it can be calculated for.")

    st.markdown("## Engines in the dataset")
    left, right = st.columns(2)
    with left:
        counts = df["engine_layout"].dropna().value_counts().reset_index()
        counts.columns = ["engine_layout", "configurations"]
        if len(counts):
            fig = px.bar(counts, x="configurations", y="engine_layout", orientation="h",
                         title="Configurations by engine layout", text="configurations")
            fig.update_traces(marker_color=ui.RED, textposition="outside")
            fig.update_yaxes(categoryorder="total ascending", title=None)
            fig.update_xaxes(title=None)
            ui.show_chart(fig, "Each bar counts how many configurations use that layout, such as "
                               "Inline-6 or V8.", 340)
        else:
            ui.empty_state("No configuration reports an engine layout yet.")
    with right:
        stats = analysis.avg_hp_by_make(df)
        if len(stats):
            fig = go.Figure(go.Bar(
                x=stats["mean"], y=stats["make"], orientation="h",
                text=[f"{m:.0f} hp, n={n}" for m, n in zip(stats["mean"], stats["n"])],
                marker_color=[ui.SILVER if r else ui.MUTED for r in stats["reliable"]],
                textposition="outside"))
            fig.update_layout(title="Average power by manufacturer")
            fig.update_yaxes(autorange="reversed", title=None)
            fig.update_xaxes(title=None, range=[0, stats["mean"].max() * 1.45])
            ui.show_chart(fig, f"Longer bar means more power on average. Dark bars rest on fewer than "
                               f"{analysis.MIN_GROUP_SIZE} configurations (n), so treat them as anecdotes.", 340)
        else:
            ui.empty_state("No unflagged configuration reports power yet.")

    st.markdown("## Power against weight")
    plot = clean.dropna(subset=["horsepower_hp", "weight_kg"]).assign(
        car=lambda d: d.apply(analysis.car_label, axis=1))
    if len(plot):
        fig = px.scatter(plot, x="weight_kg", y="horsepower_hp", color="aspiration", hover_name="car",
                         color_discrete_map=ui.ASPIRATION_COLORS, title="Horsepower against weight")
        fig.update_xaxes(title="Weight (kg)")
        fig.update_yaxes(title="Power (hp)")
        fig.update_traces(marker=dict(size=11))
        ui.show_chart(fig, f"Each dot is one car ({len(plot)} shown). Higher and further left means more "
                           "power in a lighter car.", 420)
    else:
        ui.empty_state("This chart needs configurations that report both power and weight.")

    st.markdown("## Featured vehicles")
    st.caption("Highest power-to-weight among unflagged configurations, one per model.")
    pool = clean.dropna(subset=["power_to_weight_hp_per_t"])
    featured = (pool.sort_values("power_to_weight_hp_per_t", ascending=False)
                .drop_duplicates(["make", "model"]).head(3))
    if len(featured):
        for col, (_, row) in zip(st.columns(3), featured.iterrows()):
            with col:
                ui.show_image_or_plate(row)
                st.markdown(ui.spec_panel(row), unsafe_allow_html=True)
    else:
        ui.empty_state("No configuration has both power and weight, so nothing can be featured yet.")

    st.markdown("## What the data says")
    for line in analysis.dataset_findings(df):
        st.markdown(f"- {line}")

    st.markdown("## Data quality")
    with st.expander("Verification status and field coverage"):
        a, b = st.columns(2)
        status = df["verification_status"].value_counts().rename_axis("status").reset_index(name="configurations")
        a.dataframe(status, hide_index=True, width="stretch")
        fields = ["horsepower_hp", "torque_nm", "displacement_cc", "weight_kg", "acceleration_0_100",
                  "top_speed_kmh", "gear_count", "trim", "engine_code", "horsepower_rpm", "torque_rpm"]
        b.dataframe(analysis.coverage(df, fields), hide_index=True, width="stretch")

    st.markdown("## References")
    for name, description, url in REFERENCES:
        st.markdown(f"- [{name}]({url}). {description}")
    sources = sorted({u.strip() for cell in df["source_url"].dropna() for u in str(cell).split("|") if u.strip()})
    if sources:
        with st.expander(f"Source pages for individual configurations ({len(sources)})"):
            for url in sources:
                st.markdown(f"- {url}")


pages = [
    st.Page(overview, title="Overview", default=True),
    st.Page("pages/1_Car_Explorer.py", title="Car Explorer"),
    st.Page("pages/2_Engine_Lab.py", title="Engine Lab"),
    st.Page("pages/3_Car_Comparison.py", title="Car Comparison"),
    st.Page("pages/4_Evolution.py", title="Evolution"),
]
st.navigation(pages, position="top").run()
