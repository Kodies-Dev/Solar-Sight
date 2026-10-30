"""Hourly forecast from Open-Meteo (free, no API key).

Open-Meteo is the only source of solar variables in the forecast pipeline
(shortwave/direct/diffuse radiation, sunshine) and the fallback for weather
variables when Google returns NaN. All timestamps and time features are in UTC,
consistent with the training data.

Usage (from the repository root):
    python -m solarsight.forecast.open_meteo
    python -m solarsight.forecast.open_meteo --hours 48 --city Gliwice
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from solarsight.capacity import latest_capacity_mw
from solarsight.config import DEFAULT_CITY, FORECAST_DATA_DIR
from solarsight.features import add_time_features
from solarsight.geo import load_city, solar_elevation_deg

logger = logging.getLogger(__name__)

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARIABLES = [
    "temperature_2m", "relative_humidity_2m", "surface_pressure",
    "cloud_cover", "wind_speed_10m", "uv_index",
    "shortwave_radiation",   # GHI -> shortwave_radiation_wm2
    "direct_radiation",      # -> direct_radiation_wm2
    "diffuse_radiation",     # DHI -> diffuse_radiation_wm2
    "sunshine_duration", "weather_code",
]

# Column order of the CSV consumed by solarsight.forecast.merge
CSV_COLUMNS = [
    "timestamp", "date", "hour", "day_of_year", "month",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    "uv_index", "cloud_cover_pct",
    "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa",
    "sunshine_pct",
    "shortwave_radiation_wm2", "direct_radiation_wm2", "diffuse_radiation_wm2",
]


def fetch_forecast(lat: float, lon: float, hours: int = 24) -> pd.DataFrame:
    """Raw hourly forecast for the next ``hours`` hours, starting at the current UTC hour.

    The window matches the Google Weather rolling window, so the two sources
    align hour by hour when merged. Raises RuntimeError if the API fails.
    """
    start_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_hour = start_hour + timedelta(hours=hours - 1)

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARIABLES),
        "start_hour": start_hour.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end_hour.strftime("%Y-%m-%dT%H:%M"),
        "timezone": "UTC",
    }
    response = requests.get(FORECAST_API_URL, params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Open-Meteo API error {response.status_code}: {response.text[:300]}")

    hourly = response.json().get("hourly", {})
    timestamps = pd.Series(pd.to_datetime(hourly.get("time", []), utc=True))
    if timestamps.empty:
        raise RuntimeError("Open-Meteo returned no forecast data")

    df = pd.DataFrame({
        "timestamp": timestamps,
        "temperature_c": hourly.get("temperature_2m"),
        "humidity_pct": hourly.get("relative_humidity_2m"),
        "pressure_hpa": hourly.get("surface_pressure"),
        "cloud_cover_pct": hourly.get("cloud_cover"),
        "wind_speed_ms": hourly.get("wind_speed_10m"),
        "uv_index": hourly.get("uv_index"),
        "shortwave_radiation_wm2": hourly.get("shortwave_radiation"),
        "direct_radiation_wm2": hourly.get("direct_radiation"),
        "diffuse_radiation_wm2": hourly.get("diffuse_radiation"),
        "sunshine_duration_s": hourly.get("sunshine_duration"),
        "weather_code": hourly.get("weather_code"),
    })
    df["sunshine_pct"] = (df["sunshine_duration_s"] / 3600 * 100).clip(0, 100).round(1)
    return df.drop(columns=["sunshine_duration_s"])


def build_model_input(forecast: pd.DataFrame, lat: float, lon: float) -> pd.DataFrame:
    """Turn a raw forecast into the feature frame the model expects."""
    df = forecast.copy()
    timestamps = df["timestamp"]
    df["uv_index"] = df["uv_index"].fillna(0.0).round(2)  # NaN at night
    add_time_features(df, timestamps, decimals=4)
    df["solar_elevation_deg"] = np.round(solar_elevation_deg(timestamps, lat, lon), 6)
    df["installed_pv_mw_pl"] = latest_capacity_mw()
    df["timestamp"] = timestamps.dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def to_csv_frame(forecast: pd.DataFrame) -> pd.DataFrame:
    """Format a raw forecast as the CSV consumed by the merge step."""
    df = forecast.copy()
    add_time_features(df, df["timestamp"], decimals=4)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[[c for c in CSV_COLUMNS if c in df.columns]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Open-Meteo forecast -> CSV")
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    city_info = load_city(args.city)
    forecast = fetch_forecast(float(city_info["lat"]), float(city_info["lon"]), args.hours)
    df = to_csv_frame(forecast)

    output = args.output or FORECAST_DATA_DIR / f"meteo_forecast_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"Saved {output} ({len(df)} rows, {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
