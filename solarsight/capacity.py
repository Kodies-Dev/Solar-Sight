"""Installed PV capacity in Poland (MW, end of month).

Source: monthly URE / PSE reports. The values are hard-coded because URE has no
public API and the PSE site would require scraping PDFs. Rounded to 100 MW.

Why it matters: installed capacity grew ~77% between January 2023 and December
2025. Using it as a feature lets the model learn physics (weather -> efficiency)
instead of a time trend (later date -> more capacity -> more energy).
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# (year, month) -> installed capacity in MW at the end of that month
PV_CAPACITY_PL_MW: dict[tuple[int, int], int] = {
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


def latest_capacity_mw() -> float:
    """Capacity of the most recent month in the table."""
    return float(PV_CAPACITY_PL_MW[max(PV_CAPACITY_PL_MW)])


def get_capacity_mw(timestamps: pd.Series) -> pd.Series:
    """Installed capacity for each timestamp (NaN outside the table).

    Convention: a month's value is the capacity at the end of that month, so
    2023-06-15 12:00 maps to the end of June 2023.
    """
    ts = pd.to_datetime(timestamps, utc=True)
    keys = list(zip(ts.dt.year, ts.dt.month))
    return pd.Series([PV_CAPACITY_PL_MW.get(k, float("nan")) for k in keys], index=timestamps.index)


def get_capacity_mw_with_fallback(timestamps: pd.Series) -> pd.Series:
    """Like ``get_capacity_mw`` but fills months after the table with the latest value.

    Forecasts are for the future, while the table ends at the last reported month.
    Extend ``PV_CAPACITY_PL_MW`` with new URE/PSE months to keep forecasts accurate.
    """
    capacity = get_capacity_mw(timestamps)
    missing = int(capacity.isna().sum())
    if missing:
        last_year, last_month = max(PV_CAPACITY_PL_MW)
        logger.warning("%d hours fall outside PV_CAPACITY_PL_MW; using the latest value "
                       "%.0f MW (end of %d-%02d). Extend the table for current forecasts.",
                       missing, latest_capacity_mw(), last_year, last_month)
        capacity = capacity.fillna(latest_capacity_mw())
    return capacity
