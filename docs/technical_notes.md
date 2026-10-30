# Technical notes

How the data is built, how the model is trained and how forecasts are produced. For the project overview, see the [main README](../README.md).

All commands run from the repository root after:

```bash
pip install -e .                 # the solarsight package
pip install -r requirements.txt  # plus notebook extras (Optuna, SHAP, plotting)
```

---

## Layout

```
solarsight/
├── config.py               paths (data/, models/) and constants
├── geo.py                  load_city(), load_cities(), solar_elevation_deg()
├── features.py             add_time_features(): hour/day-of-year + sin/cos encodings
├── capacity.py             PV_CAPACITY_PL_MW table, get_capacity_mw(), latest_capacity_mw()
├── ingest/
│   ├── weather_history.py  Open-Meteo archive → data/raw/weather_<city>.csv
│   ├── pv_production.py    ENTSO-E (Instrat) → data/raw/pv_production_<city>_<start>_<end>.csv
│   └── build_dataset.py    joins both → data/processed/dataset_<city>_<start>_<end>.csv
├── forecast/
│   ├── open_meteo.py       forecast incl. solar variables (no key)
│   ├── google_weather.py   weather forecast (key required)
│   ├── merge.py            Google primary, Open-Meteo fallback → model input
│   └── run.py              all three steps in one command
└── inference.py            predict(), simulate(), load_model()

backend/app.py              Flask API (/analyze, /simulate)
backend/api_requests.http   request collection, including error cases
data/cities.csv             city registry: city, lat, lon, population
models/pv_xgb_no_lags.joblib  deployed XGBoost model
notebooks/01_eda.ipynb      exploratory analysis
notebooks/02_train_model.ipynb  Optuna tuning, training, evaluation, SHAP
notebooks/03_prediction_check.ipynb  quick inference check
```

`data/raw/` and `data/forecast/` are generated and gitignored.

---

## Training dataset

```bash
python -m solarsight.ingest.build_dataset                       # Gliwice, 2023-01-01 → 2025-12-31
python -m solarsight.ingest.build_dataset --city Katowice --start 2024-01-01 --end 2025-12-31
python -m solarsight.ingest.build_dataset --skip-download       # reuse files in data/raw/
```

The city must exist in `data/cities.csv`. Each step can also run on its own:
`python -m solarsight.ingest.weather_history` and `python -m solarsight.ingest.pv_production`.

### 1. PV production (`ingest/pv_production.py`)

