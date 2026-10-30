"""Project-wide paths and constants."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"              # intermediate downloads (gitignored)
PROCESSED_DATA_DIR = DATA_DIR / "processed"  # training datasets
FORECAST_DATA_DIR = DATA_DIR / "forecast"    # forecast CSVs (gitignored)
CITIES_CSV = DATA_DIR / "cities.csv"

MODELS_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODELS_DIR / "pv_xgb_no_lags.joblib"

ENV_FILE = PROJECT_ROOT / ".env"

DEFAULT_CITY = "Gliwice"
DEFAULT_START_DATE = date(2023, 1, 1)
DEFAULT_END_DATE = date(2025, 12, 31)

# There is no public per-city PV capacity data, so national production is scaled
# to a city by its share of the population. This is an approximation; a better
# source would be the city's share of installed capacity (e.g. the URE register).
POPULATION_PL = 37_800_000

# On 2024-06-13 ENTSO-E switched Polish PV reporting from 60-minute resolution
# (one sample, already in MWh) to 15-minute resolution (four samples in MW that
# get summed per hour). From this date the hourly sum must be multiplied by 0.25.
ENTSOE_15MIN_TRANSITION = datetime(2024, 6, 13, 0, 0, tzinfo=timezone.utc)

TARGET_COLUMN = "production_mwh"
