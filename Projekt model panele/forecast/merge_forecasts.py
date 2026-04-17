"""
merge_forecasts.py — łączy prognozy z Google Weather API i Open-Meteo.

Google = źródło PRIMARY dla danych pogodowych (temperatura, wiatr, wilgotność,
         ciśnienie, zachmurzenie)
Meteo  = JEDYNE źródło danych solarnych (shortwave/direct/diffuse radiation,
         sunshine_pct) + FALLBACK dla danych pogodowych gdy Google zwróci NaN

Wyjście zawiera dokładnie te same kolumny co dane treningowe (minus production_mwh),
gotowe do bezpośredniego przekazania do modelu.

Użycie:
    python merge_forecasts.py
    python merge_forecasts.py --google google_forecast_*.csv --meteo meteo_forecast_*.csv
    python merge_forecasts.py --output forecast_final.csv --city Gliwice
"""

import argparse
import glob
import sys
from datetime import timezone
from pathlib import Path

import numpy as np
import pandas as pd

CITIES_CSV = Path(__file__).parent.parent / "pipeline" / "miasta.csv"
DEFAULT_CITY = "Gliwice"

# Kolumny pogodowe gdzie Google jest primary, Meteo jest fallback
_WEATHER_COLS = [
    "cloud_cover_pct",
    "temperature_c",
    "wind_speed_ms",
    "humidity_pct",
    "pressure_hpa",
]

# Kolumny solarne — tylko Meteo je dostarcza
_SOLAR_COLS = [
    "shortwave_radiation_wm2",
    "direct_radiation_wm2",
    "diffuse_radiation_wm2",
    "sunshine_pct",
]

# Finalny porządek kolumn zgodny ze schematem treningowym
_OUTPUT_COLS = [
    "timestamp", "date", "hour", "day_of_year", "month",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    "shortwave_radiation_wm2", "direct_radiation_wm2", "diffuse_radiation_wm2",
    "cloud_cover_pct", "sunshine_pct",
    "temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa",
    "solar_elevation_deg",
]


def load_city(city: str) -> dict:
    df = pd.read_csv(CITIES_CSV)
    row = df.loc[df["city"].str.lower() == city.lower()]
    if row.empty:
        raise ValueError(f"Nie znaleziono miasta '{city}' w {CITIES_CSV}")
    return row.iloc[0].to_dict()


def solar_elevation_deg(timestamps_utc: pd.Series, lat: float, lon: float) -> np.ndarray:
    """Kąt Słońca nad horyzontem (wzór NOAA). Ujemne = noc."""
    doy = timestamps_utc.dt.dayofyear.to_numpy()
    hour_utc = timestamps_utc.dt.hour.to_numpy() + timestamps_utc.dt.minute.to_numpy() / 60.0
    gamma = 2 * np.pi / 365 * (doy - 1)
    decl = (0.006918
            - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
            - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
            - 0.002697 * np.cos(3 * gamma) + 0.00148  * np.sin(3 * gamma))
    eqtime = 229.18 * (0.000075
                       + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma)
                       - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    solar_time = hour_utc * 60 + eqtime + 4 * lon
    hour_angle = np.deg2rad(solar_time / 4 - 180)
    lat_rad = np.deg2rad(lat)
    sin_elev = (np.sin(lat_rad) * np.sin(decl)
                + np.cos(lat_rad) * np.cos(decl) * np.cos(hour_angle))
    return np.rad2deg(np.arcsin(np.clip(sin_elev, -1.0, 1.0)))


def find_latest(prefix: str) -> str | None:
    candidates = sorted(glob.glob(f"{prefix}_*.csv"), reverse=True)
    return candidates[0] if candidates else None


def load_csv(path: str, label: str) -> pd.DataFrame:
    print(f"Wczytywanie {label}: {path}")
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        print(f"BŁĄD: Brak kolumny 'timestamp' w {path}")
        sys.exit(1)
    print(f"  -> {len(df)} rekordów | {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
    return df


def merge(google: pd.DataFrame, meteo: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(google, meteo, on="timestamp", how="left", suffixes=("", "_meteo"))

    # Pogodowe: Google primary, Meteo fallback
    for col in _WEATHER_COLS:
        meteo_col = f"{col}_meteo"
        if meteo_col in merged.columns:
            filled = merged[col].isna().sum()
            merged[col] = merged[col].fillna(merged[meteo_col])
            if filled:
                print(f"  Uzupełniono {filled} braków w '{col}' z Meteo")
            merged.drop(columns=[meteo_col], inplace=True)

    # Solarne: tylko Meteo — dodaj bezpośrednio (bez sufiksu, nie ma konfliktu)
    for col in _SOLAR_COLS:
        meteo_col = f"{col}_meteo"
        if col not in merged.columns and meteo_col in merged.columns:
            merged[col] = merged[meteo_col]
        if meteo_col in merged.columns:
            merged.drop(columns=[meteo_col], inplace=True)

    # Kolumny czasowe: Google primary, Meteo fallback
    for col in ["date", "hour", "day_of_year", "month",
                "hour_sin", "hour_cos", "doy_sin", "doy_cos"]:
        meteo_col = f"{col}_meteo"
        if meteo_col in merged.columns:
            merged[col] = merged[col].fillna(merged[meteo_col])
            merged.drop(columns=[meteo_col], inplace=True)

    # Usuń pozostałe kolumny _meteo
    merged.drop(columns=[c for c in merged.columns if c.endswith("_meteo")], inplace=True)

    return merged


def main():
    ap = argparse.ArgumentParser(description="Merge Google Weather + Open-Meteo")
    ap.add_argument("--google", default=None)
    ap.add_argument("--meteo", default=None)
    ap.add_argument("--output", default="forecast_final.csv")
    ap.add_argument("--city", default=DEFAULT_CITY)
    args = ap.parse_args()

    google_path = args.google or find_latest("google_forecast")
    meteo_path = args.meteo or find_latest("meteo_forecast")

    if not google_path:
        print("BŁĄD: Brak pliku Google CSV.\n  Uruchom: python google_forecast.py --api-key KLUCZ")
        sys.exit(1)
    if not meteo_path:
        print("BŁĄD: Brak pliku Meteo CSV.\n  Uruchom: python meteo_forecast.py")
        sys.exit(1)

    google_df = load_csv(google_path, "Google Weather")
    meteo_df = load_csv(meteo_path, "Open-Meteo")

    print("\nMergowanie...")
    df = merge(google_df, meteo_df)

    # Oblicz solar_elevation_deg na UTC timestampach
    city_info = load_city(args.city)
    ts_utc = pd.to_datetime(df["timestamp"], utc=True)
    df["solar_elevation_deg"] = solar_elevation_deg(ts_utc, float(city_info["lat"]), float(city_info["lon"]))

    # Zachowaj tylko kolumny wyjściowe zgodne ze schematem treningowym
    df = df[[c for c in _OUTPUT_COLS if c in df.columns]]

    df.to_csv(args.output, index=False)

    print(f"\n{'=' * 55}")
    print(f"Zapisano: {args.output}")
    print(f"Rekordów: {len(df)} | Kolumn: {df.shape[1]}")
    print(f"Zakres:   {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
    print(f"\nKompletność danych:")
    for col in _OUTPUT_COLS[2:]:
        if col in df.columns:
            ok = df[col].notna().sum()
            total = len(df)
            flag = "OK" if ok == total else f"BRAK {total - ok}"
            print(f"  {col:30s}: {ok}/{total} {flag}")
    print("=" * 55)


if __name__ == "__main__":
    main()
