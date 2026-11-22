"""
CarDNA - shared interface helpers (Streamlit-native components + custom CSS).

Visual direction: a premium automotive engineering publication.
Graphite backgrounds, muted silver / off-white type, one restrained red accent,
serif editorial headlines (Lora), clean sans body (IBM Plex Sans) and monospaced
numbers (IBM Plex Mono) for technical specifications.
"""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analysis

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "assets" / "images"

GRAPHITE, PANEL, LINE = "#111214", "#17191c", "#2b2e33"
OFFWHITE, SILVER, MUTED, RED = "#ece9e3", "#c3c6cb", "#8b9097", "#b5252b"

ASPIRATION_COLORS = {"Naturally aspirated": "#9aa1a9", "Turbocharged": RED, "Supercharged": "#c9b48a"}
LAYOUT_COLORS = ["#b5252b", "#c3c6cb", "#7d8794", "#c9b48a", "#5b6572", "#e2ded6", "#8f3a3f"]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500;0,600;0,700;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"], .stApp {{ font-family: 'IBM Plex Sans', sans-serif; color: {OFFWHITE}; }}
.stApp {{ background: {GRAPHITE}; }}
.block-container {{ max-width: 1180px; padding-top: 2.2rem; padding-bottom: 5rem; }}

h1, h2, h3 {{ font-family: 'Lora', Georgia, serif !important; color: {OFFWHITE}; letter-spacing: -0.01em; font-weight: 600; }}
h1 {{ font-size: 3rem !important; line-height: 1.05 !important; margin-bottom: .2rem; }}
h2 {{ font-size: 1.7rem !important; margin-top: 2.6rem !important; }}
h3 {{ font-size: 1.2rem !important; }}
p, li, label, .stMarkdown {{ color: {SILVER}; line-height: 1.6; }}
a {{ color: {OFFWHITE}; text-decoration-color: {RED}; text-underline-offset: 3px; }}

.kicker {{ font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: .22em;
           font-size: .72rem; color: {RED}; margin-bottom: .6rem; }}
.lede {{ font-family: 'Lora', serif; font-style: italic; font-size: 1.2rem; color: {SILVER}; max-width: 46rem; margin-bottom: 1.6rem; }}
.rule {{ border: 0; border-top: 1px solid {LINE}; margin: 1.6rem 0; }}
.rule-red {{ border: 0; border-top: 2px solid {RED}; width: 56px; margin: 1.1rem 0 1.6rem 0; }}

/* metrics */
[data-testid="stMetric"] {{ border-top: 1px solid {LINE}; padding-top: .8rem; }}
[data-testid="stMetricLabel"] p {{ font-family:'IBM Plex Mono',monospace; text-transform:uppercase; letter-spacing:.14em; font-size:.68rem !important; color:{MUTED}; }}
[data-testid="stMetricValue"] {{ font-family:'Lora',serif; font-size:2.3rem; color:{OFFWHITE}; }}

/* spec panel */
.spec {{ background:{PANEL}; border-top:2px solid {RED}; padding:1.1rem 1.3rem 1.3rem 1.3rem; margin-bottom:1rem; }}
.spec h4 {{ font-family:'Lora',serif; font-size:1.2rem; color:{OFFWHITE}; margin:0 0 .15rem 0; font-weight:600; }}
.spec .sub {{ font-family:'IBM Plex Mono',monospace; font-size:.72rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.12em; margin-bottom:.8rem; }}
.spec dl {{ display:grid; grid-template-columns: 1fr 1fr; column-gap:1.6rem; margin:0; }}
.spec dt {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.1em; color:{MUTED}; padding-top:.55rem; border-top:1px solid {LINE}; }}
.spec dd {{ font-family:'IBM Plex Mono',monospace; font-size:.95rem; color:{OFFWHITE}; margin:0 0 .35rem 0; }}
.spec dd.na {{ color:#5d6269; }}
.badge {{ display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:.66rem; letter-spacing:.08em; text-transform:uppercase;
          border:1px solid {LINE}; color:{SILVER}; padding:.1rem .45rem; margin-right:.35rem; }}
.badge.warn {{ border-color:{RED}; color:{RED}; }}

/* image placeholder (no photograph available) */
.plate {{ height:170px; background: linear-gradient(180deg,#1b1d20,#141517); border-top:1px solid {LINE};
          display:flex; flex-direction:column; justify-content:flex-end; padding:1rem 1.2rem; margin-bottom:.4rem; }}
.plate .big {{ font-family:'Lora',serif; font-size:1.7rem; color:{OFFWHITE}; line-height:1.1; }}
.plate .small {{ font-family:'IBM Plex Mono',monospace; font-size:.68rem; color:{MUTED}; letter-spacing:.14em; text-transform:uppercase; }}

/* tabs, inputs, tables: quiet, square */
.stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom:1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ background:transparent; padding:.5rem 0; font-family:'IBM Plex Mono',monospace; font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; color:{MUTED}; }}
.stTabs [aria-selected="true"] {{ color:{OFFWHITE}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color:{RED}; }}
[data-baseweb="select"] > div, .stTextInput input {{ border-radius:2px !important; }}
[data-testid="stDataFrame"] {{ border:1px solid {LINE}; border-radius:0; }}
[data-testid="stSidebar"] {{ background:{PANEL}; border-right:1px solid {LINE}; }}
.note {{ border-left:2px solid {RED}; padding:.2rem 0 .2rem .9rem; color:{SILVER}; font-size:.9rem; margin:.8rem 0 1.2rem 0; }}
footer, #MainMenu {{ visibility:hidden; }}

@media (max-width: 760px) {{
  h1 {{ font-size: 2.1rem !important; }}
  .spec dl {{ grid-template-columns: 1fr; }}
  .block-container {{ padding-left:1rem; padding-right:1rem; }}
  [data-testid="stMetricValue"] {{ font-size:1.8rem; }}
}}
</style>
"""


def setup_page(title: str = "CarDNA") -> None:
    """Page config (only the first call per run is allowed) + CSS."""
    try:
        st.set_page_config(page_title=f"{title} · CarDNA", page_icon="🧬", layout="wide")
    except st.errors.StreamlitAPIException:
        pass   # already configured by app.py when running through the navigation
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(kicker: str, title: str, lede: str = "") -> None:
    st.markdown(f'<div class="kicker">{html.escape(kicker)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown('<hr class="rule-red">', unsafe_allow_html=True)
    if lede:
        st.markdown(f'<div class="lede">{html.escape(lede)}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Load the processed dataset once and cache it."""
    if not analysis.DATASET_PATH.exists():
        st.error("Dataset not found. Build it with `python -m src.data_collection --download` "
                 "then `python -m src.data_cleaning`.")
        st.stop()
    return analysis.load_dataset()


def style_fig(fig: go.Figure, height: int = 440) -> go.Figure:
    """Apply the CarDNA look to a Plotly figure."""
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=SILVER, size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.2),
        colorway=LAYOUT_COLORS, hoverlabel=dict(bgcolor=PANEL, font_color=OFFWHITE),
        title=dict(font=dict(family="Lora, serif", size=18, color=OFFWHITE), x=0),
    )
    fig.update_xaxes(gridcolor=LINE, zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zeroline=False, linecolor=LINE)
    return fig


