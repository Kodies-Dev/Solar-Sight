"""Hourly national PV production from ENTSO-E (via the Instrat energy API), scaled to a city."""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests
from urllib3.exceptions import InsecureRequestWarning

from solarsight.config import (DEFAULT_CITY, DEFAULT_END_DATE, DEFAULT_START_DATE,
                               ENTSOE_15MIN_TRANSITION, POPULATION_PL, RAW_DATA_DIR)
from solarsight.geo import load_city

logger = logging.getLogger(__name__)

# The Instrat API certificate does not verify reliably, so requests run with verify=False.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

INSTRAT_API_URL = "https://energy-api.instrat.pl/api/energy/production_entsoe"
SOLAR_COLUMN = "solar"
PRODUCTION_COLUMN = "pv_production_mwh"


def pv_production_path(city: str, start_date: date, end_date: date) -> Path:
    return RAW_DATA_DIR / f"pv_production_{city.lower()}_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"


def format_api_datetime(value: date, end_of_day: bool) -> str:
    suffix = "T23:59:00Z" if end_of_day else "T00:00:00Z"
    return value.strftime("%d-%m-%Y") + suffix


def iter_date_ranges(start_date: date, end_date: date, chunk_days: int = 92) -> Iterator[tuple[date, date]]:
    """Split a date range into chunks the API accepts in one request."""
    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_date)
        yield chunk_start, chunk_end
        chunk_start = chunk_end + timedelta(days=1)


def fetch_chunk(session: requests.Session, start_date: date, end_date: date,
                aggregation_timeframe: str = "hour", aggregation_type: str = "sum") -> list[dict]:
    params = {
        "date_from": format_api_datetime(start_date, end_of_day=False),
        "date_to": format_api_datetime(end_date, end_of_day=True),
        "aggregation_timeframe": aggregation_timeframe,
        "aggregation_type": aggregation_type,
    }
    response = session.get(INSTRAT_API_URL, params=params, timeout=60, verify=False)
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected API response format: {type(payload)!r}")
    return payload


def fetch_hourly_pv_production(city: str = DEFAULT_CITY,
                               start_date: date = DEFAULT_START_DATE,
                               end_date: date = DEFAULT_END_DATE) -> pd.DataFrame:
    """Hourly PV production for a city: national production × the city's population share."""
    city_info = load_city(city)
    population_share = float(city_info["population"]) / POPULATION_PL
    logger.info("Fetching PV production for %s (%s -> %s, population share %.6f)",
                city_info["city"], start_date, end_date, population_share)

    records: list[dict] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for chunk_start, chunk_end in iter_date_ranges(start_date, end_date):
            records.extend(fetch_chunk(session, chunk_start, chunk_end))

    if not records:
        raise ValueError("The API returned no data")

    df = pd.DataFrame(records)
    for column in ("date", SOLAR_COLUMN):
        if column not in df.columns:
            raise ValueError(f"Column '{column}' missing from the API response")

    df[SOLAR_COLUMN] = pd.to_numeric(df[SOLAR_COLUMN], errors="coerce").fillna(0.0)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    # See ENTSOE_15MIN_TRANSITION: from that date four 15-minute MW samples are
    # summed per hour, so the sum is multiplied by 0.25 h to get MWh. Verified
    # against the API: 2024-06-12 10:00 solar=7183, 2024-06-13 10:00 solar=22828.
    mw_to_mwh = (df["date"] >= ENTSOE_15MIN_TRANSITION).map({True: 0.25, False: 1.0})
    national_mwh = df[SOLAR_COLUMN] * mw_to_mwh

    df[PRODUCTION_COLUMN] = national_mwh * population_share
    df["city"] = city_info["city"]
    df["lat"] = city_info["lat"]
    df["lon"] = city_info["lon"]

    return (
        df[["date", "city", "lat", "lon", PRODUCTION_COLUMN]]
        .groupby(["date", "city", "lat", "lon"], as_index=False)
        .sum()
        .sort_values("date")
    )


def fetch_daily_pv_production(city: str = DEFAULT_CITY,
                              start_date: date = DEFAULT_START_DATE,
                              end_date: date = DEFAULT_END_DATE) -> pd.DataFrame:
    """Daily totals of ``fetch_hourly_pv_production``."""
    hourly = fetch_hourly_pv_production(city, start_date, end_date)
    return (
        hourly.assign(date=pd.to_datetime(hourly["date"], utc=True))
        .set_index("date")
        .groupby(["city", "lat", "lon"])
        .resample("D")[PRODUCTION_COLUMN]
        .sum()
        .reset_index()
        .rename(columns={PRODUCTION_COLUMN: "pv_production_daily_mwh"})
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download hourly PV production (ENTSO-E via Instrat)")
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START_DATE)
    parser.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END_DATE)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    df = fetch_hourly_pv_production(args.city, args.start, args.end)
    output = args.output or pv_production_path(args.city, args.start, args.end)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"Saved {output} ({len(df)} rows)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
