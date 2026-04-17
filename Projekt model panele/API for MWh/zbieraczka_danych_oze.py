from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator, Optional, Tuple

import pandas as pd
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

API_URL = "https://energy-api.instrat.pl/api/energy/production_entsoe"
PV_COLUMN = "solar"


def shift_years(source_date: date, years: int) -> date:
    try:
        return source_date.replace(year=source_date.year + years)
    except ValueError:
        return source_date.replace(month=2, day=28, year=source_date.year + years)


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


def pobierz_fotowoltaike_godzinowo(years_back: int = 3, output_path: Optional[str] = "fotowoltaika_godzinowo_3_lata.csv") -> pd.DataFrame:
    today = datetime.utcnow().date()
    start_date = shift_years(today, -years_back)

    print("Pobieranie danych o produkcji fotowoltaiki...")

    records: list[dict] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        for chunk_start, chunk_end in iter_ranges(start_date, today):
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

    # API zwraca godzinową moc dla fotowoltaiki, więc przeliczamy ją na energię dla każdej godziny.
    df["PV_MW"] = df[PV_COLUMN]
    df["Produkcja_PV_Godz_MWh"] = df["PV_MW"] * 0.25

    df_hourly = (
        df[["date", "Produkcja_PV_Godz_MWh"]]
        .groupby("date", as_index=False)
        .sum()
        .sort_values("date")
    )

    if output_path:
        df_hourly.to_csv(output_path, index=False)
        print(f"Zapisano plik: {output_path}")

    return df_hourly


def pobierz_fotowoltaike_dziennie(years_back: int = 3, output_path: Optional[str] = "fotowoltaika_dziennie_3_lata.csv") -> pd.DataFrame:
    df_hourly = pobierz_fotowoltaike_godzinowo(years_back=years_back, output_path=None)
    df_daily = (
        df_hourly.assign(date=pd.to_datetime(df_hourly["date"], utc=True))
        .set_index("date")
        .resample("D")
        .sum()
        .reset_index()
        .rename(columns={"Produkcja_PV_Godz_MWh": "Produkcja_PV_Dzien_MWh"})
    )

    if output_path:
        df_daily.to_csv(output_path, index=False)
        print(f"Zapisano plik: {output_path}")

    return df_daily


if __name__ == "__main__":
    wynik = pobierz_fotowoltaike_godzinowo()
    print(wynik.head())