"""Merge the Google Weather and Open-Meteo forecasts into one model-ready frame.

Google is the primary source for weather variables (temperature, wind, humidity,
pressure, cloud cover). Open-Meteo is the only source of solar variables and the
fallback whenever Google returns NaN. The output has exactly the training
feature columns (without the target).

Usage (from the repository root):
    python -m solarsight.forecast.merge                      # newest files in data/forecast/
    python -m solarsight.forecast.merge --google g.csv --meteo m.csv --output final.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from solarsight.capacity import get_capacity_mw_with_fallback
from solarsight.config import DEFAULT_CITY, FORECAST_DATA_DIR
from solarsight.geo import load_city, solar_elevation_deg

logger = logging.getLogger(__name__)

WEATHER_COLUMNS = ["cloud_cover_pct", "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa"]
SOLAR_COLUMNS = ["shortwave_radiation_wm2", "direct_radiation_wm2", "diffuse_radiation_wm2", "sunshine_pct"]
TIME_COLUMNS = ["date", "hour", "day_of_year", "month", "hour_sin", "hour_cos", "doy_sin", "doy_cos"]

# Final column order, matching the training schema (no target, no derived columns)
OUTPUT_COLUMNS = [
    "timestamp", "date", "hour", "day_of_year", "month",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    "shortwave_radiation_wm2", "direct_radiation_wm2", "diffuse_radiation_wm2",
    "cloud_cover_pct", "sunshine_pct",
    "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa",
    "solar_elevation_deg",
    "installed_pv_mw_pl",
]


def merge_forecasts(google: pd.DataFrame, meteo: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(google, meteo, on="timestamp", how="left", suffixes=("", "_meteo"))

    # weather and time columns: Google first, Open-Meteo as fallback
    for column in WEATHER_COLUMNS + TIME_COLUMNS:
        meteo_column = f"{column}_meteo"
        if meteo_column in merged.columns:
            missing = int(merged[column].isna().sum())
            merged[column] = merged[column].fillna(merged[meteo_column])
            if missing and column in WEATHER_COLUMNS:
                logger.info("Filled %d gaps in '%s' from Open-Meteo", missing, column)

    # solar columns: only Open-Meteo has them
    for column in SOLAR_COLUMNS:
        meteo_column = f"{column}_meteo"
        if column not in merged.columns and meteo_column in merged.columns:
            merged[column] = merged[meteo_column]

    return merged.drop(columns=[c for c in merged.columns if c.endswith("_meteo")])


def add_location_features(df: pd.DataFrame, city: str) -> pd.DataFrame:
    city_info = load_city(city)
    timestamps = pd.to_datetime(df["timestamp"], utc=True)
    df["solar_elevation_deg"] = solar_elevation_deg(timestamps, float(city_info["lat"]), float(city_info["lon"]))
    df["installed_pv_mw_pl"] = get_capacity_mw_with_fallback(timestamps)
    return df[[c for c in OUTPUT_COLUMNS if c in df.columns]]


def find_latest(prefix: str, directory: Path = FORECAST_DATA_DIR) -> Path | None:
    candidates = sorted(directory.glob(f"{prefix}_*.csv"), reverse=True)
    return candidates[0] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Google Weather + Open-Meteo forecasts")
    parser.add_argument("--google", type=Path, default=None)
    parser.add_argument("--meteo", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=FORECAST_DATA_DIR / "forecast_final.csv")
    parser.add_argument("--city", default=DEFAULT_CITY)
    args = parser.parse_args()

    google_path = args.google or find_latest("google_forecast")
    meteo_path = args.meteo or find_latest("meteo_forecast")
    if not google_path:
        sys.exit("No Google forecast CSV. Run: python -m solarsight.forecast.google_weather")
    if not meteo_path:
        sys.exit("No Open-Meteo forecast CSV. Run: python -m solarsight.forecast.open_meteo")

    df = merge_forecasts(pd.read_csv(google_path), pd.read_csv(meteo_path))
    df = add_location_features(df, args.city)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} ({len(df)} rows, {df.shape[1]} columns)")
    for column in OUTPUT_COLUMNS[2:]:
        if column in df.columns:
            present = int(df[column].notna().sum())
            status = "OK" if present == len(df) else f"MISSING {len(df) - present}"
            print(f"  {column:30s} {present}/{len(df)} {status}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
