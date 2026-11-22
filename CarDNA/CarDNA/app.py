"""
CarDNA - entry point and Overview page.

Run locally:   streamlit run app.py
The other four pages live in pages/ and are wired together with st.navigation
so the first tab is called "Overview" instead of "app".
"""
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from src import analysis, ui


def overview() -> None:
    ui.setup_page("Overview")
    df = ui.load_data()

    ui.page_header(
        "CarDNA · Automotive engineering data",
        "The engineering behind Japanese performance",
        "Horsepower, torque, displacement, weight and layout for enthusiast cars "
        "from 1980 to 2010 — measured, compared and honestly caveated.",
    )
    flagged = int((df["verification_status"].isin(["conflict_flagged", "needs_review"])).sum())
    ui.note(f"<b>Data status.</b> {len(df)} configurations from a single secondary source "
            f"(gor3a/vehicle-makes-models, derived from autoevolution.com). "
            f"<b>None have been manually verified</b>; {flagged} are flagged for conflicts or implausible values. "
            "Treat figures as source-reported, not authoritative.")

    # ---- headline numbers ------------------------------------------------
    hp = df["horsepower_hp"].dropna()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Vehicle configurations", f"{len(df)}")
    c2.metric("Manufacturers", f"{df['make'].nunique()}")
    c3.metric("Average horsepower", f"{hp.mean():.0f} hp" if len(hp) else "—",
              help=f"Mean of {len(hp)} configurations with a power figure (median {hp.median():.0f} hp).")
    n_pw = int(df["power_to_weight_hp_per_t"].notna().sum())
    c4.metric("With power-to-weight", f"{n_pw}", help="Configurations with both power and weight, "
              "the only ones power-to-weight can be calculated for.")

    # ---- distributions ---------------------------------------------------
    st.markdown("## Engine configurations")
    left, right = st.columns(2)
    with left:
        counts = df["engine_layout"].value_counts().reset_index()
        counts.columns = ["engine_layout", "configs"]
        fig = px.bar(counts, x="configs", y="engine_layout", orientation="h",
                     title="Configurations by engine layout", text="configs")
        fig.update_traces(marker_color=ui.RED, textposition="outside")
        fig.update_yaxes(categoryorder="total ascending", title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
    with right:
        stats = analysis.avg_hp_by_make(df)
        fig = go.Figure(go.Bar(
            x=stats["mean"], y=stats["make"], orientation="h",
            text=[f"{m:.0f} hp · n={n}" for m, n in zip(stats["mean"], stats["n"])],
            marker_color=[ui.SILVER if r else "#4a4f56" for r in stats["reliable"]],
            textposition="outside"))
        fig.update_layout(title="Average horsepower by manufacturer")
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(title=None, range=[0, stats["mean"].max() * 1.35])
        st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
        st.caption(f"Darker bars = fewer than {analysis.MIN_GROUP_SIZE} configurations: treat as anecdotal.")

    # ---- featured vehicles -------------------------------------------------
    st.markdown("## Featured vehicles")
    st.caption("Top power-to-weight among configurations with no conflict or review flag; one per model.")
    pool = analysis.clean_rows(df).dropna(subset=["power_to_weight_hp_per_t"])
    featured = (pool.sort_values("power_to_weight_hp_per_t", ascending=False)
                .drop_duplicates(["make", "model"]).head(3))
    cols = st.columns(3)
    for col, (_, row) in zip(cols, featured.iterrows()):
        with col:
            ui.show_image_or_plate(row)
            st.markdown(ui.spec_panel(row), unsafe_allow_html=True)

    # ---- findings -----------------------------------------------------------
    st.markdown("## What the data says")
    for line in analysis.dataset_findings(df):
        st.markdown(f"- {line}")

    # ---- data quality -------------------------------------------------------
    st.markdown("## Data quality")
    with st.expander("Verification status and field coverage", expanded=False):
        a, b = st.columns(2)
        status = df["verification_status"].value_counts().rename_axis("status").reset_index(name="configs")
        a.dataframe(status, hide_index=True, width="stretch")
        cov_cols = ["horsepower_hp", "torque_nm", "displacement_cc", "weight_kg",
                    "acceleration_0_100", "top_speed_kmh", "gear_count", "trim", "engine_code",
                    "horsepower_rpm", "torque_rpm"]
        b.dataframe(analysis.coverage(df, cov_cols), hide_index=True, width="stretch")
        st.caption("Empty columns (engine code, power/torque RPM) are not provided by the current source "
                   "and are left blank rather than guessed. See the README for how to add sources.")


pages = [
    st.Page(overview, title="Overview", default=True),
    st.Page("pages/1_Car_Explorer.py", title="Car Explorer"),
    st.Page("pages/2_Engine_Lab.py", title="Engine Lab"),
    st.Page("pages/3_Car_Comparison.py", title="Car Comparison"),
    st.Page("pages/4_Evolution.py", title="Evolution"),
]
st.navigation(pages, position="top").run()