Downloads national hourly PV generation from ENTSO-E via [Instrat](https://energy-api.instrat.pl) and scales it to the city:

```
pv_production_mwh = national_production × (city_population / POPULATION_PL)
```

**ENTSO-E reporting change, 13 June 2024.** Polish PV data switched from 60-minute resolution (one sample, already MWh) to 15-minute resolution (four MW samples summed per hour). From that date the hourly sum is multiplied by 0.25 h. Without the correction, every hour after the switch is about 4× too high.

### 2. Weather history (`ingest/weather_history.py`)

Hourly data from the [Open-Meteo archive API](https://archive-api.open-meteo.com/v1/archive), in UTC.

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
| `pressure_hpa` | Surface pressure [hPa] |

`uv_index` is not used for training because the archive endpoint returns null for it; shortwave radiation is the better predictor anyway. Missing radiation and sunshine values are filled with 0 (night), and the continuous variables are interpolated.

Engineered features:

| Column | Description |
|---|---|
| `hour`, `day_of_year`, `month` | Calendar features (UTC) |
| `hour_sin`, `hour_cos` | Cyclic encoding of the hour |
| `doy_sin`, `doy_cos` | Cyclic encoding of the day of year |
| `solar_elevation_deg` | Sun elevation above the horizon (NOAA formula) |

### 3. Merge (`ingest/build_dataset.py`)

- Joins weather and production on a **complete hourly UTC grid**, so the spring DST change cannot leave a hole. The one missing PV hour per year falls at night and is filled with 0.
- Adds `installed_pv_mw_pl` from `capacity.py` and `capacity_factor = production_mwh / (installed_pv_mw_pl × population_share)`.
- The target column is `production_mwh`.

### Installed capacity (`capacity.py`)

`PV_CAPACITY_PL_MW` is a hard-coded table of monthly installed PV capacity in Poland (URE/PSE reports, end of month, rounded to 100 MW). URE has no public API, so the numbers are copied by hand. Capacity grew from ~12.7 GW (January 2023) to ~22.5 GW (December 2025); feeding it to the model lets it learn weather-driven efficiency instead of a growth trend. **Extend the table with new months** to keep forecasts accurate; until then forecasts use the latest value.

---

## Model (`notebooks/02_train_model.ipynb`)

- **Algorithm:** XGBoost regressor
- **Tuning:** Optuna, 100 trials, each scored by 5-fold `TimeSeriesSplit` (30-day test windows, 24 h gap)
- **Features:** every dataset column except `timestamp`, `date`, `city`, `production_mwh`, `capacity_factor`
- **Final evaluation:** chronological 80/20 split

| Metric | Value |
|---|---|
| MAE | 2.56 MWh |
| RMSE | 5.85 MWh |
| R² | 0.845 |

An earlier variant with lagged production features reported MAE 0.29 MWh, RMSE 1.37 MWh, R² 0.9873. Lagged production does not exist when forecasting 24 h ahead from weather alone, so the deployed model has no lag features.

---

## Forecast pipeline

```bash
python -m solarsight.forecast.run                          # 24 h, Gliwice, key from .env
python -m solarsight.forecast.run --hours 48 --city Opole --keep-intermediate
```

Output: `data/forecast/forecast_final.csv`, with exactly the training feature columns (no target). Copy `.env.example` to `.env` and set `GOOGLE_WEATHER_API_KEY`.

Google Weather is the **primary** source for weather variables (temperature, wind, humidity, pressure, cloud cover). Open-Meteo is the **only** source of solar variables (shortwave, direct, diffuse radiation, sunshine) and the fallback when Google returns NaN. The steps can also run separately: `solarsight.forecast.open_meteo`, `solarsight.forecast.google_weather`, `solarsight.forecast.merge`.

> The live API does not need a Google key: `solarsight.inference` fetches its forecast straight from Open-Meteo.

---

## API (`backend/app.py`)

| Endpoint | Body | Returns |
|---|---|---|
| `GET /` | | health check and package version |
| `POST /analyze` | `{"city": "Katowice"}` | 24 rows: `timestamp`, `hour`, `production_mwh`, `temperature_c`, `uv_index`, `cloud_cover_pct`, `weather_code`, `status` |
| `POST /simulate` | `{"city": "Gliwice", "cloud_cover": 50}` | 24 rows: `timestamp`, `hour`, `production_mwh`, `cloud_cover_pct` |

`city` can also be passed as a query string; an empty or missing city falls back to Gliwice. Errors: 400 for an unknown city or invalid `cloud_cover`, 502 when Open-Meteo fails, 500 otherwise. Forecasts are cached per city for 15 minutes.

---

## Adding a city

1. Append a row to `data/cities.csv`: `Rybnik,50.0971,18.5463,134000`
2. Add a marker to `frontend/src/data/cities.json`.
3. Optional: build a dataset for it with `--city Rybnik`.

---

## Known limitations

- **No city feature in the model.** It was trained on Gliwice-scaled production, so every city gets a Gliwice-sized forecast for the same weather. Population scaling is not applied at inference yet.
- **Hours are UTC.** The night-hour clamp (22:00–03:00) and the chart labels use UTC hours, not Polish time.
- **Results are sorted by hour**, so a 24 h window that crosses midnight mixes today's and tomorrow's hours on the chart.
