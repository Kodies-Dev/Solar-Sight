"""City registry and solar geometry."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from solarsight.config import CITIES_CSV


@lru_cache(maxsize=4)
def _read_cities(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_cities(path: Path = CITIES_CSV) -> pd.DataFrame:
    """Return the city registry (columns: city, lat, lon, population)."""
    return _read_cities(Path(path)).copy()


def load_city(city: str, path: Path = CITIES_CSV) -> dict:
    """Look up one city (case-insensitive). Raises ValueError if it is unknown."""
    cities = load_cities(path)
    row = cities.loc[cities["city"].str.lower() == city.lower()]
    if row.empty:
        available = ", ".join(cities["city"])
        raise ValueError(f"Unknown city '{city}'. Available: {available}")
    return row.iloc[0].to_dict()


def solar_elevation_deg(timestamps_utc: pd.Series, lat: float, lon: float) -> np.ndarray:
    """Sun elevation above the horizon in degrees (simplified NOAA formula).

    Negative values mean the sun is below the horizon. This is the most important
    non-linear feature for PV: panels produce roughly in proportion to
    sin(elevation) and nothing below the horizon.
    """
    day_of_year = timestamps_utc.dt.dayofyear.to_numpy()
    hour_utc = timestamps_utc.dt.hour.to_numpy() + timestamps_utc.dt.minute.to_numpy() / 60.0

    gamma = 2 * np.pi / 365 * (day_of_year - 1)
    declination = (0.006918
                   - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
                   - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
                   - 0.002697 * np.cos(3 * gamma) + 0.00148 * np.sin(3 * gamma))
    equation_of_time_min = 229.18 * (0.000075
                                     + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma)
                                     - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))

    solar_time_min = hour_utc * 60 + equation_of_time_min + 4 * lon
    hour_angle = np.deg2rad((solar_time_min / 4) - 180)

    lat_rad = np.deg2rad(lat)
    sin_elevation = (np.sin(lat_rad) * np.sin(declination)
                     + np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle))
    return np.rad2deg(np.arcsin(np.clip(sin_elevation, -1.0, 1.0)))
