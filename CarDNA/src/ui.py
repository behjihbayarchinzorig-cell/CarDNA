"""
Shared look and helpers for every CarDNA page.

Design direction: a premium automotive engineering publication.
Graphite background, off-white and silver type, one restrained red accent,
Barlow Condensed for headings (industrial signage), Source Serif 4 for text.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from src import analysis, data_collection

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "assets" / "images"

GRAPHITE = "#14161A"
CHARCOAL = "#1D2025"
LINE = "#2C3037"
OFFWHITE = "#E8E6E1"
SILVER = "#9AA0A8"
RED = "#C8352E"
MUTED = "#4A4F56"
ASPIRATION_COLORS = {
    "Naturally aspirated": SILVER,
    "Turbocharged": RED,
    "Supercharged": "#B08D57",
    "Twin-charged": "#6F8FA8",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap');
.stApp, .stMarkdown, .stCaption, p, li { font-family: 'Source Serif 4', Georgia, serif; }
.stApp h1, .stApp h2, .stApp h3 {
  font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; font-weight: 600;
  letter-spacing: .005em; line-height: 1.05; color: __OFF__;
}
.stApp h1 { font-size: clamp(2.6rem, 6vw, 4.6rem); margin: 0 0 .5rem; }
.stApp h2 { font-size: clamp(1.7rem, 3vw, 2.3rem); margin-top: 3.2rem; padding-top: 1.2rem; border-top: 1px solid __LINE__; }
.stApp h3 { font-size: 1.5rem; margin-top: 1.6rem; }
.block-container { max-width: 1080px; padding: 3rem 1.5rem 5rem; }
header[data-testid="stHeader"] { background: transparent; }
a { color: __OFF__; text-decoration-color: __RED__; text-underline-offset: 3px; }
.cd-deck { font-size: 1.2rem; color: __SILVER__; max-width: 34em; line-height: 1.55; margin: 0 0 1.2rem; }
.cd-note { border-left: 3px solid __RED__; padding: .7rem 1rem; background: __CHARCOAL__; color: __SILVER__;
  margin: 1.4rem 0 2rem; font-size: .98rem; line-height: 1.55; }
.cd-note b { color: __OFF__; }
.cd-spec { width: 100%; border-collapse: collapse; margin-top: .6rem; font-size: .95rem; }
.cd-spec td { padding: .4rem 0; border-bottom: 1px solid __LINE__; vertical-align: top; overflow-wrap: anywhere; }
.cd-spec td:first-child { color: __SILVER__; width: 44%; font-family: 'Barlow Condensed', sans-serif; font-size: 1.05rem; }
.cd-plate { border: 1px solid __LINE__; border-left: 3px solid __RED__; padding: 1.2rem; min-height: 150px;
  display: flex; flex-direction: column; justify-content: flex-end; background: __CHARCOAL__; }
.cd-plate b { font-family: 'Barlow Condensed', sans-serif; font-size: 2.1rem; font-weight: 600; line-height: 1; }
.cd-plate span { color: __SILVER__; }
[data-testid="stMetricValue"] { font-family: 'Barlow Condensed', sans-serif; font-size: 2.6rem; font-weight: 600; }
[data-testid="stMetricLabel"] p { color: __SILVER__; }
@media (max-width: 640px) { .block-container { padding: 2rem 1rem 4rem; } .stApp h2 { margin-top: 2.4rem; } }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
"""


def configure() -> None:
    """Page settings and styles. Called once, in app.py, before navigation."""
    st.set_page_config(page_title="CarDNA", layout="wide", initial_sidebar_state="collapsed")
    css = _CSS
    for token, value in {"__OFF__": OFFWHITE, "__LINE__": LINE, "__RED__": RED,
                         "__SILVER__": SILVER, "__CHARCOAL__": CHARCOAL}.items():
        css = css.replace(token, value)
    st.markdown(css, unsafe_allow_html=True)


def page_header(title: str, deck: str) -> None:
    st.markdown(f"# {title}")
    st.markdown(f'<p class="cd-deck">{html.escape(deck)}</p>', unsafe_allow_html=True)


def note(text_html: str) -> None:
    """A highlighted note. Pass trusted HTML only (never user input)."""
    st.markdown(f'<div class="cd-note">{text_html}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading dataset")
def _read(path: str, modified: float) -> pd.DataFrame:
    return pd.read_csv(path)


def load_data() -> pd.DataFrame:
    """Load data/processed/cardna.csv, building it from data/raw/ the first time."""
    path = data_collection.PROCESSED_PATH
    if not path.exists():
        data_collection.run_pipeline()
    if not path.exists():
        st.error("No data found. Add a CSV or JSON file to data/raw/ and run "
                 "`python -m src.data_collection`. See the README for the file format.")
        st.stop()
    return _read(str(path), path.stat().st_mtime)


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def style_fig(fig, height: int = 400):
    """Apply the CarDNA look to any Plotly figure."""
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Barlow Condensed, Arial Narrow, sans-serif", size=15, color=OFFWHITE),
        title=dict(font=dict(size=21)), height=height, margin=dict(l=10, r=20, t=55, b=10),
        legend_title_text=None, colorway=[RED, SILVER, "#B08D57", "#6F8FA8", MUTED],
    )
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    return fig


