"""
data_processor.py

Utilities for processing OHLC time series used by the Currency Exchange Tracker.

Provides:
- calculate_historical_volatility: log returns and annualized volatility
- calculate_pivot_points: standard pivot points and support/resistance levels
- prepare_chart_data: normalize DataFrame for plotting libraries

All public functions accept and return pandas.DataFrame objects and include
type annotations and input validation to fail fast on unexpected input.
"""

from __future__ import annotations

from typing import Iterable, List

import numpy as np
import pandas as pd


def _ensure_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    """
    Validate that required columns exist in the DataFrame.

    Raises:
        ValueError: if any required column is missing.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")


def _to_numeric_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """
    Convert specified columns to numeric dtype in-place and return the DataFrame.

    Non-convertible values become NaN.
    """
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def calculate_historical_volatility(df: pd.DataFrame, window_size: int = 20) -> pd.DataFrame:
    """
    Calculate log returns and annualized historical volatility.

    Args:
        df: DataFrame indexed by datetime or with a 'date' column and containing a 'close' column.
        window_size: Rolling window size (in periods) used to compute the rolling standard deviation.

    Returns:
        DataFrame with added columns:
            - 'log_ret' : log returns
            - 'hv'      : annualized historical volatility in percentage

    Notes:
        - Uses 252 trading days for annualization (standard in finance).
        - Drops rows with NaN produced by shifting/rolling operations.
    """
    if "close" not in df.columns:
        raise ValueError("Input DataFrame must contain a 'close' column")

    df = df.copy()
    # Ensure numeric close values
    df = _to_numeric_columns(df, ["close"])

    # Compute log returns
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))

    # Rolling standard deviation of log returns
    rolling_std = df["log_ret"].rolling(window=window_size, min_periods=1).std()

    # Annualize using 252 trading days and convert to percentage
    df["hv"] = rolling_std * np.sqrt(252) * 100.0

    # Drop rows with NaN in hv or log_ret (first rows)
    return df.dropna(subset=["log_ret", "hv"])


def calculate_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate daily pivot points and support/resistance levels.

    Args:
        df: DataFrame indexed by datetime (or with 'date' column) containing 'high', 'low', 'close'.

    Returns:
        DataFrame with added columns:
            - 'pivot', 'r1', 's1', 'r2', 's2', 'r3', 's3'

    Behavior:
        - Uses previous period's high/low/close to compute pivot levels for the current row.
        - Rows with insufficient history (NaN after shift) are dropped.
    """
    required = {"high", "low", "close"}
    _ensure_columns(df, required)

    df = df.copy()
    # Ensure numeric types
    df = _to_numeric_columns(df, ["high", "low", "close"])

    # Use previous period values to compute pivot for the current period
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    prev_close = df["close"].shift(1)

    # Pivot point
    df["pivot"] = (prev_high + prev_low + prev_close) / 3.0

    # First level support/resistance
    df["r1"] = 2 * df["pivot"] - prev_low
    df["s1"] = 2 * df["pivot"] - prev_high

    # Second level
    df["r2"] = df["pivot"] + (prev_high - prev_low)
    df["s2"] = df["pivot"] - (prev_high - prev_low)

    # Third level
    df["r3"] = prev_high + 2 * (df["pivot"] - prev_low)
    df["s3"] = prev_low - 2 * (prev_high - df["pivot"])

    # Drop rows where pivot could not be computed (first row)
    return df.dropna(subset=["pivot"])


def prepare_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare DataFrame for charting libraries.

    Ensures:
    - 'date' is a column (not only an index)
    - OHLC columns are present and numeric
    - Data is sorted by date ascending

    Args:
        df: DataFrame indexed by datetime or with a 'date' column.

    Returns:
        DataFrame with 'date' column and numeric 'open','high','low','close' columns.
    """
    df = df.copy()

    # If index is datetime and 'date' column not present, reset index
    if "date" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df = df.rename(columns={df.columns[0]: "date"}) if df.columns[0] != "date" else df
        else:
            # If no date column and index is not datetime, attempt to coerce any index to datetime
            try:
                df = df.reset_index()
            except Exception:
                raise ValueError("DataFrame must have a datetime index or a 'date' column")

    # Normalize column names to lowercase for consistency
    df.columns = [c.lower() for c in df.columns]

    # Ensure OHLC columns exist
    required = {"open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        missing = required.difference(set(df.columns))
        raise ValueError(f"Chart data missing required OHLC columns: {missing}")

    # Convert date column to datetime and OHLC to numeric
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = _to_numeric_columns(df, ["open", "high", "low", "close"])

    # Drop rows with invalid dates or OHLC values
    df = df.dropna(subset=["date", "open", "high", "low", "close"])

    # Sort by date ascending
    df = df.sort_values("date").reset_index(drop=True)
    return df
