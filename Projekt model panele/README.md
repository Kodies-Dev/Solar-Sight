# PV production forecasting: technical notes

Hourly PV production model driven by the weather forecast (24-hour horizon). The data pipeline defaults to **Gliwice**. For the project overview, see the [main README](../README.md).

---

## Repository layout

```
.
├── pipeline/                    # Data collection and processing
│   ├── class_weather_api.py     # Historical weather (Open-Meteo)
│   ├── zbieraczka_danych_oze.py # PV production (ENTSO-E / Instrat)
│   ├── pv_capacity_pl.py        # Monthly installed PV capacity in Poland (URE)
│   ├── merge_dataset.py         # Joins both sources into the training set
│   └── miasta.csv               # City registry (coordinates, population)
│
├── forecast/                    # Builds model inputs for prediction
│   ├── google_forecast.py       # Google Weather API forecast (key required)
│   ├── meteo_forecast.py        # Open-Meteo forecast (no key) + solar data
│   └── merge_forecasts.py       # Merges both into the model's input format
│
├── trained_model_usage/
│   └── predicting_mwh.py        # Inference + what-if simulation used by the API
│
├── backend/                     # Flask API (server.py) + test.rest
├── frontend/                    # React + Mapbox dashboard
│
├── data/
│   └── solar_dataset_tauron.csv # Training dataset (produced by the pipeline)
│
├── artifacts/
│   ├── model_bez_lagow.joblib   # Deployed XGBoost model (no lag features)
│   └── model.joblib, model_ok.joblib  # Earlier variants
│
├── notebooks/
│   └── data_analysis.ipynb      # Exploratory data analysis
│
├── main_model.ipynb             # Training and evaluation
└── requirements.txt
```

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Build the training dataset

```bash
cd pipeline
python run_pipeline.py --city Gliwice --start 2023-01-01 --end 2025-12-31
```

> ⚠️ `run_pipeline.py` (the orchestrator) is referenced here but is not in the repository yet. Until it is added, run the three steps below one by one. A ready-made dataset for Gliwice (2023–2025) is in `pipeline/dataset_Gliwice_20230101_20251231.csv`.

The city name must exist in `pipeline/miasta.csv`. To add a city, append a row to that file.

### 3. Train the model

Open `main_model.ipynb` and run all cells.

---

## Data pipeline

### Step 1: PV production (`zbieraczka_danych_oze.py`)

