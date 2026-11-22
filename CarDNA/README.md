# CarDNA

Streamlit app for exploring car performance from a cleaned dataset.

## Structure

```
CarDNA/
├── app.py                  Main Streamlit application
├── requirements.txt
├── data/
│   ├── raw/                Original data collected from sources
│   └── processed/
│       └── cars.csv        Cleaned dataset used by the app
├── src/
│   ├── data_collection.py  Retrieves data through APIs or permitted scraping
│   ├── data_cleaning.py    Fixes missing values, units, and inconsistent formats
│   └── analysis.py         Calculates performance metrics
└── pages/
    ├── 1_Car_Explorer.py
    ├── 2_Engine_Lab.py
    ├── 3_Car_Comparison.py
    └── 4_Evolution.py
```

## Run

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
