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
from typing import Iterable, List, Optional, Union
import numpy as np
import pandas as pd
from pandas import DataFrame


def _ensure_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    """
    Validate required columns exist in DataFrame.
    
    Args:
        df: Input DataFrame
        required: Set of required column names
        
    Raises:
        ValueError: If any required column missing
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be pandas.DataFrame")
    
    missing: List[str] = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")


def _to_numeric_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """
    Convert specified columns to numeric dtype in-place.
    
    Args:
        df: Input DataFrame
        cols: List of column names to convert
        
    Returns:
        DataFrame with numeric columns (NaN for non-convertible values)
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be pandas.DataFrame")
    
    result: pd.DataFrame = df.copy()
    for col in cols:
        if col not in result.columns:
            raise ValueError(f"Column '{col}' not found in DataFrame")
        result[col] = pd.to_numeric(result[col], errors="coerce")
    
    return result


def calculate_historical_volatility(
    df: pd.DataFrame, 
    window_size: int = 20, 
    price_col: str = "close"
) -> pd.DataFrame:
    """
    Calculate log returns and annualized historical volatility.
    
    Args:
        df: OHLC DataFrame with price column
        window_size: Rolling window for volatility calculation (default: 20 periods)
        price_col: Price column name (default: 'close')
        
    Returns:
        DataFrame with added columns:
            - f'{price_col}_log_ret': Log returns
            - 'hv': Annualized historical volatility (%)
    
    Notes:
        - Uses 252 trading days for annualization (FX standard)
        - Drops NaN rows from rolling calculations
        - Handles weekends/missing data gracefully
    """
    # Input validation
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be pandas.DataFrame")
    if price_col not in df.columns:
        raise ValueError(f"Price column '{price_col}' not found")
    if not isinstance(window_size, int) or window_size < 2:
        raise ValueError("window_size must be integer >= 2")
    
    df_work: pd.DataFrame = df.copy()
    
    # Ensure numeric price data
    df_work = _to_numeric_columns(df_work, [price_col])
    
    # Calculate log returns: ln(Pt / Pt-1)
    log_ret_col: str = f"{price_col}_log_ret"
    df_work[log_ret_col] = np.log(
        df_work[price_col] / df_work[price_col].shift(1)
    )
    
    # Rolling standard deviation of log returns
    rolling_std: pd.Series = df_work[log_ret_col].rolling(
        window=window_size, 
        min_periods=2  # Need at least 2 periods for std
    ).std()
    
    # Annualize: std * sqrt(252) * 100 for percentage
    ANNUALIZATION_FACTOR: float = np.sqrt(252)
    df_work["hv"] = rolling_std * ANNUALIZATION_FACTOR * 100.0
    
    # Clean: drop rows with NaN returns or volatility
    result: pd.DataFrame = df_work.dropna(subset=[log_ret_col, "hv"])
    
    return result


