"""Build the hourly training dataset: weather history + PV production + installed capacity.

Usage (from the repository root):
    python -m solarsight.ingest.build_dataset
    python -m solarsight.ingest.build_dataset --city Gliwice --start 2023-01-01 --end 2025-12-31
    python -m solarsight.ingest.build_dataset --skip-download   # reuse files in data/raw/
"""
from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from solarsight.capacity import get_capacity_mw
from solarsight.config import (DEFAULT_CITY, DEFAULT_END_DATE, DEFAULT_START_DATE,
                               POPULATION_PL, PROCESSED_DATA_DIR, TARGET_COLUMN)
from solarsight.geo import load_city, solar_elevation_deg
from solarsight.ingest.pv_production import (PRODUCTION_COLUMN, fetch_hourly_pv_production,
                                             pv_production_path)
from solarsight.ingest.weather_history import (INTERPOLATED_COLUMNS, ZERO_FILL_COLUMNS,
                                               fetch_weather_history, weather_history_path)

logger = logging.getLogger(__name__)


def dataset_path(city: str, start_date: date, end_date: date) -> Path:
    return PROCESSED_DATA_DIR / f"dataset_{city.lower()}_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"


def merge_sources(weather: pd.DataFrame, pv: pd.DataFrame, city: str,
                  start_date: date, end_date: date) -> pd.DataFrame:
    """Join weather and PV production on a complete hourly UTC grid."""
    start = pd.Timestamp(start_date, tz="UTC")
    end = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(hours=23)

    weather = weather.copy()
    pv = pv.copy()
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    pv["timestamp"] = pd.to_datetime(pv.pop("date"), utc=True)

    # A full hourly UTC range guarantees no holes: the spring DST change drops
    # one hour a year from the ENTSO-E data because the API works in Polish time.
    grid = pd.DataFrame({"timestamp": pd.date_range(start, end, freq="h", tz="UTC")})

    weather = weather.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    pv = pv.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    weather_columns = [c for c in weather.columns if c not in {"city", "lat", "lon"}]

    merged = grid.merge(weather[weather_columns], on="timestamp", how="left")
    merged = merged.merge(pv[["timestamp", PRODUCTION_COLUMN]], on="timestamp", how="left")
    merged = merged.rename(columns={PRODUCTION_COLUMN: TARGET_COLUMN})

    missing_pv = int(merged[TARGET_COLUMN].isna().sum())
    if missing_pv:
        # Always 02:00 UTC on the last Sunday of March (DST in Poland): night, so 0.
        logger.info("Filling %d missing PV hours with 0.0 (DST spring-forward)", missing_pv)
    merged[TARGET_COLUMN] = merged[TARGET_COLUMN].fillna(0.0)

    missing_weather = int(merged["shortwave_radiation_wm2"].isna().sum())
    if missing_weather:
        logger.warning("%d missing weather hours, filling/interpolating", missing_weather)
        merged[ZERO_FILL_COLUMNS] = merged[ZERO_FILL_COLUMNS].fillna(0.0)
        merged[INTERPOLATED_COLUMNS] = (merged[INTERPOLATED_COLUMNS]
                                        .interpolate(method="linear", limit_direction="both")
                                        .ffill().bfill())

    city_info = load_city(city)
    if "solar_elevation_deg" not in merged.columns:
        # older weather files were saved before this feature existed
        merged["solar_elevation_deg"] = solar_elevation_deg(
            merged["timestamp"], float(city_info["lat"]), float(city_info["lon"]))

    # Capacity factor = production / installed capacity attributed to the city.
    # It depends on weather and time of day/year but not on capacity growth, so
    # it stays stable over time. 1 h × MW = MWh, which makes it dimensionless.
    merged["installed_pv_mw_pl"] = get_capacity_mw(merged["timestamp"])
    population_share = float(city_info["population"]) / POPULATION_PL
    merged["capacity_factor"] = merged[TARGET_COLUMN] / (merged["installed_pv_mw_pl"] * population_share)

    merged.insert(1, "city", city_info["city"])
    return merged


def build_dataset(city: str = DEFAULT_CITY,
                  start_date: date = DEFAULT_START_DATE,
                  end_date: date = DEFAULT_END_DATE,
                  skip_download: bool = False,
                  output: Path | None = None) -> pd.DataFrame:
    """Run the whole ingestion pipeline and save the training CSV."""
    weather_file = weather_history_path(city)
    pv_file = pv_production_path(city, start_date, end_date)

    if skip_download:
        weather = pd.read_csv(weather_file)
        pv = pd.read_csv(pv_file)
    else:
        weather_file.parent.mkdir(parents=True, exist_ok=True)
        weather = fetch_weather_history(city, start_date.isoformat(), end_date.isoformat())
        weather.to_csv(weather_file, index=False)
        pv = fetch_hourly_pv_production(city, start_date, end_date)
        pv.to_csv(pv_file, index=False)

    dataset = merge_sources(weather, pv, city, start_date, end_date)
    output = output or dataset_path(city, start_date, end_date)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output, index=False)
    logger.info("Saved %s (%d rows, %d columns)", output, len(dataset), dataset.shape[1])
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the PV training dataset")
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START_DATE)
    parser.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END_DATE)
    parser.add_argument("--skip-download", action="store_true",
                        help="reuse the weather and PV files already in data/raw/")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    build_dataset(args.city, args.start, args.end, args.skip_download, args.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
