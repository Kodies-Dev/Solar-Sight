# Predykcja produkcji fotowoltaiki — dataset

Hackathon AI Tauron. Predykcja godzinowej produkcji PV na najblizsze 24h w Gliwicach
na podstawie prognoz pogodowych.

## Pipeline

```
miasta.csv  ---->  class_weather_api.py  ---->  weather_<CITY>_real.csv
                                                        |
miasta.csv  ---->  zbieraczka_danych_oze.py  ---->  fotowoltaika_godzinowo_<CITY>_...csv
                                                        |
                  pv_capacity_pl.py (hardcoded URE) ----+
                                                        v
                                          merge_dataset.py
                                                        |
                                                        v
                                          dataset_<CITY>_<start>_<end>.csv
```

1. **`class_weather_api.py`** — pobiera historyczne dane pogodowe z Open-Meteo
   (`https://archive-api.open-meteo.com/v1/archive`) w UTC dla wspolrzednych miasta.
2. **`zbieraczka_danych_oze.py`** — pobiera krajowa godzinowa produkcje PV
   z ENTSO-E przez API instrat (`https://energy-api.instrat.pl`) i skaluje ja
   proporcjonalnie do liczby mieszkancow miasta.
3. **`pv_capacity_pl.py`** — hardcoded miesieczna moc PV PL z URE/PSE (2023-2025).
4. **`merge_dataset.py`** — laczy oba zrodla po `timestamp` (UTC), wypelnia dziury
   (DST spring-forward), liczy capacity factor i zapisuje finalny CSV.

## Plik `pv_capacity_pl.py` — co to jest i jak dziala

To **trzeci plik w pipeline**, ale w przeciwienstwie do dwoch pierwszych nie
pobiera niczego z internetu. Zawiera **tabele stalych liczb** (slownik Pythonowy)
z miesieczna moca zainstalowana PV w calej Polsce — wartosci przepisane recznie
z publicznych raportow URE/PSE.

```python
PV_CAPACITY_PL_MW = {
    (2023, 1): 12700,   # styczen 2023 -> cala PL miala 12.7 GW
    (2023, 2): 13100,
    ...
    (2025, 12): 22500,  # grudzien 2025 -> cala PL 22.5 GW
}
```

### Dlaczego ten plik istnieje

Zainstalowana moc PV w Polsce rosla **+57% w naszym okresie** (12.7 -> 22.5 GW).
Bez tej informacji model nie umialby rozroznic "duzo paneli * sredni dzien"
od "malo paneli * sloneczny dzien" — obie sytuacje daja podobne MWh w produkcji,
ale to zupelnie inne wzorce pogodowe. Model dostalby sprzeczne sygnaly i uczylby
sie czasu zamiast pogody.

### Czy ten plik jest "dla Gliwic"?

**NIE.** Hardcoded sa wartosci dla **calej Polski** (te same dla kazdego miasta).
Skalowanie do konkretnego miasta odbywa sie dynamicznie w `merge_dataset.py`
przez populacje z `miasta.csv`:

```python
population_share  = population_miasta / 37_800_000      # np. Gliwice: 0.004451
city_capacity_mw  = installed_pv_mw_pl * population_share
capacity_factor   = Produkcja_PV_Godz_MWh / city_capacity_mw
```

To jest **dokladnie ten sam mechanizm per-capita** ktorego uzywamy do skalowania
samej produkcji w `zbieraczka_danych_oze.py`. Spojnosc zalozenia.

### Co `capacity_factor` realnie znaczy

Bezwymiarowy wskaznik [0..~0.7] — "ile procent teoretycznej mocy bylo wykorzystane
w tej godzinie". Zalezy **tylko od pogody, pory dnia, pory roku** — NIE od trendu
wzrostu mocy zainstalowanej. To wlasnie czyni go stabilnym targetem do treningu.

