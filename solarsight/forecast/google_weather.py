"""Hourly weather forecast from the Google Weather API (key required).

Provides temperature, wind, humidity, pressure, UV index and cloud cover
(up to 240 h ahead). Timestamps and time features are in UTC.

Usage (from the repository root):
    python -m solarsight.forecast.google_weather --api-key YOUR_KEY
    GOOGLE_WEATHER_API_KEY=YOUR_KEY python -m solarsight.forecast.google_weather --hours 48
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from solarsight.config import DEFAULT_CITY, ENV_FILE, FORECAST_DATA_DIR
from solarsight.features import add_time_features
from solarsight.geo import load_city

logger = logging.getLogger(__name__)

load_dotenv(ENV_FILE)

GOOGLE_WEATHER_API_URL = "https://weather.googleapis.com/v1/forecast/hours:lookup"
MAX_HOURS = 240

CSV_COLUMNS = [
    "timestamp", "date", "hour", "day_of_year", "month",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    "uv_index", "cloud_cover_pct",
    "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa",
]


def get_api_key(explicit_key: str | None = None) -> str | None:
    return explicit_key or os.environ.get("GOOGLE_WEATHER_API_KEY")


def fetch_forecast(api_key: str, lat: float, lon: float, hours: int) -> pd.DataFrame:
    """Raw hourly forecast. Raises RuntimeError if the API fails."""
    params = {
        "key": api_key,
        "location.latitude": lat,
        "location.longitude": lon,
        "hours": min(hours, MAX_HOURS),
    }
    response = requests.get(GOOGLE_WEATHER_API_URL, params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Google Weather API error {response.status_code}: {response.text[:300]}")

    forecast_hours = response.json().get("forecastHours", [])
    if not forecast_hours:
        raise RuntimeError("Google Weather returned no forecast data")

    rows = []
    for hour in forecast_hours:
        start = hour.get("interval", {}).get("startTime", "")
        try:
            timestamp = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        wind = hour.get("wind", {}).get("speed", {})
        wind_value = wind.get("value", 0)
        wind_ms = wind_value / 3.6 if wind.get("unit", "KILOMETERS_PER_HOUR") == "KILOMETERS_PER_HOUR" else wind_value

        rows.append({
            "timestamp": timestamp,
            "temperature_c": hour.get("temperature", {}).get("degrees"),
            "wind_speed_ms": round(wind_ms, 2),
            "humidity_pct": hour.get("relativeHumidity"),
            "pressure_hpa": hour.get("airPressure", {}).get("meanSeaLevelMillibars"),
            "uv_index": hour.get("uvIndex", 0),
            "cloud_cover_pct": hour.get("cloudCover"),
        })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def to_csv_frame(forecast: pd.DataFrame) -> pd.DataFrame:
    """Format a raw forecast as the CSV consumed by the merge step."""
    df = forecast.copy()
    add_time_features(df, df["timestamp"], decimals=4)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[[c for c in CSV_COLUMNS if c in df.columns]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Weather forecast -> CSV")
    parser.add_argument("--api-key", default=None, help="defaults to GOOGLE_WEATHER_API_KEY (.env)")
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    api_key = get_api_key(args.api_key)
    if not api_key:
        sys.exit("Missing API key: pass --api-key or set GOOGLE_WEATHER_API_KEY in .env")

    city_info = load_city(args.city)
    forecast = fetch_forecast(api_key, float(city_info["lat"]), float(city_info["lon"]), args.hours)
    df = to_csv_frame(forecast)

    output = args.output or FORECAST_DATA_DIR / f"google_forecast_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"Saved {output} ({len(df)} rows, {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
