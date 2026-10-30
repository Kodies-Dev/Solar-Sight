"""Historical hourly weather from the Open-Meteo archive API."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import requests

from solarsight.config import DEFAULT_CITY, DEFAULT_END_DATE, DEFAULT_START_DATE, RAW_DATA_DIR
from solarsight.features import add_time_features
from solarsight.geo import load_city, solar_elevation_deg

logger = logging.getLogger(__name__)

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

# shortwave_radiation replaces uv_index, which the historical endpoint does not
# provide (it returns null). Shortwave radiation is the direct energy input for
# PV panels, so it is a better predictor than UV anyway.
HOURLY_VARIABLES = [
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "cloud_cover", "sunshine_duration",
    "temperature_2m", "wind_speed_10m",
    "relative_humidity_2m", "surface_pressure",
]

# Missing radiation/sunshine means night or no measurement, so 0.0 is physical.
ZERO_FILL_COLUMNS = ["shortwave_radiation_wm2", "direct_radiation_wm2",
                     "diffuse_radiation_wm2", "sunshine_pct", "cloud_cover_pct"]
# 0.0 would be unrealistic for these, so they are interpolated instead.
INTERPOLATED_COLUMNS = ["temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa"]


def weather_history_path(city: str) -> Path:
    return RAW_DATA_DIR / f"weather_{city.lower()}.csv"


def fetch_weather_history(city: str = DEFAULT_CITY,
                          start_date: str = DEFAULT_START_DATE.isoformat(),
                          end_date: str = DEFAULT_END_DATE.isoformat()) -> pd.DataFrame:
    """Download hourly weather for a city and add the engineered features."""
    city_info = load_city(city)
    lat, lon = float(city_info["lat"]), float(city_info["lon"])

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HOURLY_VARIABLES,
        "timezone": "UTC",
    }
    logger.info("Fetching weather history for %s (%s -> %s)", city_info["city"], start_date, end_date)
    response = requests.get(ARCHIVE_API_URL, params=params, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"Open-Meteo archive error {response.status_code}: {response.text[:300]}")

    hourly = response.json()["hourly"]
    timestamps = pd.Series(pd.to_datetime(hourly["time"], utc=True))

    df = pd.DataFrame({
        "timestamp": timestamps,
        "shortwave_radiation_wm2": hourly["shortwave_radiation"],
        "direct_radiation_wm2": hourly["direct_radiation"],
        "diffuse_radiation_wm2": hourly["diffuse_radiation"],
        "cloud_cover_pct": hourly["cloud_cover"],
        "sunshine_pct": hourly["sunshine_duration"],
        "temperature_c": hourly["temperature_2m"],
        "wind_speed_ms": hourly["wind_speed_10m"],
        "humidity_pct": hourly["relative_humidity_2m"],
        "pressure_hpa": hourly["surface_pressure"],
    })

    # seconds of sunshine per hour -> percent of the hour
    df["sunshine_pct"] = (df["sunshine_pct"] / 3600 * 100).round(1)

    df["city"] = city_info["city"]
    df["lat"] = lat
    df["lon"] = lon

    add_time_features(df, timestamps)
    df["solar_elevation_deg"] = solar_elevation_deg(timestamps, lat, lon)

    df[ZERO_FILL_COLUMNS] = df[ZERO_FILL_COLUMNS].fillna(0.0)
    df[INTERPOLATED_COLUMNS] = (df[INTERPOLATED_COLUMNS]
                                .interpolate(method="linear", limit_direction="both")
                                .ffill()
                                .bfill())
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Download hourly weather history (Open-Meteo archive)")
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--start", default=DEFAULT_START_DATE.isoformat())
    parser.add_argument("--end", default=DEFAULT_END_DATE.isoformat())
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    df = fetch_weather_history(args.city, args.start, args.end)
    output = args.output or weather_history_path(args.city)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"Saved {output} ({len(df)} rows)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
