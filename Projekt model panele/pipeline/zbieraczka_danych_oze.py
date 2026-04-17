from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pandas as pd
import requests
from urllib3.exceptions import InsecureRequestWarning

# 2024-06-13 ENTSO-E PL przeszlo z raportowania 60-min (1 probka w MWh)
# na 15-min (4 probki w MW sumowane w godzinie). Przed ta data nie mnozymy
# przez 0.25; od tej daty — mnozymy. Empirycznie zweryfikowane na API instrat:
# 2024-06-12 10:00 solar=7183, 2024-06-13 10:00 solar=22828 (skok ~3.2x
# zgodny z wzrostem mocy + zmiana jednostki).
ENTSO_15MIN_TRANSITION = datetime(2024, 6, 13, 0, 0, tzinfo=timezone.utc)

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

API_URL = "https://energy-api.instrat.pl/api/energy/production_entsoe"
PV_COLUMN = "solar"

# Założenie skalowania: brak publicznie dostępnych danych o zainstalowanej mocy PV
# per miasto, więc krajową produkcję skalujemy proporcjonalnie do liczby mieszkańców.
# To przybliżenie — docelowo warto podmienić na udział zainstalowanej mocy PV
# (np. z rejestru URE) lub udział produkcji wojewódzkiej.
POPULATION_PL = 37_800_000
CITIES_CSV = "miasta.csv"
DEFAULT_CITY = "Gliwice"
DEFAULT_START_DATE = date(2023, 1, 1)
DEFAULT_END_DATE = date(2025, 12, 31)


def format_api_datetime(value: date, end_of_day: bool) -> str:
    suffix = "T23:59:00Z" if end_of_day else "T00:00:00Z"
    return value.strftime("%d-%m-%Y") + suffix


def iter_ranges(start_date: date, end_date: date, chunk_days: int = 92) -> Iterator[Tuple[date, date]]:
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=chunk_days - 1), end_date)
        yield current_start, current_end
        current_start = current_end + timedelta(days=1)


def fetch_chunk(
    session: requests.Session,
    start_date: date,
    end_date: date,
    aggregation_timeframe: str = "hour",
    aggregation_type: str = "sum",
) -> list[dict]:
    params = {
        "date_from": format_api_datetime(start_date, end_of_day=False),
        "date_to": format_api_datetime(end_date, end_of_day=True),
        "aggregation_timeframe": aggregation_timeframe,
        "aggregation_type": aggregation_type,
    }
    response = session.get(API_URL, params=params, timeout=60, verify=False)
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Nieoczekiwany format odpowiedzi API: {type(payload)!r}")
    return payload


def load_city(city: str, cities_csv: str = CITIES_CSV) -> dict:
    path = Path(cities_csv)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    cities = pd.read_csv(path)
    row = cities.loc[cities["city"].str.lower() == city.lower()]
    if row.empty:
        raise ValueError(f"Nie znaleziono miasta '{city}' w {path}")
    return row.iloc[0].to_dict()


def pobierz_fotowoltaike_godzinowo(
    city: str = DEFAULT_CITY,
    start_date: date = DEFAULT_START_DATE,
    end_date: date = DEFAULT_END_DATE,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    city_info = load_city(city)
    scaling_factor = float(city_info["population"]) / POPULATION_PL

    print(f"Pobieranie danych o produkcji fotowoltaiki dla {city_info['city']} "
          f"({start_date} -> {end_date}, skalowanie per capita: {scaling_factor:.6f})...")

    records: list[dict] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        for chunk_start, chunk_end in iter_ranges(start_date, end_date):
            chunk_records = fetch_chunk(session, chunk_start, chunk_end, aggregation_timeframe="hour", aggregation_type="sum")
            records.extend(chunk_records)

    if not records:
        raise ValueError("API nie zwrocilo zadnych danych")

    df = pd.DataFrame(records)
    if "date" not in df.columns:
        raise ValueError("Brak kolumny 'date' w odpowiedzi API")

    if PV_COLUMN not in df.columns:
        raise ValueError("Brak kolumny 'solar' w odpowiedzi API")

    df[PV_COLUMN] = pd.to_numeric(df[PV_COLUMN], errors="coerce").fillna(0.0)

    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    # ENTSO-E przed 2024-06-13 raportowalo dla PL w rozdzielczosci 60-min
    # (1 probka, juz w MWh), od 2024-06-13 — 15-min (4 probki w MW, sumowane
    # do godziny przy aggregation_type=sum -> trzeba pomnozyc przez 0.25h).
    # Bez tej korekty dane sprzed 2024-06-13 sa zanizone ~4x.
    mw_scale = (df["date"] >= ENTSO_15MIN_TRANSITION).map({True: 0.25, False: 1.0})
    df["Produkcja_PV_Godz_MWh_PL"] = df[PV_COLUMN] * mw_scale

    df["Produkcja_PV_Godz_MWh"] = df["Produkcja_PV_Godz_MWh_PL"] * scaling_factor
    df["city"] = city_info["city"]
    df["lat"] = city_info["lat"]
    df["lon"] = city_info["lon"]

    df_hourly = (
        df[["date", "city", "lat", "lon", "Produkcja_PV_Godz_MWh"]]
        .groupby(["date", "city", "lat", "lon"], as_index=False)
        .sum()
        .sort_values("date")
    )

    if output_path is None:
        output_path = (
            f"fotowoltaika_godzinowo_{city_info['city']}_"
            f"{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"
        )

    if output_path:
        df_hourly.to_csv(output_path, index=False)
        print(f"Zapisano plik: {output_path}")

    return df_hourly


def pobierz_fotowoltaike_dziennie(
    city: str = DEFAULT_CITY,
    start_date: date = DEFAULT_START_DATE,
    end_date: date = DEFAULT_END_DATE,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    df_hourly = pobierz_fotowoltaike_godzinowo(
        city=city, start_date=start_date, end_date=end_date, output_path=None
    )
    df_daily = (
        df_hourly.assign(date=pd.to_datetime(df_hourly["date"], utc=True))
        .set_index("date")
        .groupby(["city", "lat", "lon"])
        .resample("D")["Produkcja_PV_Godz_MWh"]
        .sum()
        .reset_index()
        .rename(columns={"Produkcja_PV_Godz_MWh": "Produkcja_PV_Dzien_MWh"})
    )

    if output_path is None:
        output_path = (
            f"fotowoltaika_dziennie_{city}_"
            f"{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"
        )

    if output_path:
        df_daily.to_csv(output_path, index=False)
        print(f"Zapisano plik: {output_path}")

    return df_daily


if __name__ == "__main__":
    wynik = pobierz_fotowoltaike_godzinowo(city=DEFAULT_CITY)
    print(wynik.head())