Weryfikacja stabilnosci (max godzinowy CF w czerwcu):
- 2023-06: 0.580
- 2024-06: 0.584
- 2025-06: 0.577

Surowe MWh w tych samych miesiacach: 39.3 / 51.0 / 56.2 — rosna +43%.
CF: stabilny **±1%**.

### Jak go uzywac

**W treningu:** `target = capacity_factor`, nie `Produkcja_PV_Godz_MWh`.

**W inference (predykcja "tu i teraz"):**
```python
predicted_cf  = model.predict(features_z_prognozy_pogody)
city_capacity = aktualna_moc_PL_mw * (population_miasta / 37_800_000)
predicted_mwh = predicted_cf * city_capacity
```

### Jak rozszerzac

**Nowe miasto** (np. Katowice) — dopisz wiersz do `miasta.csv`:
```
Katowice,50.2649,19.0238,290000
```
`pv_capacity_pl.py` **bez zmian** — te same liczby krajowe pasuja do kazdego miasta.

**Nowy miesiac** (np. styczen 2026) — dopisz wpis do slownika `PV_CAPACITY_PL_MW`:
```python
(2026, 1): 23000,
```
Wartosc znajdziesz w najnowszym raporcie URE.

### Konwencja wartosci

Liczby reprezentuja **moc zainstalowana na koniec danego miesiaca** (snapshot URE).
Dla dowolnego timestampa w danym miesiacu zwracamy te sama wartosc — nie
interpolujemy w obrebie miesiaca, bo URE nie publikuje danych dziennych.

## Uruchomienie

```bash
python class_weather_api.py   # albo wywolac WeatherAPI().upload_weather_data(...)
python zbieraczka_danych_oze.py
python merge_dataset.py
```

## Wyjasnienie skalowania per-capita

Brak publicznie dostepnych danych o produkcji PV per miasto — dlatego krajowa
produkcja jest mnozona przez `population_miasta / 37_800_000`.
Gliwice (168 248 mieszkancow) -> wspolczynnik ~0.00445.

## Capacity factor — KLUCZOWE dla treningu

Zainstalowana moc PV w PL rosla **+57%** w naszym okresie (2023-01: ~12.7 GW
-> 2025-12: ~22.5 GW). To samo promieniowanie w 2025 daje wiecej MWh niz w 2023.
Model uczony na surowym `Produkcja_PV_Godz_MWh` nauczylby sie czasu zamiast pogody.

Rozwiazanie: normalizujemy target przez moc zainstalowana przypisana do miasta:

```
city_capacity_mw = installed_pv_mw_pl * (population_miasta / population_pl)
capacity_factor  = Produkcja_PV_Godz_MWh / city_capacity_mw
```

Capacity factor (CF) to bezwymiarowy wskaznik wykorzystania mocy [0..~0.7].
Zalezy tylko od pogody i pory dnia/roku — **nie od trendu wzrostu mocy**.

**Weryfikacja stabilnosci CF (max godzinowy w czerwcu):**
- 2023-06: 0.580
- 2024-06: 0.584
- 2025-06: 0.577

vs surowy MWh w czerwcu rosnacy 39 -> 51 -> 56. CF **stabilny**.

### Trening i inference

- **Trenuj na `capacity_factor`**, nie na `Produkcja_PV_Godz_MWh`.
- Przy inference: `predicted_mwh = predicted_cf * current_capacity_mw_dla_miasta`.
- `current_capacity_mw_dla_miasta` w czasie rzeczywistym: aktualna krajowa moc
  z URE razy population_share (lub tabela z `pv_capacity_pl.py` rozszerzona o nowe miesiace).

## Strefa czasowa

Wszystkie timestampy sa w **UTC**. Open-Meteo (parametr `timezone=UTC`) i
instrat/ENTSO-E pracuja natywnie w UTC. Brak DST.

Wyjatek: instrat gubi 3 godziny (po 1 rocznie) na przelomie czasu zimowego -> letniego
(ostatnia niedziela marca, 02:00 UTC). To nocne godziny, produkcja PV = 0,
uzupelniane automatycznie przez `merge_dataset.py`.

