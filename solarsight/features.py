"""Calendar features shared by training and forecasting."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_time_features(df: pd.DataFrame, timestamps_utc: pd.Series,
                      decimals: int | None = None) -> pd.DataFrame:
    """Add date/hour/day-of-year/month and their cyclic encodings.

    Sine/cosine encodings tell the model that hour 23 is next to hour 0 and that
    31 December is next to 1 January. Pass ``decimals`` to round the encodings
    (the forecast inputs are rounded to 4 places, the training data is not).
    """
    df["date"] = timestamps_utc.dt.strftime("%Y-%m-%d")
    df["hour"] = timestamps_utc.dt.hour.astype(int)
    df["day_of_year"] = timestamps_utc.dt.dayofyear.astype(int)
    df["month"] = timestamps_utc.dt.month.astype(int)

    encodings = {
        "hour_sin": np.sin(2 * np.pi * df["hour"] / 24),
        "hour_cos": np.cos(2 * np.pi * df["hour"] / 24),
        "doy_sin": np.sin(2 * np.pi * df["day_of_year"] / 365),
        "doy_cos": np.cos(2 * np.pi * df["day_of_year"] / 365),
    }
    for name, values in encodings.items():
        df[name] = np.round(values, decimals) if decimals is not None else values
    return df
