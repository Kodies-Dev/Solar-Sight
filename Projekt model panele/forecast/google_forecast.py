"""
google_forecast.py — pobiera prognozę pogodową z Google Weather API.

Dane: temperatura, wiatr, wilgotność, ciśnienie, UV index, zachmurzenie
Zakres: 240h max, domyślnie 72h, rozdzielczość godzinowa
Wszystkie timestampy i cechy czasowe (hour, day_of_year) w UTC —
spójne z danymi treningowymi z pipeline/class_weather_api.py.

Użycie:
    python google_forecast.py --api-key TWÓJ_KLUCZ
    python google_forecast.py --api-key KLUCZ --hours 48 --city Gliwice
    export GOOGLE_WEATHER_API_KEY=TWÓJ_KLUCZ && python google_forecast.py
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CITIES_CSV = Path(__file__).parent.parent / "pipeline" / "miasta.csv"
DEFAULT_CITY = "Gliwice"


def load_city(city: str) -> dict:
    df = pd.read_csv(CITIES_CSV)
    row = df.loc[df["city"].str.lower() == city.lower()]
    if row.empty:
        raise ValueError(f"Nie znaleziono miasta '{city}' w {CITIES_CSV}")
    return row.iloc[0].to_dict()


def fetch_google(api_key: str, lat: float, lon: float, hours: int) -> pd.DataFrame:
    url = "https://weather.googleapis.com/v1/forecast/hours:lookup"
    params = {
        "key": api_key,
        "location.latitude": lat,
        "location.longitude": lon,
        "hours": min(hours, 240),
    }

    print(f"Pobieranie {hours}h prognozy z Google Weather API ({lat}, {lon})...")
    r = requests.get(url, params=params, timeout=30)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print(f"BŁĄD {r.status_code}: {r.text[:500]}")
        sys.exit(1)

    forecast = r.json().get("forecastHours", [])
    if not forecast:
        print("Brak danych w odpowiedzi!")
        sys.exit(1)

    print(f"Liczba forecastHours w odpowiedzi: {len(forecast)}")

    rows = []
    for fh in forecast:
        start = fh.get("interval", {}).get("startTime", "")
        try:
            ts = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        wind_obj = fh.get("wind", {}).get("speed", {})
        wind_val = wind_obj.get("value", 0)
        wind_unit = wind_obj.get("unit", "KILOMETERS_PER_HOUR")
        wind_ms = wind_val / 3.6 if wind_unit == "KILOMETERS_PER_HOUR" else wind_val

        rows.append({
            "timestamp": ts,
            "temperature_c": fh.get("temperature", {}).get("degrees"),
            "wind_speed_ms": round(wind_ms, 2),
            "humidity_pct": fh.get("relativeHumidity"),
            "pressure_hpa": fh.get("airPressure", {}).get("meanSeaLevelMillibars"),
            "uv_index": fh.get("uvIndex", 0),
            "cloud_cover_pct": fh.get("cloudCover"),
        })

    df = pd.DataFrame(rows)
    print(f"Pobrano {len(df)} rekordów")
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    # Timestampy są w UTC (Google zwraca Z suffix) — godziny spójne z danymi treningowymi
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    df["month"] = df["timestamp"].dt.month

    df["hour_sin"] = np.round(np.sin(2 * np.pi * df["hour"] / 24), 4)
    df["hour_cos"] = np.round(np.cos(2 * np.pi * df["hour"] / 24), 4)
    df["doy_sin"] = np.round(np.sin(2 * np.pi * df["day_of_year"] / 365), 4)
    df["doy_cos"] = np.round(np.cos(2 * np.pi * df["day_of_year"] / 365), 4)

    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def main():
    ap = argparse.ArgumentParser(description="Google Weather API -> CSV")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--city", default=DEFAULT_CITY)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    key = args.api_key or os.environ.get("GOOGLE_WEATHER_API_KEY")
    if not key:
        print("Podaj klucz API: --api-key KLUCZ  lub  export GOOGLE_WEATHER_API_KEY=KLUCZ")
        sys.exit(1)

    city_info = load_city(args.city)
    df = fetch_google(key, float(city_info["lat"]), float(city_info["lon"]), args.hours)
    df = add_features(df)

    cols = [
        "timestamp", "date", "hour", "day_of_year", "month",
        "hour_sin", "hour_cos", "doy_sin", "doy_cos",
        "uv_index", "cloud_cover_pct",
        "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa",
    ]
    df = df[[c for c in cols if c in df.columns]]

    path = args.output or f"google_forecast_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"
    df.to_csv(path, index=False)
    print(f"\nZapisano: {path}")
    print(f"Rekordów: {len(df)} | Zakres: {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")


if __name__ == "__main__":
    main()
