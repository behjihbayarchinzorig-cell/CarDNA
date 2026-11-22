# CarDNA

An automotive engineering data app for Japanese performance cars (1980 to 2010), built with Streamlit, Pandas, NumPy, Plotly and Requests.

Every row is one vehicle configuration with its source URL and a verification status. Nothing is estimated or invented: if a source does not report a value, the field stays empty and the app says "not reported".

## Current data status (read this first)

- `data/raw/starter_manual.csv` holds **3 configurations** (Toyota Supra A80, three markets and engines). Each value was read from the cited page, and units were converted by the pipeline. Their status is `source_reported`, not `manually_verified`: nobody has compared them against a manufacturer document.
- That is far smaller than the 50 to 100 vehicles the project aims for. The app works with any amount of data, and charts that need more rows say so instead of drawing misleading statistics.
- The gor3a dataset is not imported yet. Its release (`vehicle-data-csv.zip`, `vehicle-data-json.zip`, `vehicles.sqlite`) is normalized into several linked tables, and the exact files and columns were not inspected. A joiner has to be written against the real files.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Pages

| Page | What it does |
|---|---|
| Overview | Totals, engine layouts, power by manufacturer, power against weight, featured cars, findings, data quality, references |
| Car Explorer | Search and filter, open the full specification and sources of any configuration, download the filtered rows |
| Engine Lab | Power per litre, torque, displacement, naturally aspirated vs turbocharged, inline-4 / inline-6 / V6 / V8 |
| Car Comparison | Two to four configurations side by side, with charts |
| Evolution | Pick a model and compare its generations |

## Data pipeline

```
data/raw/*.csv, *.json  ->  src/data_collection.py  ->  src/data_cleaning.py  ->  data/processed/cardna.csv
```

```bash
python -m src.data_collection                  # rebuild the processed dataset
python -m src.data_collection --check-nhtsa    # also check make/model names against NHTSA (needs internet)
```

What the cleaning step does:

1. **Column mapping.** Common column names (`brand`, `hp`, `year`, ...) are mapped to the CarDNA schema. Only unit-explicit names are guessed; a bare `torque` is ignored because it could be Nm or lb-ft.
2. **Unit conversion.** PS, kW, lb-ft, kgf-m, litres, pounds and mph are converted to hp, Nm, cc, kg and km/h. A value a source reported directly is never overwritten.
3. **Normalization.** Consistent labels: `Inline-6`, `V8`, `Flat-4`, `Rotary`; `Naturally aspirated`, `Turbocharged`; `RWD`, `FWD`, `AWD`.
4. **Plausibility checks.** Out-of-range values and rows without a source URL are marked `needs_review`.
5. **Duplicates.** Rows with the same make, model, generation, trim, market, year, engine code and transmission are merged. When sources differ by more than a tolerance (3% for power, torque, weight and top speed), the most trusted source's value is kept and the row becomes `conflict_flagged` with a note.
6. **Metrics.** `power_density_hp_per_l = hp / litres` and `power_to_weight_hp_per_t = hp / tonnes`, left empty when an input is missing.

Verification statuses: `manually_verified`, `cross_checked` (two sources agree), `source_reported`, `needs_review`, `conflict_flagged`. Averages and rankings exclude the last two.

### Adding a source

1. Put a CSV (or a JSON list of records) in `data/raw/`.
2. Make sure each row has `source_url` and `source_name`, or add `<filename>.meta.json` next to the file:

```json
{
  "source_name": "cardata.wiki",
  "source_url": "https://cardata.wiki/",
  "column_map": {"kerb_weight": "weight_kg"}
}
```

3. Set its trust level in `SOURCE_PRIORITY` in `src/data_cleaning.py`.
4. Run `python -m src.data_collection` and read the report, which lists any columns it ignored.

Check each source's terms before collecting from it. Use downloadable datasets and public APIs, and do not scrape sites that do not allow it.

## Data sources

- **gor3a/vehicle-makes-models**: <https://github.com/gor3a/vehicle-makes-models>. Compiled from autoevolution.com, Open Database License 1.0. Not imported yet.
- **NHTSA vPIC API**: <https://vpic.nhtsa.dot.gov/api/>. Covers vehicles sold in the US and has no per-configuration power, torque or weight, so it is only used to check names.
- **cardata.wiki** and **autoseeker.eu**: listed in the project brief; their formats and licensing have not been checked yet.
- Starter rows: the pages cited in `source_url` inside `data/raw/starter_manual.csv`.

If you publish a database built from the gor3a data, the ODbL requires crediting the source and sharing your derived database under the same license.

## Photos

The app shows a typographic plate for any car without a photo. To add a photo, save it as `assets/images/<make>-<model>-<generation>.jpg` in lowercase with dashes, for example `toyota-supra-a80-jza80.jpg`. Only add images you have the right to use.

## Tests

```bash
python -m unittest discover -s tests -v
```

13 tests cover unit conversion, normalization, duplicate merging, conflict flagging, metric formulas (including missing and zero inputs) and the small-sample safeguards. The fixtures in `tests/` are synthetic and are never written to `data/`.

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository (the processed `data/processed/cardna.csv` is committed so the app starts with data).
2. Go to <https://share.streamlit.io>, sign in with GitHub and choose **Create app**.
3. Select the repository and branch, and set the main file to `app.py`.
4. Deploy. Dependencies install from `requirements.txt`. No secrets are needed.
5. After changing anything in `data/raw/`, run `python -m src.data_collection` locally and commit the updated `data/processed/cardna.csv`.

## Project layout

```
app.py                   entry point and Overview page
pages/                   Car Explorer, Engine Lab, Car Comparison, Evolution
src/data_collection.py   read raw files, map columns, run the pipeline, NHTSA check
src/data_cleaning.py     units, normalization, duplicates, conflicts, metrics
src/analysis.py          calculations with small-sample safeguards (no Streamlit)
src/ui.py                theme, charts, specification panel
data/raw, data/processed source files and the cleaned output
assets/images            optional photos
tests/                   unit tests
.streamlit/config.toml   dark theme colours
```
