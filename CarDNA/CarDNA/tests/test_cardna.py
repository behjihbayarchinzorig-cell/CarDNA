"""Run with:  python -m pytest -q"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import analysis, data_cleaning as dc, data_collection as col

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- units
def test_unit_conversions():
    df = pd.DataFrame({"weight_kg": [2000.0], "torque_nm": [100.0], "horsepower_hp": [100.0],
                       "top_speed_kmh": [100.0], "displacement_cc": [3.0]})
    out = dc.convert_units(df, {"weight_kg": "lb", "torque_nm": "lb-ft", "horsepower_hp": "kW",
                                "top_speed_kmh": "mph", "displacement_cc": "L"})
    assert out.at[0, "weight_kg"] == pytest.approx(907.18, abs=0.01)
    assert out.at[0, "torque_nm"] == pytest.approx(135.58, abs=0.01)
    assert out.at[0, "horsepower_hp"] == pytest.approx(135.96, abs=0.01)
    assert out.at[0, "top_speed_kmh"] == pytest.approx(160.93, abs=0.01)
    assert out.at[0, "displacement_cc"] == 3000

def test_unknown_unit_raises():
    with pytest.raises(ValueError):
        dc.convert_units(pd.DataFrame({"weight_kg": [1.0]}), {"weight_kg": "stone"})

# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("label,make,model,expected,basis", [
    ("3.0L Twin Turbo 6MT RWD (330 HP)", "Toyota", "Supra", "Turbocharged", "label"),
    ("2.5L T 5MT AWD (230 HP)", "Subaru", "Impreza", "Turbocharged", "label"),
    ("3.8L V6 TT 6AT (480 HP)", "Nissan", "GT-R", "Turbocharged", "label"),
    ("2.0i 16V 5MT AWD (265 HP)", "Mitsubishi", "Lancer Evolution", "Turbocharged", "model_rule"),
    ("2.0L 6MT RWD (250 HP)", "Honda", "S2000", "Naturally aspirated", "assumed_na"),
    ("GT-S 1.8L 5MT", "Honda", "Integra", "Naturally aspirated", "assumed_na"),   # "GT" must not mean turbo
])
def test_aspiration(label, make, model, expected, basis):
    assert dc.parse_aspiration(label, make, model) == (expected, basis)

def test_layout():
    assert dc.parse_layout("3.5L V6 6MT", "Nissan", "350Z", 6)[0] == "V6"
    assert dc.parse_layout("2.0L 6MT", "Honda", "S2000", 4)[0] == "Inline-4"
    assert dc.parse_layout("2.5L T 5MT", "Subaru", "Impreza", 4)[0] == "Flat-4"
    assert dc.parse_layout("1.3L 6MT", "Mazda", "RX-8", 2)[0] == "Rotary"

def test_transmission():
    assert dc.parse_transmission("5-speed manual") == ("Manual", 5.0)
    assert dc.parse_transmission("4-Speed automatic") == ("Automatic", 4.0)
    assert dc.parse_transmission("Manual, 5 Speed") == ("Manual", 5.0)
    assert dc.parse_transmission("CVT")[0] == "CVT"
    assert dc.parse_transmission(np.nan, "3.0L 4AT RWD (220 HP)") == ("Automatic", 4.0)

# ---------------------------------------------------------------- cleaning
def _row(**kw):
    base = dict(make="X", model="Y", generation="Y (1990)", displacement_cc=2000, aspiration="Turbocharged",
                transmission="Manual", gear_count=5, horsepower_hp=200, torque_nm=300, weight_kg=1300,
                acceleration_0_100=6.0, top_speed_kmh=230, drivetrain="Rear Wheel Drive",
                engine_layout="Inline-4", source_label="", source_name="A", source_url="u",
                verification_status=np.nan, quality_flags=np.nan)
    base.update(kw)
    return base

def test_implausible_weight_is_blanked_and_flagged():
    out = dc.add_plausibility_flags(pd.DataFrame([_row(weight_kg=320)]))
    assert pd.isna(out.at[0, "weight_kg"])
    assert "weight_kg_implausible(320)" in out.at[0, "quality_flags"]

def test_duplicates_merge_and_conflicts_flag():
    df = pd.DataFrame([_row(), _row(source_name="B", weight_kg=1500)])
    out = dc.deduplicate_and_flag(dc.add_plausibility_flags(df))
    assert len(out) == 1 and out.at[0, "n_source_rows"] == 2
    assert out.at[0, "verification_status"] == "conflict_flagged"
    assert "conflict_weight_kg" in out.at[0, "quality_flags"]

def test_agreeing_sources_are_cross_checked_and_single_is_unverified():
    two = dc.deduplicate_and_flag(dc.add_plausibility_flags(pd.DataFrame([_row(), _row(source_name="B")])))
    assert two.at[0, "verification_status"] == "cross_checked"
    one = dc.deduplicate_and_flag(dc.add_plausibility_flags(pd.DataFrame([_row()])))
    assert one.at[0, "verification_status"] == "unverified_single_source"

def test_blank_drivetrain_filled_from_duplicate_but_distinct_drivetrains_kept():
    out = dc.deduplicate_and_flag(dc.add_plausibility_flags(
        pd.DataFrame([_row(drivetrain=np.nan), _row()])))
    assert len(out) == 1 and out.at[0, "drivetrain"] == "Rear Wheel Drive"
    out = dc.deduplicate_and_flag(dc.add_plausibility_flags(
        pd.DataFrame([_row(drivetrain="All Wheel Drive"), _row()])))
    assert len(out) == 2

# ---------------------------------------------------------------- analysis
def test_metrics_and_missing_values():
    df = pd.DataFrame({"displacement_cc": [2000, np.nan, 2000, 1300], "horsepower_hp": [200, 200, 200, 230],
                       "weight_kg": [1000, 1000, np.nan, 1300], "torque_nm": [300] * 4,
                       "engine_layout": ["Inline-4", "Inline-4", "Inline-4", "Rotary"],
                       "production_year_end": [np.nan] * 4, "production_year": [1990] * 4,
                       "aspiration": ["Turbocharged"] * 4, "transmission": ["Manual"] * 4,
                       "gear_count": [5] * 4, "make": ["X"] * 4, "generation": ["g"] * 4,})
    out = analysis.add_metrics(df)
    assert out.at[0, "power_density_hp_per_l"] == pytest.approx(100)
    assert out.at[0, "power_to_weight_hp_per_t"] == pytest.approx(200)
    assert pd.isna(out.at[1, "power_density_hp_per_l"])          # missing displacement
    assert pd.isna(out.at[2, "power_to_weight_hp_per_t"])        # missing weight
    assert pd.isna(out.at[3, "power_density_hp_per_l"])          # rotary excluded

def test_grouped_stats_ignores_missing_and_marks_small_groups():
    df = pd.DataFrame({"g": ["a"] * 4 + ["b", "c"], "v": [1, 2, 3, np.nan, 10, np.nan]})
    s = analysis.grouped_stats(df, "g", "v").set_index("g")
    assert s.at["a", "n"] == 3 and s.at["a", "mean"] == 2 and bool(s.at["a", "reliable"])
    assert s.at["b", "n"] == 1 and not bool(s.at["b", "reliable"])   # too small -> marked unreliable
    assert "c" not in s.index                                      # only NaN -> not reported

def test_linear_fit_needs_enough_points():
    assert analysis.linear_fit(pd.Series([1, 2]), pd.Series([1, 2])) is None
    fit = analysis.linear_fit(pd.Series(range(6)), pd.Series([2 * i + 1 for i in range(6)]))
    assert fit["slope"] == pytest.approx(2) and fit["r"] == pytest.approx(1)

# ---------------------------------------------------------------- real dataset
@pytest.fixture(scope="module")
def data():
    return analysis.load_dataset()

def test_dataset_schema_and_size(data):
    assert all(c in data.columns for c in dc.SCHEMA_COLUMNS)
    assert 50 <= len(data) <= 100
    assert data["config_id"].is_unique
    assert data["source_url"].notna().all() and data["source_name"].notna().all()
    assert set(data["verification_status"]) <= {"unverified_single_source", "needs_review", "conflict_flagged",
                                                "cross_checked", "verified_manual"}

def test_dataset_values_are_plausible(data):
    assert data["production_year"].between(1978, 2010).all()
    assert data["horsepower_hp"].between(*dc.PLAUSIBLE_RANGES["horsepower_hp"]).all()
    w = data["weight_kg"].dropna()
    assert w.between(*dc.PLAUSIBLE_RANGES["weight_kg"]).all()
    assert (data.loc[data["engine_layout"] == "Rotary", "power_density_hp_per_l"].isna()).all()

def test_derived_metrics_match_manual_calculation(data):
    r = data.dropna(subset=["displacement_cc", "weight_kg"]).query("engine_layout != 'Rotary'").iloc[0]
    assert r["power_density_hp_per_l"] == pytest.approx(r["horsepower_hp"] / (r["displacement_cc"] / 1000))
    assert r["power_to_weight_hp_per_t"] == pytest.approx(r["horsepower_hp"] / (r["weight_kg"] / 1000))

def test_findings_are_generated_from_data(data):
    f = analysis.dataset_findings(data)
    assert len(f) >= 3 and all("n =" in x or "of " in x for x in f)

def test_generation_summary(data):
    s = analysis.generation_summary(data, "Mitsubishi", "Lancer Evolution")
    assert len(s) >= 5 and s["production_year"].is_monotonic_increasing

# ---------------------------------------------------------------- pages
@pytest.mark.parametrize("path", ["app.py"] + [str(Path(p).relative_to(ROOT)) for p in sorted(glob.glob(str(ROOT / "pages/*.py")))])
def test_pages_run_without_error(path):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / path), default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]

def test_explorer_search_filters_and_empty_state():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "pages/1_Car_Explorer.py"), default_timeout=60).run()
    at.sidebar.text_input[0].set_value("supra").run()
    assert not at.exception
    assert any("match" in m.value for m in at.markdown)
    at.sidebar.text_input[0].set_value("zzzz-no-such-car").run()
    assert not at.exception and any("No configurations match" in m.value for m in at.markdown)

def test_comparison_needs_two_selections():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "pages/3_Car_Comparison.py"), default_timeout=60).run()
    at.multiselect[0].set_value([]).run()
    assert not at.exception and any("at least two" in m.value for m in at.markdown)
