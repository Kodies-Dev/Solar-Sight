# Predykcja produkcji fotowoltaiki — Gliwice (Tauron Hackathon)

Model predykcji godzinowej produkcji PV dla Gliwic na podstawie prognozy pogody (horyzont 24h).

---

## Struktura repozytorium

```
.
├── pipeline/                   # Zbieranie i przetwarzanie danych
│   ├── run_pipeline.py         # Punkt wejścia — uruchamia cały pipeline
│   ├── class_weather_api.py    # Pobieranie danych pogodowych (Open-Meteo)
│   ├── zbieraczka_danych_oze.py # Pobieranie produkcji PV (ENTSO-E / instrat)
│   ├── merge_dataset.py        # Łączenie obu źródeł w dataset treningowy
│   └── miasta.csv              # Rejestr miast (koordynaty, populacja)
│
├── forecast/                   # Generowanie danych wejściowych do predykcji
│   ├── google_forecast.py      # Prognoza pogodowa z Google Weather API (wymaga klucza)
│   ├── meteo_forecast.py       # Prognoza z Open-Meteo (bez klucza) + dane solarne
│   └── merge_forecasts.py      # Łączy oba źródła w format gotowy dla modelu
│
├── data/
│   └── solar_dataset_tauron.csv  # Dataset treningowy (generowany przez pipeline)
│
├── artifacts/
│   └── model.joblib            # Wytrenowany model XGBoost
│
├── notebooks/
│   └── data_analysis.ipynb     # Eksploracyjna analiza danych
│
├── main_model.ipynb            # Trening i ewaluacja modelu
└── requirements.txt
```

---

## Szybki start

### 1. Instalacja zależności

```bash
pip install -r requirements.txt
```

### 2. Generowanie datasetu treningowego

```bash
cd pipeline
python run_pipeline.py
```

Domyślnie pobiera dane dla **Gliwic** za okres **2023-01-01 – 2025-12-31**.

Parametry opcjonalne:

```bash
python run_pipeline.py --city Gliwice --start 2023-01-01 --end 2025-12-31
```

Nazwa miasta musi istnieć w `pipeline/miasta.csv`. Aby dodać nowe miasto — dopisz wiersz do pliku.

### 3. Trening modelu

Otwórz `main_model.ipynb` i uruchom wszystkie komórki.

---

## Opis pipeline danych

Pipeline składa się z trzech kroków wykonywanych przez `run_pipeline.py`:

### Krok 1 — Produkcja PV (`zbieraczka_danych_oze.py`)

