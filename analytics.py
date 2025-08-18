"""
This module contains functions for processing financial data including:
- Calculating historical volatility
- Computing pivot points
- Preparing data for visualization
"""

import numpy as np
import pandas as pd
from typing import Tuple

class DataProcessor:
      
    @staticmethod
    def calculate_historical_volatility(
        df: pd.DataFrame, 
        window_size: int = 20
    ) -> pd.DataFrame:
        """
        Calculates historical volatility for a DataFrame with price data.
        
        Args:
            df: DataFrame containing price data with 'close' column
            window_size: Rolling window size for volatility calculation
            
        Returns:
            DataFrame with added columns:
                - log_ret: Logarithmic returns
                - hv: Annualized historical volatility percentage
        """
        df = df.copy()
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        rolling_std = df['log_ret'].rolling(window=window_size).std()
        df['hv'] = rolling_std * np.sqrt(365) * 100  # Annualized percentage
        return df.dropna()
    
    @staticmethod
    def calculate_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates standard pivot points and support/resistance levels.
        
        Args:
            df: DataFrame containing OHLC data with columns:
                - high: Daily high
                - low: Daily low 
                - close: Daily close
                
        Returns:
            DataFrame with added columns:
                - pivot: Pivot point
                - r1/r2/r3: Resistance levels 1-3
                - s1/s2/s3: Support levels 1-3
        """
        df = df.copy()
        df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
        df['r1'] = 2 * df['pivot'] - df['low'].shift(1)
        df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
        df['r2'] = df['pivot'] + (df['high'].shift(1) - df['low'].shift(1))
        df['s2'] = df['pivot'] - (df['high'].shift(1) - df['low'].shift(1))
        df['r3'] = df['high'].shift(1) + 2 * (df['pivot'] - df['low'].shift(1))
        df['s3'] = df['low'].shift(1) - 2 * (df['high'].shift(1) - df['pivot'])
        return df.dropna()
    
    @staticmethod
    def prepare_chart_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepares data for visualization by resetting index and ensuring proper format.
        
        Args:
            df: DataFrame with datetime index and OHLC data
            
        Returns:
            DataFrame ready for charting with date as a column
        """
        return df.reset_index()