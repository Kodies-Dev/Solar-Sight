import joblib
import pandas as pd
import numpy as np
import os
import sys
import requests
from datetime import datetime, timedelta, timezone




FOLDER_SKRYPTU = os.path.dirname(os.path.abspath(__file__))
PATH_MODEL     = os.path.join(FOLDER_SKRYPTU, '..', 'artifacts', 'model_bez_lagow.joblib')
PATH_CITIES    = os.path.join(FOLDER_SKRYPTU, '..', 'pipeline', 'miasta.csv')




def _load_cities() -> dict:

    df = pd.read_csv(PATH_CITIES)
    return {
        row['city'].lower(): {'lat': row['lat'], 'lon': row['lon']}
        for _, row in df.iterrows()
    }


def _solar_elevation(ts_utc: pd.Series, lat: float, lon: float) -> np.ndarray:

    doy      = ts_utc.dt.dayofyear.to_numpy()
    hour_utc = ts_utc.dt.hour.to_numpy() + ts_utc.dt.minute.to_numpy() / 60.0
    gamma    = 2 * np.pi / 365 * (doy - 1)
    decl     = (0.006918
                - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
                - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
                - 0.002697 * np.cos(3 * gamma) + 0.00148  * np.sin(3 * gamma))
    eqtime   = 229.18 * (0.000075
                         + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma)
                         - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    solar_t  = hour_utc * 60 + eqtime + 4 * lon
    ha       = np.deg2rad(solar_t / 4 - 180)
    lat_r    = np.deg2rad(lat)
    sin_elev = (np.sin(lat_r) * np.sin(decl)
                + np.cos(lat_r) * np.cos(decl) * np.cos(ha))
    return np.round(np.rad2deg(np.arcsin(np.clip(sin_elev, -1.0, 1.0))), 6)


def _fetch_forecast(lat: float, lon: float, hours: int = 24) -> pd.DataFrame:

    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end   = start + timedelta(hours=hours - 1)

    params = {
        "latitude":   lat,
        "longitude":  lon,
        "hourly": ",".join([
            "temperature_2m", "relative_humidity_2m", "surface_pressure",
            "cloud_cover", "wind_speed_10m", "uv_index",
            "shortwave_radiation", "direct_radiation", "diffuse_radiation",
            "sunshine_duration",
        ]),
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour":   end.strftime("%Y-%m-%dT%H:%M"),
        "timezone":   "UTC",
    }

    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
    if r.status_code != 200:
        print(f"BŁĄD API {r.status_code}: {r.text[:300]}")
        sys.exit(1)

    hourly = r.json().get("hourly", {})
    ts_utc = pd.Series(pd.to_datetime(hourly.get("time", []), utc=True))

    df = pd.DataFrame({
        "timestamp":               ts_utc,
        "temperature_c":           hourly.get("temperature_2m"),
        "humidity_pct":            hourly.get("relative_humidity_2m"),
        "pressure_hpa":            hourly.get("surface_pressure"),
        "cloud_cover_pct":         hourly.get("cloud_cover"),
        "wind_speed_ms":           hourly.get("wind_speed_10m"),
        "uv_index":                hourly.get("uv_index"),
        "shortwave_radiation_wm2": hourly.get("shortwave_radiation"),
        "direct_radiation_wm2":    hourly.get("direct_radiation"),
        "diffuse_radiation_wm2":   hourly.get("diffuse_radiation"),
        "sunshine_duration_s":     hourly.get("sunshine_duration"),
    })

    # sunshine sekundy
    df["sunshine_pct"] = (df["sunshine_duration_s"] / 3600 * 100).clip(0, 100).round(1)
    df.drop(columns=["sunshine_duration_s"], inplace=True)

    # uzupełnij NaN w UV (noc)
    df["uv_index"] = df["uv_index"].fillna(0.0).round(2)

    # kolumny czasowe
    df["date"]        = ts_utc.dt.strftime("%Y-%m-%d")
    df["hour"]        = ts_utc.dt.hour.astype(int)
    df["day_of_year"] = ts_utc.dt.dayofyear.astype(int)
    df["month"]       = ts_utc.dt.month.astype(int)

    # kodowanie cykliczne
    df["hour_sin"] = np.round(np.sin(2 * np.pi * df["hour"] / 24), 4)
    df["hour_cos"] = np.round(np.cos(2 * np.pi * df["hour"] / 24), 4)
    df["doy_sin"]  = np.round(np.sin(2 * np.pi * df["day_of_year"] / 365), 4)
    df["doy_cos"]  = np.round(np.cos(2 * np.pi * df["day_of_year"] / 365), 4)


    df["solar_elevation_deg"] = _solar_elevation(ts_utc, lat, lon)


    df["installed_pv_mw_pl"] = 22500.0


    df["timestamp"] = ts_utc.dt.strftime("%Y-%m-%d %H:%M:%S")

    return df




def predykuj(city: str = "gliwice") -> pd.DataFrame:



    cities = _load_cities()
    city_key = city.lower()

    if city_key not in cities:
        dostepne = [c.capitalize() for c in cities.keys()]
        raise ValueError(f"Nieznane miasto '{city}'. Dostępne: {dostepne}")

    lat = cities[city_key]['lat']
    lon = cities[city_key]['lon']

    print(f"Miasto: {city.capitalize()} ({lat}, {lon})")

    # sprawdź model
    if not os.path.exists(PATH_MODEL):
        raise FileNotFoundError(f"Nie znaleziono modelu: {PATH_MODEL}")

    # pobierz dane pogodowe
    print("Pobieram prognozę pogodową...")
    df = _fetch_forecast(lat, lon, hours=24)
    print(f"Pobrano {len(df)} godzin danych")

    # załaduj model
    model = joblib.load(PATH_MODEL)

    # uzupełnij brakujące kolumny
    required_features = list(model.feature_names_in_)
    for col in required_features:
        if col not in df.columns:
            print(f"UWAGA: brakuje '{col}' — uzupełniam zerami")
            df[col] = 0.0

    X = df[required_features]

    # predykcja
    predykcja = model.predict(X)
    predykcja = np.maximum(0, predykcja).round(3)

    wyniki = pd.DataFrame({
        'timestamp':     df['timestamp'],
        'hour':          df['hour'],
        'predykcja_mwh': predykcja
    })

    wyniki.sort_values(by='hour', ascending=True, inplace=True)

    return wyniki


