"""
meteo_forecast.py — pobiera prognozę z Open-Meteo (darmowe, bez klucza).

Dane: pogodowe (fallback dla Google) + solarne (shortwave/direct/diffuse radiation,
      sunshine_pct) — jedyne źródło danych solarnych w pipeline prognozy.
Zakres: 72h do przodu (domyślnie), rozdzielczość godzinowa.
Wszystkie timestampy i cechy czasowe (hour, day_of_year) w UTC —
spójne z danymi treningowymi z pipeline/class_weather_api.py.

Użycie:
    python meteo_forecast.py
    python meteo_forecast.py --hours 48 --city Gliwice
    python meteo_forecast.py --output moja_prognoza_meteo.csv
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
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


def fetch_meteo(lat: float, lon: float, hours: int) -> pd.DataFrame:
    # Wyrownanie zakresu z Google Weather (rolling window od biezacej godziny):
    # prosimy Open-Meteo o dokladnie te same N godzin, zaczynajac od biezacej
    # pelnej godziny UTC. Dzieki temu merge w merge_forecasts.py nie gubi danych.
    start_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_hour = start_hour + timedelta(hours=hours - 1)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "cloud_cover",
            "wind_speed_10m",
            "uv_index",
            "shortwave_radiation",       # GHI -> shortwave_radiation_wm2 w treningu
            "direct_radiation",          # DNI bezpośrednie -> direct_radiation_wm2 w treningu
            "diffuse_radiation",         # DHI -> diffuse_radiation_wm2 w treningu
            "direct_normal_irradiance",  # DNI (nie używane przez model, referencja)
            "sunshine_duration",
        ]),
        "start_hour": start_hour.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end_hour.strftime("%Y-%m-%dT%H:%M"),
        # UTC — spójne z danymi treningowymi (pipeline używa timezone=UTC)
        "timezone": "UTC",
    }

    print(f"Pobieranie {hours}h prognozy z Open-Meteo ({lat}, {lon})"
          f" [{start_hour:%Y-%m-%d %H:%M} -> {end_hour:%Y-%m-%d %H:%M} UTC]...")
    r = requests.get(url, params=params, timeout=30)
    if r.status_code != 200:
        print(f"BŁĄD {r.status_code}: {r.text[:500]}")
        sys.exit(1)

    hourly = r.json().get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        print("Brak danych w odpowiedzi!")
        sys.exit(1)

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(times, utc=True),
        "temperature_c": hourly.get("temperature_2m"),
        "humidity_pct": hourly.get("relative_humidity_2m"),
        "pressure_hpa": hourly.get("surface_pressure"),
        "cloud_cover_pct": hourly.get("cloud_cover"),
        "wind_speed_ms": hourly.get("wind_speed_10m"),
        "uv_index": hourly.get("uv_index"),
        # Nazwy zgodne ze schematem treningowym
        "shortwave_radiation_wm2": hourly.get("shortwave_radiation"),
        "direct_radiation_wm2": hourly.get("direct_radiation"),
        "diffuse_radiation_wm2": hourly.get("diffuse_radiation"),
        "sunshine_duration_s": hourly.get("sunshine_duration"),
    })

    df["sunshine_pct"] = (df["sunshine_duration_s"] / 3600 * 100).clip(0, 100).round(1)
    df = df.drop(columns=["sunshine_duration_s"])

    print(f"Pobrano {len(df)} rekordów")
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
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
    ap = argparse.ArgumentParser(description="Open-Meteo -> CSV")
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--city", default=DEFAULT_CITY)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    city_info = load_city(args.city)
    df = fetch_meteo(float(city_info["lat"]), float(city_info["lon"]), args.hours)
    df = add_features(df)

    cols = [
        "timestamp", "date", "hour", "day_of_year", "month",
        "hour_sin", "hour_cos", "doy_sin", "doy_cos",
        "uv_index", "cloud_cover_pct",
        "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa",
        "sunshine_pct",
        "shortwave_radiation_wm2", "direct_radiation_wm2", "diffuse_radiation_wm2",
    ]
    df = df[[c for c in cols if c in df.columns]]

    path = args.output or f"meteo_forecast_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"
    df.to_csv(path, index=False)
    print(f"\nZapisano: {path}")
    print(f"Rekordów: {len(df)} | Zakres: {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")


if __name__ == "__main__":
    main()
