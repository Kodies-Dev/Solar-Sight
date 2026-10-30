"""Hourly PV production forecasts and the cloud-cover what-if simulation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from solarsight.config import DEFAULT_CITY, MODEL_PATH, TARGET_COLUMN
from solarsight.forecast.open_meteo import build_model_input, fetch_forecast
from solarsight.geo import load_city

logger = logging.getLogger(__name__)

FORECAST_HOURS = 24
WEATHER_CACHE_TTL_S = 900  # 15 minutes: repeated what-if requests reuse one forecast
NIGHT_HOURS_UTC = [22, 23, 0, 1, 2, 3]

# At 100% cloud cover direct radiation drops by ~75% (empirical linear approximation).
CLOUD_ATTENUATION = 0.75

# WMO weather interpretation codes, https://open-meteo.com/en/docs
WMO_WEATHER_STATUS = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with light hail", 99: "Thunderstorm with heavy hail",
}

_weather_cache: dict[str, tuple[pd.DataFrame, float]] = {}


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
    logger.info("Loading model from %s", MODEL_PATH)
    return joblib.load(MODEL_PATH)


def get_model_input(city: str) -> pd.DataFrame:
    """Forecast features for a city, cached for WEATHER_CACHE_TTL_S seconds."""
    city_info = load_city(city)  # raises ValueError for unknown cities
    city_key = city.lower()

    now = datetime.now(timezone.utc).timestamp()
    cached = _weather_cache.get(city_key)
    if cached and (now - cached[1]) < WEATHER_CACHE_TTL_S:
        logger.info("Weather cache hit for %s (age %.0fs)", city_info["city"], now - cached[1])
        return cached[0].copy()

    lat, lon = float(city_info["lat"]), float(city_info["lon"])
    logger.info("Fetching weather forecast for %s (%s, %s)", city_info["city"], lat, lon)
    df = build_model_input(fetch_forecast(lat, lon, hours=FORECAST_HOURS), lat, lon)
    _weather_cache[city_key] = (df.copy(), now)
    return df


def _predict_production(df: pd.DataFrame) -> np.ndarray:
    model = load_model()
    features = list(model.feature_names_in_)
    for column in features:
        if column not in df.columns:
            logger.warning("Missing feature '%s', filling with zeros", column)
            df[column] = 0.0
    prediction = model.predict(df[features])
    return np.maximum(0, prediction).round(3)


def _finalize(results: pd.DataFrame) -> pd.DataFrame:
    results.loc[results["hour"].isin(NIGHT_HOURS_UTC), TARGET_COLUMN] = 0.0
    return results.sort_values(by="hour", ascending=True)


def predict(city: str = DEFAULT_CITY) -> pd.DataFrame:
    """24 hourly production forecasts (MWh) with the weather the model saw."""
    df = get_model_input(city)
    production = _predict_production(df)
    weather_code = df["weather_code"].fillna(0).astype(int)

    results = pd.DataFrame({
        "timestamp": df["timestamp"],
        "hour": df["hour"],
        TARGET_COLUMN: production,
        "temperature_c": df["temperature_c"].round(1),
        "uv_index": df["uv_index"],
        "cloud_cover_pct": df["cloud_cover_pct"].fillna(0).astype(int),
        "weather_code": weather_code,
        "status": weather_code.map(WMO_WEATHER_STATUS).fillna("Unknown"),
    })
    return _finalize(results)


def simulate(city: str = DEFAULT_CITY, cloud_cover: float = 0.0) -> pd.DataFrame:
    """Re-run the forecast with cloud cover forced to ``cloud_cover`` percent [0, 100].

    Shortwave and direct radiation are rescaled with the same linear attenuation
    so the inputs stay physically consistent (more clouds -> less radiation).
    """
    df = get_model_input(city)

    base_cloud = df["cloud_cover_pct"].fillna(0).clip(0, 100)
    new_cloud = pd.Series(float(cloud_cover), index=df.index).clip(0, 100)

    base_factor = (1 - base_cloud / 100.0 * CLOUD_ATTENUATION).clip(lower=0.05)
    new_factor = (1 - new_cloud / 100.0 * CLOUD_ATTENUATION).clip(lower=0.0)
    ratio = new_factor / base_factor

    df["cloud_cover_pct"] = new_cloud
    df["shortwave_radiation_wm2"] = (df["shortwave_radiation_wm2"].fillna(0) * ratio).clip(lower=0)
    df["direct_radiation_wm2"] = (df["direct_radiation_wm2"].fillna(0) * ratio).clip(lower=0)

    results = pd.DataFrame({
        "timestamp": df["timestamp"],
        "hour": df["hour"],
        TARGET_COLUMN: _predict_production(df),
        "cloud_cover_pct": new_cloud.astype(int),
    })
    return _finalize(results)