Pobiera krajową godzinową produkcję fotowoltaiczną z API ENTSO-E (via [instrat.pl](https://energy-api.instrat.pl)).

Skalowanie krajowych danych do poziomu miasta:

```
produkcja_miasto = produkcja_PL × (populacja_miasta / populacja_PL)
```

Obsługuje zmianę raportowania ENTSO-E z 13.06.2024 (przejście z rozdzielczości 60-min na 15-min; dane korygowane współczynnikiem ×0.25 od tej daty).

**Wyjście:** `pipeline/fotowoltaika_godzinowo_{miasto}_{start}_{end}.csv`

### Krok 2 — Dane pogodowe (`class_weather_api.py`)

Pobiera historyczne dane godzinowe z [Open-Meteo Archive API](https://archive-api.open-meteo.com/v1/archive).

Pobierane cechy:

| Kolumna | Opis |
|---|---|
| `shortwave_radiation_wm2` | Promieniowanie krótkofalowe [W/m²] |
| `direct_radiation_wm2` | Promieniowanie bezpośrednie [W/m²] |
| `diffuse_radiation_wm2` | Promieniowanie rozproszone [W/m²] |
| `cloud_cover_pct` | Zachmurzenie [%] |
| `sunshine_pct` | Nasłonecznienie w godzinie [%] |
| `temperature_c` | Temperatura [°C] |
| `wind_speed_ms` | Prędkość wiatru [m/s] |
| `humidity_pct` | Wilgotność względna [%] |
| `pressure_hpa` | Ciśnienie atmosferyczne [hPa] |

Cechy inżynieryjne wyliczane lokalnie:

| Kolumna | Opis |
|---|---|
| `hour_sin`, `hour_cos` | Cykliczne kodowanie godziny |
| `doy_sin`, `doy_cos` | Cykliczne kodowanie dnia roku |
| `solar_elevation_deg` | Kąt Słońca nad horyzontem (wzór NOAA) |

**Wyjście:** `pipeline/weather_{miasto}_real.csv`

### Krok 3 — Merge (`merge_dataset.py`)

Łączy dane pogodowe i produkcji PV na pełnej godzinowej siatce UTC (zapobiega lukom DST). Brakujące godziny PV (wiosenna zmiana czasu) uzupełniane zerem — poprawne fizycznie (noc). Po połączeniu orkiestrator (`run_pipeline.py`) usuwa kolumny meta i zmienia nazwę targetu na `production_mwh`, po czym zapisuje wynik do `data/solar_dataset_tauron.csv`.

---

## Pipeline predykcji (forecast/)

Dane wejściowe do modelu generowane są w trzech krokach:

```
1. meteo_forecast.py    → meteo_forecast_YYYYMMDD_HHMM.csv    (dane solarne + pogodowe)
2. google_forecast.py   → google_forecast_YYYYMMDD_HHMM.csv   (pogodowe, lepsza jakość)
3. merge_forecasts.py   → forecast_final.csv                  (gotowy input dla modelu)
```

Google Weather jest źródłem **primary** dla danych pogodowych (temperatura, wiatr,
wilgotność, ciśnienie, zachmurzenie). Open-Meteo jest **jedynym** źródłem danych
solarnych (promieniowanie krótkofalowe, bezpośrednie, rozproszone, nasłonecznienie)
oraz fallbackiem gdy Google zwróci NaN.

Wyjście `merge_forecasts.py` zawiera **dokładnie te same kolumny** co dane treningowe
(bez `production_mwh`) — gotowe do bezpośredniego przekazania do modelu.

```bash
cd forecast

# Krok 1 — dane solarne + pogodowe z Open-Meteo (bez klucza)
python meteo_forecast.py --hours 24

# Krok 2 — dane pogodowe z Google (wymaga klucza)
python google_forecast.py --api-key TWÓJ_KLUCZ --hours 24

# Krok 3 — merge (automatycznie znajdzie najnowsze pliki)
python merge_forecasts.py --output forecast_final.csv
```

Parametr `--city` (domyślnie `Gliwice`) musi być wpisany w `pipeline/miasta.csv`.

---

## Model

**Algorytm:** XGBoost Regressor  
**Optymalizacja hiperparametrów:** Optuna (100 prób, walidacja TimeSeriesSplit)  
**Walidacja:** 5-fold TimeSeriesSplit, gap=24h, test_size=30 dni  

Wyniki na zbiorze testowym:

| Metryka | Wartość |
|---|---|
| MAE | 0.29 MWh |
| RMSE | 1.37 MWh |
| R² | 0.9873 |

Wytrenowany model zapisany w `artifacts/model.joblib`.

---

## Dodawanie nowego miasta

1. Dodaj wiersz do `pipeline/miasta.csv`:
   ```
   Katowice,50.2599,19.0216,285000
   ```
2. Uruchom pipeline z parametrem `--city Katowice`.

---

## Historia zmian względem pierwszej wersji

### Co zostało przepisane

| Stary komponent | Nowy odpowiednik | Zmiana |
|---|---|---|
| `API for MWh/zbieraczka_danych_oze.py` | `pipeline/zbieraczka_danych_oze.py` | Miasto nie jest wpisane na sztywno; koordynaty i populacja ładowane z `miasta.csv` |
| `api_for_weather/class_weather_api.py` | `pipeline/class_weather_api.py` | j.w.; zastąpiono `uv_index` (niedostępny w archiwum Open-Meteo) promieniowaniem krótkofalowym; dodano `solar_elevation_deg` |
| `merged_weather_mwh/merge_weather_mwh.py` | `pipeline/merge_dataset.py` + `run_pipeline.py` | Pełna siatka godzinowa UTC; obsługa luk DST; skalowanie populacyjne przeniesione do źródła |

### Co zostało usunięte

- `API for MWh/` — zastąpiony przez `pipeline/`
- `api_for_weather/` — zastąpiony przez `pipeline/`
- `merged_weather_mwh/` — zastąpiony przez `pipeline/`
- `data_solar_panel_analysis/` — notebook przeniesiony do `notebooks/`
- `main.py` — pusty placeholder, usunięty
- `data/opis_datasetu_solar.docx` — zastąpiony tym README

---

## Wymagania

```
pandas
numpy
sklearn
optuna
xgboost
seaborn
matplotlib
requests
urllib3
```

```bash
pip install -r requirements.txt
```