## Zmiana raportowania ENTSO-E PL (2024-06-13)

Od 2024-06-13 ENTSO-E Polska zmienilo rozdzielczosc raportowania z 60-min
(1 probka w MWh) na 15-min (4 probki w MW sumowane do godziny). `zbieraczka_danych_oze.py`
stosuje warunkowy mnoznik 1.0 / 0.25 w zaleznosci od daty, zeby obie ery byly
spojne w MWh. Bez tego dane sprzed 2024-06-13 byly ~4x zanizone.

## Kolumny w finalnym dataset (23 kolumny)

### Czas
| Kolumna | Opis |
|---|---|
| `timestamp` | UTC, ISO 8601 z offsetem `+00:00` |
| `date` | data (YYYY-MM-DD), UTC |
| `hour` | godzina 0-23 UTC |
| `day_of_year` | 1-366 |
| `month` | 1-12 |
| `hour_sin`, `hour_cos` | cykliczne kodowanie godziny (okres 24h) |
| `doy_sin`, `doy_cos` | cykliczne kodowanie dnia roku (okres 365) |

### Pogoda (Open-Meteo)
| Kolumna | Jednostka | Opis |
|---|---|---|
| `shortwave_radiation_wm2` | W/m^2 | promieniowanie krotkofalowe — najsilniejszy predyktor PV |
| `direct_radiation_wm2` | W/m^2 | promieniowanie bezposrednie |
| `diffuse_radiation_wm2` | W/m^2 | promieniowanie rozproszone |
| `cloud_cover_pct` | % | calkowite zachmurzenie |
| `sunshine_pct` | % | procent godziny ze slonecznym oswietleniem |
| `temperature_c` | °C | temperatura 2m nad ziemia |
| `wind_speed_ms` | m/s | wiatr 10m |
| `humidity_pct` | % | wilgotnosc wzgledna 2m |
| `pressure_hpa` | hPa | cisnienie przy powierzchni |

### Cecha astronomiczna
| Kolumna | Opis |
|---|---|
| `solar_elevation_deg` | kat Slonca nad horyzontem w stopniach (lat, lon, timestamp). Ujemny = noc. |

### Moc i produkcja
| Kolumna | Jednostka | Opis |
|---|---|---|
| `installed_pv_mw_pl` | MW | krajowa zainstalowana moc PV (URE/PSE, miesieczna) |
| `Produkcja_PV_Godz_MWh` | MWh | godzinowa produkcja PV w Gliwicach (per-capita scaling) |
| **`capacity_factor`** | [0..~0.7] | **glowny target** — wskaznik wykorzystania mocy, niezalezny od trendu wzrostu mocy |

## Uwagi dla trenowania

- **Target: `capacity_factor`** (nie `Produkcja_PV_Godz_MWh`). Inference: mnozyc CF
  przez aktualna moc zainstalowana w mieście.
- Kolumny stale: `city`, `installed_pv_mw_pl` ma slaba zmiennosc w czasie — opcjonalnie
  zostawic jako feature (nie zaszkodzi LightGBM).
- Cechy redundantne: `hour`/`day_of_year`/`month` vs cykliczne sinusy — wystarcza cykliczne.
- Walidacja: **chronologiczny split** (train 2023-2024, val 2025), nigdy losowy.
- CF moze byc lekko bimodalny (dzien/noc) — rozwazyc oddzielne metryki dla dnia.
- Wiersze nocne maja CF=0, sa poprawne, nie usuwac.

## Zakres danych

- Miasto: **Gliwice** (50.2945 N, 18.6714 E, pop. 168 248)
- Okres: 2023-01-01 00:00 UTC -> 2025-12-31 23:00 UTC (26 304 godziny)
- Rozdzielczosc: 1h
- Ilosc kolumn: 23
