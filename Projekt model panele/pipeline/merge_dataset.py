"""
Laczy dane pogodowe (Open-Meteo) i produkcji PV (instrat/ENTSO-E) w jeden
dataset godzinowy, gotowy do treningu modelu predykcji produkcji fotowoltaiki.

Uzycie:
    python merge_dataset.py
albo:
    from merge_dataset import merge_dataset
    df = merge_dataset(city="Gliwice", start_date="2023-01-01", end_date="2025-12-31")
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

try:
    from class_weather_api import solar_elevation_deg
except ImportError:
    solar_elevation_deg = None


def merge_dataset(
    city: str = "Gliwice",
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    weather_csv: str | None = None,
    pv_csv: str | None = None,
    output_csv: str | None = None,
) -> pd.DataFrame:
    start = pd.Timestamp(start_date, tz="UTC")
    end = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(hours=23)

    base = Path(__file__).parent
    weather_path = Path(weather_csv) if weather_csv else base / f"weather_{city}_real.csv"
    pv_path = Path(pv_csv) if pv_csv else base / (
        f"fotowoltaika_godzinowo_{city}_"
        f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
    )

    weather = pd.read_csv(weather_path)
    pv = pd.read_csv(pv_path)

    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    pv["date"] = pd.to_datetime(pv["date"], utc=True)
    pv = pv.rename(columns={"date": "timestamp"})

    # Pelen zakres godzinowy UTC — zagwarantuje brak dziur (np. DST spring-forward
    # gubi 1h rocznie w danych ENTSO-E, bo API operuje w czasie lokalnym PL).
    full_index = pd.date_range(start, end, freq="h", tz="UTC")
    grid = pd.DataFrame({"timestamp": full_index})

    # Deduplikacja i alignment.
    weather = weather.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    pv = pv.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

    pv_cols = ["timestamp", "Produkcja_PV_Godz_MWh"]
    weather_cols = [c for c in weather.columns if c not in {"city", "lat", "lon"}]

    merged = grid.merge(weather[weather_cols], on="timestamp", how="left")
    merged = merged.merge(pv[pv_cols], on="timestamp", how="left")

    missing_pv = merged["Produkcja_PV_Godz_MWh"].isna().sum()
    missing_weather = merged["shortwave_radiation_wm2"].isna().sum()
    if missing_pv:
        # Brakujace godziny PV to zawsze 02:00 UTC ostatniej niedzieli marca
        # (zmiana czasu w PL). To noc -> produkcja = 0.
        print(f"Uzupelniam {missing_pv} brakujacych godzin PV wartoscia 0.0 (DST spring-forward)")
    if missing_weather:
        print(f"UWAGA: {missing_weather} brakujacych godzin pogody — interpoluje.")
        radiation_cols = [c for c in weather_cols if "radiation" in c or c in {"sunshine_pct", "cloud_cover_pct"}]
        continuous_cols = [c for c in weather_cols if c not in radiation_cols and c != "timestamp"]
        merged[radiation_cols] = merged[radiation_cols].fillna(0.0)
        merged[continuous_cols] = (merged[continuous_cols]
                                    .interpolate(method="linear", limit_direction="both")
                                    .ffill().bfill())

    merged["Produkcja_PV_Godz_MWh"] = merged["Produkcja_PV_Godz_MWh"].fillna(0.0)

    # Dopisz solar_elevation_deg jesli brakuje (np. gdy weather CSV pochodzi
    # ze starszej wersji class_weather_api.py sprzed dodania tej cechy).
    if "solar_elevation_deg" not in merged.columns and solar_elevation_deg is not None:
        cities = pd.read_csv(base / "miasta.csv")
        row = cities.loc[cities["city"].str.lower() == city.lower()].iloc[0]
        merged["solar_elevation_deg"] = solar_elevation_deg(
            merged["timestamp"], float(row["lat"]), float(row["lon"])
        )

    merged.insert(1, "city", city)

    if output_csv is None:
        output_csv = base / (
            f"dataset_{city}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
        )
    merged.to_csv(output_csv, index=False)
    print(f"Zapisano: {output_csv} ({len(merged)} wierszy, {merged.shape[1]} kolumn)")

    return merged


if __name__ == "__main__":
    merge_dataset()
