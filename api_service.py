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
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import requests
from requests import Response
from requests.exceptions import RequestException, HTTPError


class APIService:
    """
    TraderMade API service wrapper with robust error handling and type safety.
    
    Handles:
    - Currency list retrieval
    - Live currency conversion  
    - Historical OHLC timeseries data
    """
    
    # API Endpoints (Immutable)
    LIST_URL: str = "https://marketdata.tradermade.com/api/v1/live_currencies_list"
    CONVERT_URL: str = "https://marketdata.tradermade.com/api/v1/convert" 
    TIMESERIES_URL: str = "https://marketdata.tradermade.com/api/v1/timeseries"
    
    # HTTP Headers for Cloud compatibility
    DEFAULT_HEADERS: Dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Connection': 'close'
    }
    
    def __init__(self, api_key: str, timeout: int = 15) -> None:
        """
        Initialize API service with authentication and timeout configuration.
        
        Args:
            api_key: TraderMade API key (required for all endpoints)
            timeout: HTTP request timeout in seconds (default: 15s)
        """
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("API key must be a non-empty string")
            
        self.api_key: str = api_key.strip()
        self._timeout: int = max(5, timeout)  # Minimum 5s timeout
        self._session: Optional[requests.Session] = None
        
    @property
    def session(self) -> requests.Session:
        """Lazy session initialization for connection pooling."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.DEFAULT_HEADERS)
        return self._session
    
    def _make_request(self, url: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generic request handler with comprehensive error handling.
        
        Args:
            url: Full API endpoint URL
            params: URL query parameters
            
        Returns:
            Parsed JSON response as dict
            
        Raises:
            ValueError: Malformed response or API errors
            RuntimeError: Network/timeout failures
        """
        try:
            # Build request params
            if params is None:
                params = {}
            params['api_key'] = self.api_key
            
            response: Response = self.session.get(
                url, 
                params=params, 
                timeout=self._timeout
            )
            response.raise_for_status()
            
            payload: Dict[str, Any] = response.json()
            
            # Check for API-level errors
            if not isinstance(payload, dict):
                raise ValueError("Invalid JSON response from API")
                
            if 'error' in payload and payload['error']:
                raise ValueError(f"API Error: {payload.get('error_message', 'Unknown error')}")
            
            return payload
            
        except HTTPError as e:
            raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except RequestException as e:
            raise RuntimeError(f"Network error: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Request failed: {str(e)}") from e
    
    def get_currency_list(self) -> List[str]:
        """
        Fetch available currencies from TraderMade.
        
        Returns:
            List of formatted currency labels: ["USD (US Dollar)", "EUR (Euro)", ...]
            
        Raises:
            RuntimeError: Network/API errors
        """
        payload: Dict[str, Any] = self._make_request(self.LIST_URL)
        
        # Validate response structure
        if 'available_currencies' not in payload:
            raise ValueError("Missing 'available_currencies' in API response")
        
        currencies: Dict[str, str] = payload['available_currencies']
        if not isinstance(currencies, dict):
            raise ValueError("'available_currencies' must be a dictionary")
        
        # Format as UI-friendly labels
        result: List[str] = [
            f"{code.upper()} ({description})" 
            for code, description in currencies.items()
            if isinstance(code, str) and isinstance(description, str)
        ]
        
        return sorted(result)
    
    def convert_currency(
        self, 
        from_currency: str, 
        to_currency: str, 
        amount: float
    ) -> Tuple[float, float]:
        """
        Convert currency amount using live rates.
        
        Args:
            from_currency: Source 3-letter code (e.g., "USD")
            to_currency: Target 3-letter code (e.g., "EUR")  
            amount: Amount to convert (positive float)
            
        Returns:
            Tuple of (converted_amount: float, exchange_rate: float)
            
        Raises:
            ValueError: Invalid currency codes or amount
            RuntimeError: API/network errors
        """
        # Input validation
        if not (isinstance(from_currency, str) and len(from_currency) == 3):
            raise ValueError("from_currency must be 3-letter code")
        if not (isinstance(to_currency, str) and len(to_currency) == 3):
            raise ValueError("to_currency must be 3-letter code")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("amount must be positive number")
        
        params: Dict[str, str] = {
            'from': from_currency.upper(),
            'to': to_currency.upper(),
            'amount': f"{amount:.2f}"
        }
        
        payload: Dict[str, Any] = self._make_request(self.CONVERT_URL, params)
        
        # Extract conversion results
        if not {'total', 'quote'}.issubset(payload):
            raise ValueError("Missing conversion results in response")
        
        try:
            total: float = float(payload['total'])
            quote: float = float(payload['quote'])
            return round(total, 6), round(quote, 6)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid conversion data: {payload}") from e
    
    def get_historical_data(
        self, 
        currency_pair: str, 
        start_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """
        Fetch historical OHLC data for currency pair.
        
        Args:
            currency_pair: Trading pair (e.g., "EURUSD", "GBPUSD")
            start_date: Inclusive start date
            end_date: Inclusive end date
            
        Returns:
            DataFrame with datetime index and lowercase OHLC columns:
                date (index), open, high, low, close
            
        Raises:
            ValueError: Invalid inputs or missing OHLC data
            RuntimeError: API/network errors
        """
        # Input validation
        if not isinstance(currency_pair, str) or len(currency_pair) < 4:
            raise ValueError("currency_pair must be valid pair (e.g., EURUSD)")
        if start_date > end_date:
            raise ValueError("start_date must be before end_date")
        
        params: Dict[str, str] = {
            'currency': currency_pair.upper(),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'interval': 'daily',  # Explicit daily candles
            'format': 'records'   # Array of records format
        }
        
        payload: Dict[str, Any] = self._make_request(self.TIMESERIES_URL, params)
        
        # Validate quotes structure
        if 'quotes' not in payload:
            raise ValueError("Missing 'quotes' array in historical response")
        
        quotes: list = payload['quotes']
        if not isinstance(quotes, list) or not quotes:
            raise ValueError("Empty or invalid quotes data")
        
        # Convert to DataFrame
        df: pd.DataFrame = pd.DataFrame(quotes)
        
        # Validate and process date column
        if 'date' not in df.columns:
            raise ValueError("Historical data missing 'date' column")
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        if df.empty:
            raise ValueError("No valid historical data after date processing")
        
        # Normalize column names to lowercase (API may return mixed case)
        df.columns = [col.lower() for col in df.columns]
        
        # Map common OHLC variants to standard names
        ohlc_mapping: Dict[str, str] = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower.startswith(('open', 'o')):
                ohlc_mapping[col] = 'open'
            elif col_lower.startswith(('high', 'h')):
                ohlc_mapping[col] = 'high'
            elif col_lower.startswith(('low', 'l')):
                ohlc_mapping[col] = 'low'
            elif col_lower.startswith(('close', 'c', 'last')):
                ohlc_mapping[col] = 'close'
        
        df = df.rename(columns=ohlc_mapping)
        
        # Validate required OHLC columns exist
        required_ohlc: set = {'open', 'high', 'low', 'close'}
        if not required_ohlc.issubset(df.columns):
            missing = required_ohlc - set(df.columns)
            raise ValueError(f"Missing OHLC columns: {missing}")
        
        # Convert OHLC to numeric and clean data
        numeric_cols: List[str] = ['open', 'high', 'low', 'close']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=numeric_cols + ['date'])
        
        # Final formatting: datetime index, sorted
        df = df.set_index('date').sort_index()
        
        return df
    
    def close(self) -> None:
        """Close HTTP session (call on app shutdown)."""
        if self._session:
            self._session.close()
            self._session = None
