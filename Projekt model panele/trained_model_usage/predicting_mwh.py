import joblib
import pandas as pd
import numpy as np
import os
import logging
import requests
from functools import lru_cache
from datetime import datetime, timedelta, timezone


logger = logging.getLogger(__name__)


FOLDER_SKRYPTU = os.path.dirname(os.path.abspath(__file__))
PATH_MODEL     = os.path.join(FOLDER_SKRYPTU, '..', 'artifacts', 'model_bez_lagow.joblib')
PATH_CITIES    = os.path.join(FOLDER_SKRYPTU, '..', 'pipeline', 'miasta.csv')


@lru_cache(maxsize=1)
def _get_model():
    if not os.path.exists(PATH_MODEL):
        raise FileNotFoundError(f"Model not found: {PATH_MODEL}")
    logger.info("Loading model from %s", PATH_MODEL)
    return joblib.load(PATH_MODEL)


# Weather forecast cache — avoids re-hitting Open-Meteo on every slider tick
_WEATHER_CACHE: dict = {}
_WEATHER_CACHE_TTL_S = 900  # 15 minutes


def _get_weather_df(city: str) -> pd.DataFrame:
    cities = _load_cities()
    city_key = city.lower()
    if city_key not in cities:
        available = [c.capitalize() for c in cities.keys()]
        raise ValueError(f"Unknown city '{city}'. Available: {available}")

    now_ts = datetime.now(timezone.utc).timestamp()
    cached = _WEATHER_CACHE.get(city_key)
    if cached and (now_ts - cached[1]) < _WEATHER_CACHE_TTL_S:
        logger.info("Weather cache hit for %s (age: %.0fs)", city.capitalize(), now_ts - cached[1])
        return cached[0].copy()

    lat = cities[city_key]['lat']
    lon = cities[city_key]['lon']
    logger.info("Fetching weather forecast for %s (%s, %s)", city.capitalize(), lat, lon)
    df = _fetch_forecast(lat, lon, hours=24)
    _WEATHER_CACHE[city_key] = (df.copy(), now_ts)
    return df


# WMO weather interpretation codes — https://open-meteo.com/en/docs
_WMO_STATUS = {
    0:  "Clear",
    1:  "Mainly clear",
    2:  "Partly cloudy",
    3:  "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    99: "Thunderstorm with heavy hail",
}




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
            "sunshine_duration", "weather_code",
        ]),
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour":   end.strftime("%Y-%m-%dT%H:%M"),
        "timezone":   "UTC",
    }

    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Open-Meteo API error {r.status_code}: {r.text[:300]}")

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
        "weather_code":            hourly.get("weather_code"),
    })

    # sunshine seconds
    df["sunshine_pct"] = (df["sunshine_duration_s"] / 3600 * 100).clip(0, 100).round(1)
    df.drop(columns=["sunshine_duration_s"], inplace=True)

    # fill NaN in UV (night)
    df["uv_index"] = df["uv_index"].fillna(0.0).round(2)

    # time columns
    df["date"]        = ts_utc.dt.strftime("%Y-%m-%d")
    df["hour"]        = ts_utc.dt.hour.astype(int)
    df["day_of_year"] = ts_utc.dt.dayofyear.astype(int)
    df["month"]       = ts_utc.dt.month.astype(int)

    # cyclical encoding
    df["hour_sin"] = np.round(np.sin(2 * np.pi * df["hour"] / 24), 4)
    df["hour_cos"] = np.round(np.cos(2 * np.pi * df["hour"] / 24), 4)
    df["doy_sin"]  = np.round(np.sin(2 * np.pi * df["day_of_year"] / 365), 4)
    df["doy_cos"]  = np.round(np.cos(2 * np.pi * df["day_of_year"] / 365), 4)


    df["solar_elevation_deg"] = _solar_elevation(ts_utc, lat, lon)


    df["installed_pv_mw_pl"] = 22500.0


    df["timestamp"] = ts_utc.dt.strftime("%Y-%m-%d %H:%M:%S")

    return df




def predykuj(city: str = "gliwice") -> pd.DataFrame:

    df = _get_weather_df(city)
    model = _get_model()

    required_features = list(model.feature_names_in_)
    for col in required_features:
        if col not in df.columns:
            logger.warning("Missing column '%s' — filling with zeros", col)
            df[col] = 0.0

    X = df[required_features]

    prediction = model.predict(X)
    prediction = np.maximum(0, prediction).round(3)

    weather_code = df['weather_code'].fillna(0).astype(int)

    results = pd.DataFrame({
        'timestamp':       df['timestamp'],
        'hour':            df['hour'],
        'predykcja_mwh':   prediction,
        'temperature_c':   df['temperature_c'].round(1),
        'uv_index':        df['uv_index'],
        'cloud_cover_pct': df['cloud_cover_pct'].fillna(0).astype(int),
        'weather_code':    weather_code,
        'status':          weather_code.map(_WMO_STATUS).fillna("Unknown"),
    })

    night_hours = [ 22, 23, 0, 1, 2, 3, ]
    results.loc[results['hour'].isin(night_hours), 'predykcja_mwh'] = 0.0

    results.sort_values(by='hour', ascending=True, inplace=True)

    return results


def symuluj(city: str = "gliwice", cloud_cover: float = 0.0) -> pd.DataFrame:
    """Re-run prediction with cloud cover forced to an absolute value [0, 100].

    Automatically rescales shortwave & direct radiation to stay physically
    consistent (more clouds → less radiation).
    """
    df = _get_weather_df(city)

    base_cloud = df['cloud_cover_pct'].fillna(0).clip(0, 100)
    new_cloud  = pd.Series(float(cloud_cover), index=df.index).clip(0, 100)

    # Radiation attenuation — empirical linear approximation.
    # At 100% cloud cover, direct radiation drops by ~75%.
    k = 0.75
    base_factor = (1 - base_cloud / 100.0 * k).clip(lower=0.05)
    new_factor  = (1 - new_cloud  / 100.0 * k).clip(lower=0.0)
    ratio = new_factor / base_factor

    df['cloud_cover_pct']         = new_cloud
    df['shortwave_radiation_wm2'] = (df['shortwave_radiation_wm2'].fillna(0) * ratio).clip(lower=0)
    df['direct_radiation_wm2']    = (df['direct_radiation_wm2'].fillna(0) * ratio).clip(lower=0)

    model = _get_model()
    required_features = list(model.feature_names_in_)
    for col in required_features:
        if col not in df.columns:
            df[col] = 0.0

    X = df[required_features]

    prediction = model.predict(X)
    prediction = np.maximum(0, prediction).round(3)

    results = pd.DataFrame({
        'timestamp':       df['timestamp'],
        'hour':            df['hour'],
        'predykcja_mwh':   prediction,
        'cloud_cover_pct': new_cloud.astype(int),
    })

    night_hours = [22, 23, 0, 1, 2, 3]
    results.loc[results['hour'].isin(night_hours), 'predykcja_mwh'] = 0.0

    results.sort_values(by='hour', ascending=True, inplace=True)

    return results