def fmt(value, unit: str = "", digits: int = 0) -> str:
    """Format a number for display; missing values show as an em dash, never 0."""
    if pd.isna(value):
        return "—"
    if isinstance(value, str):
        return value
    return f"{value:,.{digits}f}{unit}"


def spec_panel(row: pd.Series) -> str:
    """HTML technical specification panel for one configuration."""
    def dd(v, unit="", digits=0):
        s = fmt(v, unit, digits)
        return f'<dd class="{"na" if s == "—" else ""}">{html.escape(s)}</dd>'

    items = [
        ("Engine layout", row["engine_layout"], "", 0), ("Cylinders", row["cylinders"], "", 0),
        ("Displacement", row["displacement_cc"], " cc", 0), ("Aspiration", row["aspiration"], "", 0),
        ("Power", row["horsepower_hp"], " hp", 0), ("Torque", row["torque_nm"], " Nm", 0),
        ("Drivetrain", row["drivetrain"], "", 0), ("Transmission", row["transmission"], "", 0),
        ("Gears", row["gear_count"], "", 0), ("Weight", row["weight_kg"], " kg", 0),
        ("0–100 km/h", row["acceleration_0_100"], " s", 1), ("Top speed", row["top_speed_kmh"], " km/h", 0),
        ("Power density", row["power_density_hp_per_l"], " hp/L", 0),
        ("Power-to-weight", row["power_to_weight_hp_per_t"], " hp/t", 0),
        ("Trim", row["trim"], "", 0), ("Engine code", row["engine_code"], "", 0),
    ]
    body = "".join(f"<dt>{html.escape(k)}</dt>{dd(v, u, d)}" for k, v, u, d in items)
    years = fmt(row["production_year"])
    if pd.notna(row["production_year_end"]):
        years += f"–{int(row['production_year_end'])}"
    return (f'<div class="spec"><h4>{html.escape(str(row["make"]))} {html.escape(str(row["model"]))}</h4>'
            f'<div class="sub">{html.escape(str(row["generation"]))} · generation {html.escape(years)}</div>'
            f'<dl>{body}</dl></div>')


def status_badges(row: pd.Series) -> str:
    """Badges that say how much to trust the row."""
    status = str(row["verification_status"]).replace("_", " ")
    warn = row["verification_status"] in ("conflict_flagged", "needs_review")
    badges = [f'<span class="badge {"warn" if warn else ""}">{html.escape(status)}</span>']
    if row.get("aspiration_basis") == "assumed_na":
        badges.append('<span class="badge">aspiration assumed</span>')
    if row.get("engine_layout_basis", "").startswith("inferred"):
        badges.append('<span class="badge">layout inferred</span>')
    return "".join(badges)


def image_for(row: pd.Series) -> Path | None:
    """Return assets/images/<make>-<model>.(jpg|jpeg|png|webp) if you added one."""
    slug = f"{row['make']}-{row['model']}".lower().replace(" ", "-").replace("/", "-")
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = IMAGE_DIR / f"{slug}.{ext}"
        if p.exists():
            return p
    return None


def show_image_or_plate(row: pd.Series) -> None:
    """Photograph if available; otherwise an honest typographic plate (no fake photos)."""
    img = image_for(row)
    if img:
        st.image(str(img), width="stretch")
        credits = IMAGE_DIR / "credits.csv"
        if credits.exists():
            c = pd.read_csv(credits)
            hit = c[c["file"] == img.name]
            if len(hit):
                st.caption(f"Photo: {hit.iloc[0]['credit']}")
    else:
        st.markdown(
            f'<div class="plate"><div class="small">{html.escape(str(row["make"]))} · no photograph added</div>'
            f'<div class="big">{html.escape(str(row["model"]))}</div></div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)
