"""Full 24 h forecast-input pipeline: Open-Meteo + Google Weather -> merged CSV.

The Google key is read from GOOGLE_WEATHER_API_KEY (.env in the project root)
or passed with --api-key.

Usage (from the repository root):
    python -m solarsight.forecast.run
    python -m solarsight.forecast.run --hours 48 --city Gliwice --keep-intermediate
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from solarsight.config import DEFAULT_CITY, FORECAST_DATA_DIR
from solarsight.forecast import google_weather, open_meteo
from solarsight.forecast.merge import add_location_features, merge_forecasts
from solarsight.geo import load_city

logger = logging.getLogger(__name__)


def run_forecast(city: str, hours: int, api_key: str, output: Path,
                 keep_intermediate: bool = False) -> Path:
    city_info = load_city(city)
    lat, lon = float(city_info["lat"]), float(city_info["lon"])

    logger.info("[1/3] Open-Meteo")
    meteo = open_meteo.to_csv_frame(open_meteo.fetch_forecast(lat, lon, hours))
    logger.info("[2/3] Google Weather")
    google = google_weather.to_csv_frame(google_weather.fetch_forecast(api_key, lat, lon, hours))

    if keep_intermediate:
        stamp = f"{datetime.now(timezone.utc):%Y%m%d_%H%M}"
        FORECAST_DATA_DIR.mkdir(parents=True, exist_ok=True)
        meteo.to_csv(FORECAST_DATA_DIR / f"meteo_forecast_{stamp}.csv", index=False)
        google.to_csv(FORECAST_DATA_DIR / f"google_forecast_{stamp}.csv", index=False)

    logger.info("[3/3] Merge")
    merged = add_location_features(merge_forecasts(google, meteo), city)
    output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output, index=False)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the PV forecast input")
    parser.add_argument("--hours", type=int, default=24, help="forecast horizon (default 24)")
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--output", type=Path, default=FORECAST_DATA_DIR / "forecast_final.csv")
    parser.add_argument("--api-key", default=None, help="Google key (defaults to .env)")
    parser.add_argument("--keep-intermediate", action="store_true",
                        help="also save the separate Open-Meteo and Google CSVs")
    args = parser.parse_args()

    api_key = google_weather.get_api_key(args.api_key)
    if not api_key:
        sys.exit("Missing Google key: set GOOGLE_WEATHER_API_KEY in .env or pass --api-key")

    output = run_forecast(args.city, args.hours, api_key, args.output, args.keep_intermediate)
    print(f"Done: {output}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
