"""
run_forecast.py - orkiestrator pipeline prognozy 24h (Open-Meteo + Google + merge).

Uruchamia po kolei:
    1. meteo_forecast.py  -> meteo_forecast_*.csv   (solarne + fallback pogodowy)
    2. google_forecast.py -> google_forecast_*.csv  (pogodowe primary, klucz z .env)
    3. merge_forecasts.py -> forecast_final.csv     (gotowy input dla modelu)

Klucz API: czytany automatycznie z .env w korzeniu projektu
(GOOGLE_WEATHER_API_KEY) lub przekazywany przez --api-key.

Uzycie:
    python run_forecast.py
    python run_forecast.py --hours 48 --city Gliwice
    python run_forecast.py --output moja_prognoza.csv --keep-intermediate
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

FORECAST_DIR = Path(__file__).parent
PROJECT_ROOT = FORECAST_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")


def run_step(label: str, cmd: list[str], env: dict | None = None) -> None:
    print(f"\n{'=' * 60}\n[{label}]  {' '.join(cmd)}\n{'=' * 60}")
    result = subprocess.run(cmd, cwd=FORECAST_DIR, env=env)
    if result.returncode != 0:
        print(f"\nBLAD: krok '{label}' zakonczony kodem {result.returncode}")
        sys.exit(result.returncode)


def cleanup_intermediate() -> None:
    removed = 0
    for pattern in ("meteo_forecast_*.csv", "google_forecast_*.csv"):
        for f in glob.glob(str(FORECAST_DIR / pattern)):
            Path(f).unlink()
            removed += 1
    if removed:
        print(f"Usunieto {removed} posrednich plikow CSV.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Orkiestrator pipeline prognozy PV")
    ap.add_argument("--hours", type=int, default=24, help="horyzont prognozy (default 24)")
    ap.add_argument("--city", default="Gliwice")
    ap.add_argument("--output", default="forecast_final.csv", help="koncowy CSV")
    ap.add_argument("--api-key", default=None, help="klucz Google (domyslnie z .env)")
    ap.add_argument("--keep-intermediate", action="store_true",
                    help="zachowaj meteo_forecast_*.csv i google_forecast_*.csv")
    args = ap.parse_args()

    api_key = args.api_key or os.environ.get("GOOGLE_WEATHER_API_KEY")
    if not api_key:
        print("BLAD: brak klucza Google. Ustaw GOOGLE_WEATHER_API_KEY w .env lub uzyj --api-key.")
        sys.exit(1)

    py = sys.executable

    run_step("1/3 Open-Meteo", [
        py, "meteo_forecast.py",
        "--hours", str(args.hours),
        "--city", args.city,
    ])

    # Klucz przez env zeby nie wyciekl w logu komendy
    google_env = {**os.environ, "GOOGLE_WEATHER_API_KEY": api_key}
    run_step("2/3 Google Weather", [
        py, "google_forecast.py",
        "--hours", str(args.hours),
        "--city", args.city,
    ], env=google_env)

    run_step("3/3 Merge", [
        py, "merge_forecasts.py",
        "--output", args.output,
        "--city", args.city,
    ])

    if not args.keep_intermediate:
        cleanup_intermediate()

    final_path = FORECAST_DIR / args.output
    print(f"\n{'=' * 60}\nGOTOWE: {final_path}\n{'=' * 60}")


if __name__ == "__main__":
    main()
