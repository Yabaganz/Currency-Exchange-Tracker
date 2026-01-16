"""
api_service.py

API service wrapper for TraderMade market data endpoints.

Provides:
- get_currency_list
- convert_currency
- get_historical_data

Notes:
- Uses a request timeout to avoid hanging network calls.
- Does not cache responses; caching is handled at the Streamlit layer.
"""

from __future__ import annotations

from datetime import date
from typing import List, Tuple

import pandas as pd
import requests


class APIService:
    """
    Service class to interact with the TraderMade API.

    Attributes:
        api_key: API key string used for authentication.
        _timeout: Default request timeout in seconds.
    """

    def __init__(self, api_key: str, timeout: int = 10) -> None:
        """
        Initialize the API service.

        Args:
            api_key: TraderMade API key.
            timeout: Default timeout for HTTP requests in seconds.
        """
        self.api_key: str = api_key
        self.list_url: str = "https://marketdata.tradermade.com/api/v1/live_currencies_list"
        self.convert_url: str = "https://marketdata.tradermade.com/api/v1/convert"
        self.timeseries_url: str = "https://marketdata.tradermade.com/api/v1/timeseries"
        self._timeout: int = timeout

    def get_currency_list(self) -> List[str]:
        """
        Fetch available currencies.

        Returns:
            List of strings formatted as "CODE (Description)".

        Raises:
            Exception: On network or response format errors.
        """
        try:
            response = requests.get(f"{self.list_url}?api_key={self.api_key}", timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict) or "available_currencies" not in payload:
                raise ValueError("API response missing 'available_currencies' key")

            available = payload["available_currencies"]
            if not isinstance(available, dict):
                raise ValueError("'available_currencies' has unexpected format")

            currencies: List[str] = [f"{code} ({description})" for code, description in available.items()]
            return currencies

        except Exception as exc:
            # Re-raise with contextual message for upstream handling
            raise Exception(f"Failed to fetch currency list: {exc}") from exc

    def convert_currency(self, from_currency: str, to_currency: str, amount: float) -> Tuple[float, float]:
        """
        Convert an amount from one currency to another.

        Args:
            from_currency: 3-letter currency code to convert from.
            to_currency: 3-letter currency code to convert to.
            amount: Amount to convert.

        Returns:
            Tuple of (converted_total, exchange_rate).

        Raises:
            Exception: On network or response format errors.
        """
        try:
            url = (
                f"{self.convert_url}?api_key={self.api_key}"
                f"&from={from_currency}&to={to_currency}"
                f"&amount={amount}"
            )
            response = requests.get(url, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict) or "total" not in data or "quote" not in data:
                raise ValueError("API response missing conversion data")

            total = float(data["total"])
            quote = float(data["quote"])
            return round(total, 4), quote

        except Exception as exc:
            raise Exception(f"Currency conversion failed: {exc}") from exc

    def get_historical_data(self, currency_pair: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Retrieve historical OHLC data for a currency pair.

        Args:
            currency_pair: e.g., "EURUSD"
            start_date: start date (inclusive)
            end_date: end date (inclusive)

        Returns:
            pandas DataFrame indexed by datetime with OHLC columns.

        Raises:
            Exception: On network or response format errors.
        """
        try:
            url = (
                f"{self.timeseries_url}?currency={currency_pair}"
                f"&api_key={self.api_key}"
                f"&start_date={start_date.strftime('%Y-%m-%d')}"
                f"&end_date={end_date.strftime('%Y-%m-%d')}"
                f"&format=records"
            )
            response = requests.get(url, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict) or "quotes" not in payload:
                raise ValueError("Historical response missing 'quotes' key")

            quotes = payload["quotes"]
            if not isinstance(quotes, list):
                raise ValueError("'quotes' has unexpected format")

            df = pd.DataFrame(quotes)

            # Ensure date column exists and convert to datetime
            if "date" not in df.columns:
                raise ValueError("Historical data missing 'date' column")

            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])

            # Normalize column names to lowercase expected by processors
            df.columns = [col.lower() for col in df.columns]

            # Ensure OHLC columns exist; if not, try to infer common alternatives
            required = {"open", "high", "low", "close"}
            if not required.issubset(set(df.columns)):
                # Attempt to map common variants (case-insensitive)
                col_map = {}
                for col in df.columns:
                    lc = col.lower()
                    if lc.startswith("open"):
                        col_map[col] = "open"
                    elif lc.startswith("high"):
                        col_map[col] = "high"
                    elif lc.startswith("low"):
                        col_map[col] = "low"
                    elif lc.startswith("close") or lc.startswith("last"):
                        col_map[col] = "close"
                if col_map:
                    df = df.rename(columns=col_map)

            if not required.issubset(set(df.columns)):
                # If still missing, raise a clear error
                missing = required.difference(set(df.columns))
                raise ValueError(f"Historical data missing required OHLC columns: {missing}")

            # Set datetime index
            df = df.set_index("date").sort_index()
            # Convert OHLC to numeric types
            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna(subset=["open", "high", "low", "close"])
            return df

        except Exception as exc:
            raise Exception(f"Failed to fetch historical data: {exc}") from exc
