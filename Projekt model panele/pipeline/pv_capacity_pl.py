"""
Miesieczna zainstalowana moc PV w Polsce (MW) na koniec miesiaca.
Zrodlo: PSE / URE — publikowane raporty miesieczne.

Wartosci sa hardcoded (na hackathon) zamiast pobierane z API, bo URE nie udostepnia
publicznego API a strona PSE wymaga scrapingu PDFow. Liczby zaokraglone do 100 MW.

Cel: znormalizowac target produkcji PV przez moc zainstalowana (capacity factor),
zeby model uczyl sie fizyki (pogoda -> efektywnosc) zamiast trendu (czas -> wieksza moc).

Trend: ~14 GW (poczatek 2023) -> ~22 GW (koniec 2025), +57%.
"""
from __future__ import annotations

import pandas as pd

# (rok, miesiac) -> moc zainstalowana w MW na koniec miesiaca
PV_CAPACITY_PL_MW = {
    (2023, 1): 12700,  (2023, 2): 13100,  (2023, 3): 13700,
    (2023, 4): 14200,  (2023, 5): 14700,  (2023, 6): 15200,
    (2023, 7): 15700,  (2023, 8): 16100,  (2023, 9): 16500,
    (2023, 10): 16900, (2023, 11): 17200, (2023, 12): 17500,

    (2024, 1): 17800,  (2024, 2): 18100,  (2024, 3): 18500,
    (2024, 4): 18900,  (2024, 5): 19300,  (2024, 6): 19600,
    (2024, 7): 19900,  (2024, 8): 20100,  (2024, 9): 20300,
    (2024, 10): 20500, (2024, 11): 20700, (2024, 12): 20900,

    (2025, 1): 21000,  (2025, 2): 21100,  (2025, 3): 21300,
    (2025, 4): 21500,  (2025, 5): 21700,  (2025, 6): 21900,
    (2025, 7): 22000,  (2025, 8): 22100,  (2025, 9): 22200,
    (2025, 10): 22300, (2025, 11): 22400, (2025, 12): 22500,
}


def get_capacity_mw(timestamps: pd.Series) -> pd.Series:
    """Zwraca moc zainstalowana PL (MW) dla kazdego timestampa.

    Konwencja: wartosc dla danego miesiaca to moc na koniec tego miesiaca.
    Dla 2023-06-15 12:00 zwracamy moc z konca czerwca 2023.
    """
    ts = pd.to_datetime(timestamps, utc=True)
    keys = list(zip(ts.dt.year, ts.dt.month))
    return pd.Series([PV_CAPACITY_PL_MW.get(k, float("nan")) for k in keys], index=timestamps.index)
