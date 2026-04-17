"""
Orkiestrator pipeline danych PV.

Kroki:
  1. Pobierz dane produkcji PV z ENTSO-E (instrat) i przeskaluj per capita do miasta
  2. Pobierz dane pogodowe z Open-Meteo
  3. Polacz w jeden dataset
  4. Zapisz do data/solar_dataset_tauron.csv w formacie zgodnym z main_model.ipynb

Uzycie:
    python run_pipeline.py
    python run_pipeline.py --city Gliwice --start 2023-01-01 --end 2025-12-31
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from zbieraczka_danych_oze import pobierz_fotowoltaike_godzinowo
from class_weather_api import WeatherAPI
from merge_dataset import merge_dataset

# Kolumny string/meta ktore nie sa cechami modelu
_DROP_COLS = {"city", "lat", "lon"}

# Mapowanie nazw kolumn nowego pipeline -> nazewnictwo modelu
_RENAME = {"Produkcja_PV_Godz_MWh": "production_mwh"}


def run_pipeline(
    city: str = "Gliwice",
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
) -> None:
    pipeline_dir = Path(__file__).parent
    project_root = pipeline_dir.parent
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    start_s = start_date.replace("-", "")
    end_s = end_date.replace("-", "")

    print(f"\n{'=' * 55}")
    print(f"  Pipeline PV | {city} | {start_date} -> {end_date}")
    print(f"{'=' * 55}\n")

    # --- Krok 1: produkcja PV (ENTSO-E / instrat) ---
    print("[1/3] Pobieranie danych produkcji PV...")
    pv_path = pipeline_dir / f"fotowoltaika_godzinowo_{city}_{start_s}_{end_s}.csv"
    pobierz_fotowoltaike_godzinowo(
        city=city,
        start_date=start,
        end_date=end,
        output_path=str(pv_path),
    )

    # --- Krok 2: dane pogodowe (Open-Meteo) ---
    print("\n[2/3] Pobieranie danych pogodowych...")
    weather_path = pipeline_dir / f"weather_{city}_real.csv"
    api = WeatherAPI()
    api.upload_weather_data(
        CITY=city,
        START_DATE=start_date,
        END_DATE=end_date,
        TIMEZONE="UTC",
        OUTPUT=str(weather_path),
    )
    api.csv_weather_api()

    # --- Krok 3: merge (zapisuje tymczasowo w pipeline_dir) ---
    print("\n[3/3] Laczenie datasetow...")
    df: pd.DataFrame = merge_dataset(
        city=city,
        start_date=start_date,
        end_date=end_date,
        weather_csv=str(weather_path),
        pv_csv=str(pv_path),
    )

    # --- Krok 4: dostosowanie do formatu main_model.ipynb ---
    df = df.drop(columns=[c for c in _DROP_COLS if c in df.columns])
    df = df.rename(columns=_RENAME)

    output_path = project_root / "data" / "solar_dataset_tauron.csv"
    output_path.parent.mkdir(exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"\n{'=' * 55}")
    print(f"  Gotowy dataset: {output_path}")
    print(f"  Wiersze: {len(df):,} | Kolumny: {df.shape[1]}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline danych PV")
    parser.add_argument("--city", default="Gliwice", help="Nazwa miasta z miasta.csv")
    parser.add_argument("--start", default="2023-01-01", help="Data poczatkowa YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="Data koncowa YYYY-MM-DD")
    args = parser.parse_args()

    run_pipeline(city=args.city, start_date=args.start, end_date=args.end)
