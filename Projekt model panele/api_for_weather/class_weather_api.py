import requests
import pandas as pd
import numpy as np


class WeatherAPI:
    def __init__(self):
        self.url = "https://archive-api.open-meteo.com/v1/archive"

    def upload_weather_data(self,
                   LATITUDE=50.29,
                   LONGITUDE=19.02,
                   START_DATE="2023-01-01",
                   END_DATE="2025-12-31",
                   TIMEZONE="Europe/Warsaw",
                   OUTPUT="weather_gliwice_real.csv"):


        self.LATITUDE = LATITUDE
        self.LONGITUDE = LONGITUDE
        self.START_DATE = START_DATE
        self.END_DATE = END_DATE
        self.TIMEZONE = TIMEZONE
        self.OUTPUT = OUTPUT

        params = {
            "latitude": self.LATITUDE,
            "longitude": self.LONGITUDE,
            "start_date": self.START_DATE,
            "end_date": self.END_DATE,
            "hourly": ["uv_index", "cloud_cover", "sunshine_duration",
                       "temperature_2m", "wind_speed_10m",
                       "relative_humidity_2m", "surface_pressure"],
            "timezone": self.TIMEZONE
        }

        response = requests.get(self.url, params=params)
        if response.status_code != 200:
            raise Exception(f"Blad API: {response.status_code}")

        data = response.json()["hourly"]


        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["time"]),
            "uv_index": data["uv_index"],
            "cloud_cover_pct": data["cloud_cover"],
            "sunshine_pct": data["sunshine_duration"],
            "temperature_c": data["temperature_2m"],
            "wind_speed_ms": data["wind_speed_10m"],
            "humidity_pct": data["relative_humidity_2m"],
            "pressure_hpa": data["surface_pressure"]
        })


        #sekundy slonca na godzine i na procenty
        df["sunshine_pct"] = (df["sunshine_pct"] / 3600 * 100).round(1)


        df["date"] = df["timestamp"].dt.date
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_year"] = df["timestamp"].dt.dayofyear
        df["month"] = df["timestamp"].dt.month

        #trzeba zrobic funckje cos i sinus tak by model rozumial ze zero jest  po 24 h
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
        df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

        df = df.fillna(0.0)
        self.df = df


    def csv_weather_api(self):
        self.df.to_csv(self.OUTPUT, index=False)

    def shopweather_api(self):
        print(self.df.head())
        print(f'{'-'*10}Kolumny{'-'*10}')
        print(self.df.columns)



