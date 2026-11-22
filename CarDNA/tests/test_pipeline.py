"""
Tests for the data pipeline and analysis (no Streamlit needed).
Run from the project folder:   python -m unittest discover -s tests -v

The rows below are synthetic TEST FIXTURES that exist only to check the code.
They are never written to data/ and never shown in the app.
"""
import unittest

import numpy as np
import pandas as pd

from src import analysis, data_cleaning as dc, data_collection as dcol


def fixture(**overrides):
    row = {"make": "toyota", "model": "TestCar", "generation": "G1", "trim": "T", "market": "Japan",
           "production_year": 1995, "engine_code": "X1", "cylinders": 6, "displacement_cc": 3000,
           "horsepower_hp": 300, "torque_nm": 400, "weight_kg": 1500,
           "source_url": "https://example.test", "source_name": "fixture"}
    row.update(overrides)
    return row


class UnitConversion(unittest.TestCase):
    def test_conversions_fill_empty_targets(self):
        df = dc.build_dataset([pd.DataFrame([fixture(horsepower_hp=np.nan, horsepower_ps=280,
                                                     torque_nm=np.nan, torque_lbft=300,
                                                     weight_kg=np.nan, weight_lb=3000)])])
        r = df.iloc[0]
        self.assertAlmostEqual(r["horsepower_hp"], 276.2, delta=0.1)
        self.assertAlmostEqual(r["torque_nm"], 406.7, delta=0.1)
        self.assertAlmostEqual(r["weight_kg"], 1360.8, delta=0.1)

    def test_reported_value_is_not_overwritten(self):
        df = dc.build_dataset([pd.DataFrame([fixture(horsepower_hp=300, horsepower_ps=999)])])
        self.assertEqual(df.iloc[0]["horsepower_hp"], 300)


class Normalisation(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(dc.normalize_aspiration("Twin Turbo Intercooled"), "Turbocharged")
        self.assertEqual(dc.normalize_aspiration("NA"), "Naturally aspirated")
        self.assertEqual(dc.normalize_drivetrain("Rear-wheel drive"), "RWD")
        self.assertEqual(dc.normalize_drivetrain("4WD"), "AWD")
        self.assertEqual(dc.normalize_layout("inline", 6), "Inline-6")
        self.assertEqual(dc.normalize_layout("V", 8), "V8")
        self.assertEqual(dc.normalize_layout("boxer 4", None), "Flat-4")
        self.assertEqual(dc.normalize_layout("Wankel rotary", 2), "Rotary")
        self.assertEqual(dc.normalize_make("TOYOTA"), "Toyota")


class Duplicates(unittest.TestCase):
    def test_agreeing_sources_are_cross_checked(self):
        a = fixture(source_name="manual"); b = fixture(source_name="gor3a", horsepower_hp=301)
        df = dc.build_dataset([pd.DataFrame([a]), pd.DataFrame([b])])
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["verification_status"], "cross_checked")
        self.assertEqual(df.iloc[0]["horsepower_hp"], 300)  # most trusted source wins

    def test_disagreeing_sources_are_flagged(self):
        a = fixture(source_name="manual"); b = fixture(source_name="gor3a", horsepower_hp=250)
        df = dc.build_dataset([pd.DataFrame([a]), pd.DataFrame([b])])
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["verification_status"], "conflict_flagged")
        self.assertIn("horsepower_hp", df.iloc[0]["conflict_note"])

    def test_implausible_and_sourceless_rows_need_review(self):
        df = dc.build_dataset([pd.DataFrame([fixture(horsepower_hp=9000),
                                             fixture(model="B", source_url=np.nan)])])
        self.assertTrue((df["verification_status"] == "needs_review").all())


class Metrics(unittest.TestCase):
    def test_formulas(self):
        df = dc.build_dataset([pd.DataFrame([fixture()])])
        self.assertAlmostEqual(df.iloc[0]["power_density_hp_per_l"], 100.0)
        self.assertAlmostEqual(df.iloc[0]["power_to_weight_hp_per_t"], 200.0)

    def test_missing_or_zero_inputs_give_nan_not_infinity(self):
        df = dc.build_dataset([pd.DataFrame([fixture(weight_kg=np.nan, model="A"),
                                             fixture(displacement_cc=0, model="B")])])
        self.assertTrue(df["power_to_weight_hp_per_t"].isna().any())
        self.assertFalse(np.isinf(df[["power_density_hp_per_l", "power_to_weight_hp_per_t"]].to_numpy(float)).any())


class Analysis(unittest.TestCase):
    def test_small_groups_are_marked_unreliable(self):
        df = dc.build_dataset([pd.DataFrame([fixture(model=f"M{i}") for i in range(3)])])
        stats = analysis.avg_hp_by_make(df)
        self.assertEqual(int(stats.iloc[0]["n"]), 3)
        self.assertFalse(bool(stats.iloc[0]["reliable"]))

    def test_correlation_needs_enough_rows(self):
        df = dc.build_dataset([pd.DataFrame([fixture(model=f"M{i}") for i in range(3)])])
        self.assertIsNone(analysis.safe_corr(df, "displacement_cc", "torque_nm"))

    def test_empty_dataset_does_not_crash(self):
        empty = dc.build_dataset([])
        self.assertTrue(analysis.avg_hp_by_make(empty).empty)
        self.assertTrue(analysis.dataset_findings(empty))


class StarterData(unittest.TestCase):
    def test_every_starter_row_has_a_source_url(self):
        df = dcol.run_pipeline(out_path=dcol.ROOT / "data" / "processed" / "_test_cardna.csv")
        (dcol.ROOT / "data" / "processed" / "_test_cardna.csv").unlink(missing_ok=True)
        self.assertGreater(len(df), 0)
        self.assertTrue(df["source_url"].notna().all())

    def test_alias_mapping(self):
        mapped = dcol.apply_mapping(pd.DataFrame({"Brand": ["Honda"], "HP": [250], "Year": [2000]}))
        self.assertEqual(list(mapped.columns), ["make", "horsepower_hp", "production_year"])


if __name__ == "__main__":
    unittest.main()
