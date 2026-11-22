# CarDNA

An automotive engineering and data-exploration app for **Japanese performance and enthusiast cars, ~1980–2010**.
It relates horsepower, torque, displacement, engine layout, aspiration, weight and drivetrain, and is deliberately
honest about data quality: missing values stay missing, odd values are flagged, and inferred values are labelled.

Built with Python, Streamlit, Pandas, NumPy, Plotly and Requests.

## ⚠️ Read this first: data status

* The starter dataset (**98 configurations**, `data/processed/cardna_dataset.csv`) comes from **one secondary source**:
  [gor3a/vehicle-makes-models](https://github.com/gor3a/vehicle-makes-models), which in turn compiled its data from autoevolution.com.
* **No row has been manually verified against a primary source** (manufacturer documents, homologation papers).
  Rows are labelled `unverified_single_source` unless the pipeline found a problem (`needs_review`, `conflict_flagged`).
  The label `verified_manual` exists for rows you check yourself, but none are shipped.
* Specs on enthusiast sites vary by market, model year and measurement method. Treat figures as *source-reported*.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The processed dataset is committed, so the app runs immediately. To rebuild it from scratch:

```bash
python -m src.data_collection --download     # downloads gor3a engines.csv (~5 MB), selects the starter set
python -m src.data_cleaning                  # cleans, merges, flags -> data/processed/cardna_dataset.csv
python -m pytest -q                          # 29 tests (cleaning, analysis, every page)
```

## Pages

| Page | What it does |
|---|---|
| **Overview** | Totals, engine-layout distribution, average hp by manufacturer (with sample sizes), featured vehicles, findings computed from the data, data-quality panel |
| **Car Explorer** | Search + filters (manufacturer, years, drivetrain, layout, aspiration), full spec sheet with provenance and flags, CSV download |
| **Engine Lab** | hp/litre, torque vs displacement, displacement histogram, NA vs forced induction, I4 vs I6 vs V6 vs V8, weight vs power |
| **Car Comparison** | 2–6 configurations side by side, performance charts, missing values shown as — |
| **Evolution** | Pick a model, compare generations: hp, torque, displacement, weight, drivetrain, first-to-last change |

## Calculations

* **Power density** = `horsepower_hp / (displacement_cc / 1000)`  (hp per litre)
* **Power-to-weight** = `horsepower_hp / (weight_kg / 1000)`  (hp per tonne)
* A metric is **NaN** whenever an input is missing. Averages ignore NaN and show **n** (rows actually used).
  Groups with n < 3 are marked unreliable. Trend lines are computed with NumPy and show n and r.
* **Rotary engines (RX-7, RX-8) get no per-litre metrics**: the source quotes rotary displacement inconsistently
  (e.g. 1.3 L nominal for the RX-8 but 2.6 L "equivalent" for the FD RX-7).

## Data schema

One row = one vehicle configuration. Required columns: `make, model, generation, trim, market, production_year,
engine_code, engine_layout, cylinders, displacement_cc, aspiration, horsepower_hp, horsepower_rpm, torque_nm,
torque_rpm, drivetrain, transmission, gear_count, weight_kg, acceleration_0_100, top_speed_kmh, source_url,
source_name, verification_status`. Extra trust columns: `config_id, production_year_end, body_type, source_label,
aspiration_basis, engine_layout_basis, quality_flags, n_source_rows`.

Conventions and known gaps in the current source:

* `horsepower_hp` is **metric horsepower** (PS). Imports in kW/bhp are converted (`convert_units`).
* `production_year` is the **start year of the generation** (the source does not give per-configuration years).
* `generation` is the source's own label, e.g. `Supra (1993)`. Chassis codes (A80, FD3S…) are not in the source and were not added.
* `market` is `Unspecified`; `engine_code`, `horsepower_rpm`, `torque_rpm` are blank; `trim` is filled only when found in the source text.
* `aspiration_basis`: `label` (stated), `model_rule` (model is always turbo, e.g. Lancer Evolution) or **`assumed_na`**
  (no turbo marker found, so *assumed* naturally aspirated). `engine_layout_basis` shows when layout was inferred
  (Subaru → flat, otherwise inline from cylinder count).
* `source_url` points to the dataset file, not a per-car page (the source has no per-car URLs).

### Quality flags

`weight_kg_implausible(…)` etc. (value outside a plausible range → blanked, raw value kept in the flag),
`label_hp_mismatch(…)` (numeric power disagrees with the power in the text label by >8%),
`displacement_label_mismatch(…)`, `conflict_<field>(a vs b)` (duplicate rows or different sources disagree beyond tolerance).

## Data sources: what was checked

| Source | Finding | Used? |
|---|---|---|
| [gor3a/vehicle-makes-models](https://github.com/gor3a/vehicle-makes-models) | CSV/JSON/SQLite, ~31.5k engine rows, hp/torque/weight/0-100/top speed. Code MIT, data ODbL 1.0, **compiled from autoevolution.com** | **Yes** (starter set) |
| [cardata.wiki](https://cardata.wiki/) | Free per-make/model CSV downloads, CC BY 4.0, 35k+ variants, mostly UK-market specs. Paid API (£20/month) | **No**: not reachable from the build environment. Use the import workflow below |
| [autoseeker.eu](https://autoseeker.eu/en/data/) | CSV/JSON, CC BY 4.0, but only ~281 *current* EU models (WLTP, EV-oriented) | No: irrelevant to 1980–2010 |
| [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/) | US government make/model/VIN-decode API. Not reachable from the build environment, and not designed to supply hp/torque/weight for classic cars | No (untested) |

**No website was scraped.**

### Licensing caveats (please read)

* gor3a's data is under **ODbL 1.0 (attribution + share-alike)**. `cardna_dataset.csv` is a derived database, so if you
  publish it publicly, keep it under ODbL and credit "gor3a/vehicle-makes-models" and "autoevolution.com".
* gor3a states that its data was compiled from autoevolution.com. **I did not verify that autoevolution's terms allow
  that reuse**, and gor3a cannot grant rights it may not hold. Before commercial use or large-scale redistribution, check
  autoevolution's terms or replace the source with one you have verified rights to.

## Adding or verifying data

Cross-source checking is built in: when two sources describe the same configuration and disagree beyond tolerance,
the merged row is flagged `conflict_flagged`; when they agree it becomes `cross_checked`.

**Import a CSV/JSON** (e.g. a cardata.wiki download — check its licence and column names first):

```bash
echo '{"BHP": "horsepower_hp", "Torque (Nm)": "torque_nm", "Kerb weight (kg)": "weight_kg"}' > map.json
echo '{"horsepower_hp": "bhp"}' > units.json
python -m src.data_collection --import-file downloads/toyota.csv \
    --source-name "cardata.wiki" --source-url "https://cardata.wiki/toyota" \
    --column-map map.json --units units.json
python -m src.data_cleaning
```

The column map keys must match the file's real headers (they differ per source). Supported units are listed in
`src/data_cleaning.py` (`UNIT_FACTORS`). **Manual entry:** run `python -m src.data_collection --template`, fill
`data/raw/manual_import_template.csv` (one configuration per row, `source_url` required) and import it with `--verified`
*only* if you checked each row against a primary source.

## Photography

No photographs are bundled (none could be sourced with a verified licence). Cards show a typographic plate instead.
To add a photo, save it as `assets/images/<make>-<model>.jpg` in lowercase with dashes (e.g. `toyota-supra.jpg`) and
optionally list `file,credit` in `assets/images/credits.csv`. Wikimedia Commons is a good source of freely licensed images.

## Design

The look follows the brief (premium automotive engineering publication: graphite, silver, restrained red, Lora serif
headlines, IBM Plex for text and numbers). The brief named a "UI Lora" direction without further spec, so this is an
interpretation of the written description. Streamlit-native components plus custom CSS in `src/ui.py`; responsive
down to phone width.

## Deploy to Streamlit Community Cloud

1. Push this folder to a **public GitHub repository** (`git init && git add . && git commit -m "CarDNA" && git remote add origin <url> && git push -u origin main`).
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **Create app**.
3. Select the repository, branch `main`, main file path **`app.py`**, then **Deploy**.
4. No secrets or API keys are needed. If you later add any, put them in the app's *Secrets* settings, never in the repo.

All paths are relative; `requirements.txt` pins only minimum versions (Streamlit ≥ 1.50 for `st.navigation(position="top")`
and `width="stretch"`).

## Repository layout

```
app.py                  entry point + Overview page, navigation
pages/                  Car Explorer, Engine Lab, Car Comparison, Evolution
src/data_collection.py  download, starter selection, CSV/JSON import, CLI
src/data_cleaning.py    schema, units, parsing, plausibility flags, dedupe/conflicts, build
src/analysis.py         metrics, safe statistics, generation analysis, findings
src/ui.py               theme CSS, Plotly style, spec panels, cached loader
tests/                  pytest suite
data/raw/               downloads (engines.csv is git-ignored), imports/, manual template
data/processed/         cardna_dataset.csv, build_report.json
assets/images/          optional photographs
```