def show_chart(fig, how_to_read: str, height: int = 400) -> None:
    """Draw a chart followed by one plain-language sentence on how to read it."""
    st.plotly_chart(style_fig(fig, height), width="stretch")
    st.caption(how_to_read)


def empty_state(message: str) -> None:
    note(html.escape(message))


# --------------------------------------------------------------------------
# Vehicle display
# --------------------------------------------------------------------------
def _fmt(value, unit: str = "", digits: int = 0) -> str:
    if pd.isna(value):
        return "not reported"
    if isinstance(value, (int, float)):
        return f"{value:,.{digits}f}{unit}"
    return html.escape(str(value))


def spec_panel(row) -> str:
    """Specification table as HTML. All values are escaped."""
    hp = _fmt(row.get("horsepower_hp"), " hp") if pd.isna(row.get("horsepower_rpm")) else \
        f"{row['horsepower_hp']:,.0f} hp at {row['horsepower_rpm']:,.0f} rpm"
    tq = _fmt(row.get("torque_nm"), " Nm") if pd.isna(row.get("torque_rpm")) else \
        f"{row['torque_nm']:,.0f} Nm at {row['torque_rpm']:,.0f} rpm"
    rows = [
        ("Engine", _fmt(row.get("engine_code")) + (f", {html.escape(str(row['engine_layout']))}"
                                                   if pd.notna(row.get("engine_layout")) else "")),
        ("Displacement", _fmt(row.get("displacement_cc"), " cc")),
        ("Aspiration", _fmt(row.get("aspiration"))),
        ("Power", hp if pd.notna(row.get("horsepower_hp")) else "not reported"),
        ("Torque", tq if pd.notna(row.get("torque_nm")) else "not reported"),
        ("Drivetrain", _fmt(row.get("drivetrain"))),
        ("Weight", _fmt(row.get("weight_kg"), " kg")),
        ("Power per litre", _fmt(row.get("power_density_hp_per_l"), " hp/l")),
        ("Power to weight", _fmt(row.get("power_to_weight_hp_per_t"), " hp/t")),
        ("0 to 100 km/h", _fmt(row.get("acceleration_0_100"), " s", 1)),
        ("Top speed", _fmt(row.get("top_speed_kmh"), " km/h")),
        ("Status", html.escape(str(row.get("verification_status", "")).replace("_", " "))),
    ]
    links = [u.strip() for u in str(row.get("source_url", "")).split("|") if u.strip().startswith("http")]
    if links:
        rows.append(("Sources", "<br>".join(
            f'<a href="{html.escape(u)}" target="_blank" rel="noopener noreferrer">{html.escape(u)}</a>' for u in links)))
    if pd.notna(row.get("conflict_note")):
        rows.append(("Conflict", html.escape(str(row["conflict_note"]))))
    body = "".join(f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows)
    return f'<table class="cd-spec">{body}</table>'


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _image_for(row) -> Path | None:
    names = [_slug(f"{row.get('make')}-{row.get('model')}-{row.get('generation')}"),
             _slug(f"{row.get('make')}-{row.get('model')}")]
    for name in names:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = IMAGES_DIR / f"{name}{ext}"
            if candidate.exists():
                return candidate
    return None


def show_image_or_plate(row) -> None:
    """Show a photo from assets/images/ if one exists, otherwise a typographic plate."""
    image = _image_for(row)
    if image:
        st.image(str(image), width="stretch")
        return
    gen = f"<br><span>{html.escape(str(row['generation']))}</span>" if pd.notna(row.get("generation")) else ""
    st.markdown(f'<div class="cd-plate"><span>{html.escape(str(row.get("make", "")))}</span>'
                f'<b>{html.escape(str(row.get("model", "")))}</b>{gen}</div>', unsafe_allow_html=True)


def vehicle_label_map(df: pd.DataFrame) -> dict:
    """index -> readable, unique label for select boxes."""
    labels = {i: analysis.car_label(row) for i, row in df.iterrows()}
    seen: dict[str, int] = {}
    for i, text in labels.items():
        seen[text] = seen.get(text, 0) + 1
        if seen[text] > 1:
            labels[i] = f"{text} (#{seen[text]})"
    return labels
