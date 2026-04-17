from pathlib import Path

import requests
import pandas as pd
import numpy as np


def solar_elevation_deg(timestamps_utc: pd.Series, lat: float, lon: float) -> np.ndarray:
    # Wzor astronomiczny NOAA (uproszczony). Zwraca kat Slonca nad horyzontem
    # w stopniach. Ujemne wartosci = Slonce ponizej horyzontu (noc).
    # Najwazniejsza nieliniowa cecha dla predykcji PV — panele produkuja
    # proporcjonalnie do sin(elevation), zero ponizej horyzontu.
    doy = timestamps_utc.dt.dayofyear.to_numpy()
    hour_utc = timestamps_utc.dt.hour.to_numpy() + timestamps_utc.dt.minute.to_numpy() / 60.0

    gamma = 2 * np.pi / 365 * (doy - 1)
    decl = (0.006918
            - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
            - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
            - 0.002697 * np.cos(3 * gamma) + 0.00148 * np.sin(3 * gamma))
    eqtime_min = 229.18 * (0.000075
                           + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma)
                           - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))

    solar_time_min = hour_utc * 60 + eqtime_min + 4 * lon
    hour_angle = np.deg2rad((solar_time_min / 4) - 180)

    lat_rad = np.deg2rad(lat)
    sin_elev = (np.sin(lat_rad) * np.sin(decl)
                + np.cos(lat_rad) * np.cos(decl) * np.cos(hour_angle))
    sin_elev = np.clip(sin_elev, -1.0, 1.0)
    return np.rad2deg(np.arcsin(sin_elev))

CITIES_CSV = "miasta.csv"
DEFAULT_CITY = "Gliwice"


def load_city(city: str, cities_csv: str = CITIES_CSV) -> dict:
    path = Path(cities_csv)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    cities = pd.read_csv(path)
    row = cities.loc[cities["city"].str.lower() == city.lower()]
    if row.empty:
        raise ValueError(f"Nie znaleziono miasta '{city}' w {path}")
    return row.iloc[0].to_dict()


class WeatherAPI:
    def __init__(self):
        self.url = "https://archive-api.open-meteo.com/v1/archive"

    def upload_weather_data(self,
                   CITY=DEFAULT_CITY,
                   START_DATE="2023-01-01",
                   END_DATE="2025-12-31",
                   TIMEZONE="UTC",
                   OUTPUT=None):

        city_info = load_city(CITY)

        self.CITY = city_info["city"]
        self.LATITUDE = float(city_info["lat"])
        self.LONGITUDE = float(city_info["lon"])
        self.START_DATE = START_DATE
        self.END_DATE = END_DATE
        self.TIMEZONE = TIMEZONE
        self.OUTPUT = OUTPUT or f"weather_{self.CITY}_real.csv"

        # shortwave_radiation [W/m2] zastepuje uv_index, ktory w endpointcie
        # historycznym Open-Meteo nie jest dostepny (zwraca null). Promieniowanie
        # krotkofalowe jest bezposrednim wejsciem energetycznym dla paneli PV,
        # wiec jest lepszym predyktorem niz UV.
        params = {
            "latitude": self.LATITUDE,
            "longitude": self.LONGITUDE,
            "start_date": self.START_DATE,
            "end_date": self.END_DATE,
            "hourly": ["shortwave_radiation", "direct_radiation", "diffuse_radiation",
                       "cloud_cover", "sunshine_duration",
                       "temperature_2m", "wind_speed_10m",
                       "relative_humidity_2m", "surface_pressure"],
            "timezone": self.TIMEZONE
        }

        response = requests.get(self.url, params=params)
        if response.status_code != 200:
            raise Exception(f"Blad API: {response.status_code}")

        data = response.json()["hourly"]


        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["time"], utc=True),
            "shortwave_radiation_wm2": data["shortwave_radiation"],
            "direct_radiation_wm2": data["direct_radiation"],
            "diffuse_radiation_wm2": data["diffuse_radiation"],
            "cloud_cover_pct": data["cloud_cover"],
            "sunshine_pct": data["sunshine_duration"],
            "temperature_c": data["temperature_2m"],
            "wind_speed_ms": data["wind_speed_10m"],
            "humidity_pct": data["relative_humidity_2m"],
            "pressure_hpa": data["surface_pressure"]
        })


        #sekundy slonca na godzine i na procenty
        df["sunshine_pct"] = (df["sunshine_pct"] / 3600 * 100).round(1)

        df["city"] = self.CITY
        df["lat"] = self.LATITUDE
        df["lon"] = self.LONGITUDE

        df["date"] = df["timestamp"].dt.date
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_year"] = df["timestamp"].dt.dayofyear
        df["month"] = df["timestamp"].dt.month

        #trzeba zrobic funckje cos i sinus tak by model rozumial ze zero jest  po 24 h
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
        df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

        df["solar_elevation_deg"] = solar_elevation_deg(df["timestamp"], self.LATITUDE, self.LONGITUDE)

        # Radiation + sunshine: brak danych = noc/brak pomiaru -> 0.0 ma sens fizyczny.
        # Temperatura/cisnienie/wilgotnosc/wiatr: 0.0 bylby nierealistyczny i mylacy
        # dla modelu, wiec interpolujemy liniowo i w razie NaN na krancach uzupelniamy
        # sasiedziami (ffill/bfill).
        radiation_cols = ["shortwave_radiation_wm2", "direct_radiation_wm2",
                          "diffuse_radiation_wm2", "sunshine_pct", "cloud_cover_pct"]
        continuous_cols = ["temperature_c", "wind_speed_ms", "humidity_pct", "pressure_hpa"]

        df[radiation_cols] = df[radiation_cols].fillna(0.0)
        df[continuous_cols] = (df[continuous_cols]
                               .interpolate(method="linear", limit_direction="both")
                               .ffill()
                               .bfill())
        self.df = df


    def csv_weather_api(self):
        self.df.to_csv(self.OUTPUT, index=False)

    def shopweather_api(self):
        print(self.df.head())
        print(f'{"-"*10}Kolumny{"-"*10}')
        print(self.df.columns)