def calculate_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate classic floor pivot points and support/resistance levels.
    
    Formula (using previous period HLC):
        PP  = (High + Low + Close) / 3
        R1  = 2 × PP - Low
        S1  = 2 × PP - High  
        R2  = PP + (High - Low)
        S2  = PP - (High - Low)
        R3  = High + 2 × (PP - Low)
        S3  = Low - 2 × (High - PP)
    
    Args:
        df: OHLC DataFrame with 'high', 'low', 'close' columns
        
    Returns:
        DataFrame with pivot columns: 'pivot', 'r1', 'r2', 'r3', 's1', 's2', 's3'
    """
    # Validate required OHLC columns
    required: set[str] = {"high", "low", "close"}
    _ensure_columns(df, required)
    
    df_work: pd.DataFrame = df.copy()
    
    # Ensure numeric HLC data
    df_work = _to_numeric_columns(df_work, list(required))
    
    # Get previous period values (shift by 1)
    prev_high: pd.Series = df_work["high"].shift(1)
    prev_low: pd.Series = df_work["low"].shift(1) 
    prev_close: pd.Series = df_work["close"].shift(1)
    
    # Pivot Point (PP)
    df_work["pivot"] = (prev_high + prev_low + prev_close) / 3.0
    
    # Resistance levels (R1, R2, R3)
    df_work["r1"] = 2 * df_work["pivot"] - prev_low
    df_work["r2"] = df_work["pivot"] + (prev_high - prev_low)
    df_work["r3"] = prev_high + 2 * (df_work["pivot"] - prev_low)
    
    # Support levels (S1, S2, S3)
    df_work["s1"] = 2 * df_work["pivot"] - prev_high
    df_work["s2"] = df_work["pivot"] - (prev_high - prev_low)
    df_work["s3"] = prev_low - 2 * (prev_high - df_work["pivot"])
    
    # Drop first row (no previous period data)
    result: pd.DataFrame = df_work.dropna(subset=["pivot"])
    
    return result


def prepare_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize OHLC DataFrame for consistent charting across libraries.
    
    Ensures:
    - 'date' column exists (not just index)
    - Standard lowercase OHLC: 'open', 'high', 'low', 'close' 
    - Data sorted ascending by date
    - Numeric types with NaN cleaning
    
    Args:
        df: Raw OHLC data from API (flexible format)
        
    Returns:
        Clean chart-ready DataFrame
        
    Raises:
        ValueError: Missing date or OHLC columns
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be pandas.DataFrame")
    
    df_work: pd.DataFrame = df.copy()
    
    # STEP 1: Handle date column/index
    if "date" not in df_work.columns:
        if isinstance(df_work.index, pd.DatetimeIndex):
            # Move datetime index to column
            df_work = df_work.reset_index().rename(columns={df_work.index.name: "date"})
        else:
            raise ValueError("DataFrame must have 'date' column or DatetimeIndex")
    
    # STEP 2: Normalize column names to lowercase
    df_work.columns = [col.lower().strip() for col in df_work.columns]
    
    # STEP 3: Ensure date column still exists after lowercase
    if "date" not in df_work.columns:
        raise ValueError("No identifiable date column found")
    
    # STEP 4: Map OHLC variants to standard names
    ohlc_map: Dict[str, str] = {}
    for col in df_work.columns:
        col_lower: str = col.lower()
        if col_lower.startswith(('open', 'o')) and 'open' not in ohlc_map.values():
            ohlc_map[col] = 'open'
        elif col_lower.startswith(('high', 'h')) and 'high' not in ohlc_map.values():
            ohlc_map[col] = 'high'
        elif col_lower.startswith(('low', 'l')) and 'low' not in ohlc_map.values():
            ohlc_map[col] = 'low'
        elif col_lower.startswith(('close', 'c', 'last')) and 'close' not in ohlc_map.values():
            ohlc_map[col] = 'close'
    
    df_work = df_work.rename(columns=ohlc_map)
    
    # STEP 5: Validate required columns
    required_ohlc: set[str] = {'open', 'high', 'low', 'close'}
    _ensure_columns(df_work, ['date'] + list(required_ohlc))
    
    # STEP 6: Type conversions
    df_work["date"] = pd.to_datetime(df_work["date"], errors="coerce")
    df_work = _to_numeric_columns(df_work, list(required_ohlc))
    
    # STEP 7: Clean invalid data
    valid_mask: pd.Series = (
        df_work["date"].notna() & 
        df_work[required_ohlc].notna().all(axis=1) &
        (df_work["high"] >= df_work["low"]) &
        (df_work["high"] >= df_work["open"]) &
        (df_work["high"] >= df_work["close"]) &
        (df_work["low"] <= df_work["open"]) &
        (df_work["low"] <= df_work["close"])
    )
    
    cleaned: pd.DataFrame = df_work[valid_mask].copy()
    
    # STEP 8: Sort and finalize
    result: pd.DataFrame = cleaned.sort_values("date").reset_index(drop=True)
    
    if result.empty:
        raise ValueError("No valid OHLC data after cleaning")
    
    return result


class DataProcessor:
    """
    Container class for data processing utilities.
    
    Usage:
        processor = DataProcessor()
        pivots = processor.calculate_pivot_points(df)
        volatility = processor.calculate_historical_volatility(df)
        chart_data = processor.prepare_chart_data(df)
    """
    
    def calculate_historical_volatility(
        self, 
        df: pd.DataFrame, 
        window_size: int = 20, 
        price_col: str = "close"
    ) -> pd.DataFrame:
        """Instance method wrapper for calculate_historical_volatility."""
        return calculate_historical_volatility(df, window_size, price_col)
    
    def calculate_pivot_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Instance method wrapper for calculate_pivot_points."""
        return calculate_pivot_points(df)
    
    def prepare_chart_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Instance method wrapper for prepare_chart_data."""
        return prepare_chart_data(df)