Downloads national hourly PV generation from the ENTSO-E API via [Instrat](https://energy-api.instrat.pl).

National data is scaled down to city level:

```
city_production = PL_production × (city_population / PL_population)
```

The script handles the ENTSO-E reporting change of **13 June 2024**, when resolution switched from 60 minutes to 15 minutes. From that date the values are corrected by a factor of ×0.25.

**Output:** `pipeline/fotowoltaika_godzinowo_{city}_{start}_{end}.csv`

### Step 2: Weather data (`class_weather_api.py`)

Downloads historical hourly data from the [Open-Meteo Archive API](https://archive-api.open-meteo.com/v1/archive).

Downloaded features:

| Column | Description |
|---|---|
| `shortwave_radiation_wm2` | Shortwave radiation [W/m²] |
| `direct_radiation_wm2` | Direct radiation [W/m²] |
| `diffuse_radiation_wm2` | Diffuse radiation [W/m²] |
| `cloud_cover_pct` | Cloud cover [%] |
| `sunshine_pct` | Share of the hour with sunshine [%] |
| `temperature_c` | Temperature [°C] |
| `wind_speed_ms` | Wind speed [m/s] |
| `humidity_pct` | Relative humidity [%] |
| `pressure_hpa` | Air pressure [hPa] |

Engineered features computed locally:

| Column | Description |
|---|---|
| `hour_sin`, `hour_cos` | Cyclic encoding of the hour |
| `doy_sin`, `doy_cos` | Cyclic encoding of the day of year |
| `solar_elevation_deg` | Sun elevation above the horizon (NOAA formula) |
| `installed_pv_mw_pl` | Installed PV capacity in Poland [MW] (`pv_capacity_pl.py`) |

**Output:** `pipeline/weather_{city}_real.csv`

### Step 3: Merge (`merge_dataset.py`)

Joins weather and PV production on a complete hourly UTC grid, which prevents DST gaps. Missing PV hours (the spring clock change) are filled with zero, which is physically correct because they fall at night. After the merge, meta columns are dropped, the target is renamed to `production_mwh`, and the result is saved to `data/solar_dataset_tauron.csv`.

---

## Prediction pipeline (`forecast/`)

Model inputs are built in three steps:

```
1. meteo_forecast.py    → meteo_forecast_YYYYMMDD_HHMM.csv    (solar + weather)
2. google_forecast.py   → google_forecast_YYYYMMDD_HHMM.csv   (weather, higher quality)
3. merge_forecasts.py   → forecast_final.csv                  (ready model input)
```

Google Weather is the **primary** source for weather variables (temperature, wind, humidity, pressure, cloud cover). Open-Meteo is the **only** source of solar data (shortwave, direct and diffuse radiation, sunshine). It is also the fallback whenever Google returns NaN.

The output of `merge_forecasts.py` has **exactly the same columns** as the training data (minus `production_mwh`), so it can go straight into the model.

```bash
cd forecast

# Step 1: solar + weather data from Open-Meteo (no key)
python meteo_forecast.py --hours 24

# Step 2: weather data from Google (key required)
python google_forecast.py --api-key YOUR_KEY --hours 24

# Step 3: merge (automatically picks the newest files)
python merge_forecasts.py --output forecast_final.csv
```

The `--city` parameter (default `Gliwice`) must be listed in `pipeline/miasta.csv`.

> The live API (`backend/server.py`) fetches its forecast directly from Open-Meteo inside `trained_model_usage/predicting_mwh.py`, so it needs no Google key.

---

## Model

**Algorithm:** XGBoost Regressor
**Hyperparameter search:** Optuna (100 trials, scored with TimeSeriesSplit)
**Validation:** 5-fold TimeSeriesSplit, gap = 24 h, test size = 30 days

Deployed model (`artifacts/model_bez_lagow.joblib`, no lag features), chronological 80/20 hold-out, from `main_model.ipynb`:

| Metric | Value |
|---|---|
| MAE | 2.56 MWh |
| RMSE | 5.85 MWh |
| R² | 0.845 |

An earlier variant with lag features reported MAE 0.29 MWh, RMSE 1.37 MWh and R² 0.9873. Lagged production isn't available when forecasting 24 hours ahead, so the API uses the lag-free model.

---

## Adding a city

1. Add a row to `pipeline/miasta.csv`:
   ```
   Katowice,50.2599,19.0216,285000
   ```
2. Run the pipeline with `--city Katowice`.

---

## Changes since the first version

### Rewritten

| Old component | New equivalent | Change |
|---|---|---|
| `API for MWh/zbieraczka_danych_oze.py` | `pipeline/zbieraczka_danych_oze.py` | The city is no longer hard-coded; coordinates and population are read from `miasta.csv` |
| `api_for_weather/class_weather_api.py` | `pipeline/class_weather_api.py` | Same as above; `uv_index` (unavailable in the Open-Meteo archive) replaced with shortwave radiation; `solar_elevation_deg` added |
| `merged_weather_mwh/merge_weather_mwh.py` | `pipeline/merge_dataset.py` + `run_pipeline.py` | Full hourly UTC grid; DST gaps handled; population scaling moved to the source |

### Removed

- `API for MWh/`, replaced by `pipeline/`
- `api_for_weather/`, replaced by `pipeline/`
- `merged_weather_mwh/`, replaced by `pipeline/`
- `data_solar_panel_analysis/`, notebook moved to `notebooks/`
- `main.py`, an empty placeholder
- `data/opis_datasetu_solar.docx`, replaced by this README

---

## Requirements

See `requirements.txt` (pandas, numpy, scikit-learn, optuna, xgboost, seaborn, matplotlib, requests, urllib3, python-dotenv, joblib, flask, flask-cors).

```bash
pip install -r requirements.txt
```
