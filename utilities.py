# api_service.py
"""
This module handles all API interactions with the TraderMade market data service.
It provides functions to fetch currency lists, perform conversions, and get historical data.
"""

import requests
from datetime import date
from typing import Dict, List, Optional, Tuple
import pandas as pd

class APIService:
    """
    A service class for interacting with the TraderMade Forex API.
    
    Attributes:
        api_key (str): The API key for authentication
        list_url (str): Endpoint for fetching available currencies
        convert_url (str): Endpoint for currency conversion
        timeseries_url (str): Endpoint for historical data
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the API service with authentication key.
        
        Args:
            api_key: TraderMade API key for authentication
        """
        self.api_key = api_key
        self.list_url = "https://marketdata.tradermade.com/api/v1/live_currencies_list"
        self.convert_url = "https://marketdata.tradermade.com/api/v1/convert"
        self.timeseries_url = "https://marketdata.tradermade.com/api/v1/timeseries"
    
    def get_currency_list(self) -> List[str]:
        """
        Fetches the list of available currencies from the API.
        
        Returns:
            List of currency strings in format "CODE (Description)"
            
        Raises:
            Exception: If API request fails or response format is invalid
        """
        try:
            response = requests.get(f'{self.list_url}?api_key={self.api_key}')
            response.raise_for_status()
            currency_json = response.json()
            
            if "available_currencies" not in currency_json:
                raise ValueError("API response missing 'available_currencies' key")
                
            currencies = []
            for code, description in currency_json["available_currencies"].items():
                currencies.append(f'{code} ({description})')
            return currencies
            
        except Exception as e:
            raise Exception(f"Failed to fetch currency list: {str(e)}")
    
    def convert_currency(
        self, 
        from_currency: str, 
        to_currency: str, 
        amount: float
    ) -> Tuple[float, float]:
        """
        Converts an amount from one currency to another.
        
        Args:
            from_currency: 3-letter currency code to convert from
            to_currency: 3-letter currency code to convert to
            amount: Amount to convert
            
        Returns:
            Tuple of (converted_total, exchange_rate)
            
        Raises:
            Exception: If conversion fails or response format is invalid
        """
        try:
            url = (
                f"{self.convert_url}?api_key={self.api_key}"
                f"&from={from_currency}&to={to_currency}"
                f"&amount={amount}"
            )
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if "total" not in data or "quote" not in data:
                raise ValueError("API response missing conversion data")
                
            return round(data["total"], 4), data["quote"]
            
        except Exception as e:
            raise Exception(f"Currency conversion failed: {str(e)}")
    
    def get_historical_data(
        self, 
        currency_pair: str, 
        start_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """
        Fetches historical exchange rate data for a currency pair.
        
        Args:
            currency_pair: Currency pair in format "FROMTO" (e.g., "EURUSD")
            start_date: Start date for historical data
            end_date: End date for historical data
            
        Returns:
            DataFrame with historical rates containing:
                - date: Datetime index
                - open: Opening rate
                - high: Daily high
                - low: Daily low 
                - close: Closing rate
                
        Raises:
            Exception: If data fetch fails or processing error occurs
        """
        try:
            url = (
                f"{self.timeseries_url}?currency={currency_pair}"
                f"&api_key={self.api_key}"
                f"&start_date={start_date.strftime('%Y-%m-%d')}"
                f"&end_date={end_date.strftime('%Y-%m-%d')}"
                f"&format=records"
            )
            response = requests.get(url)
            response.raise_for_status()
            historical_data = response.json()
            
            df = pd.DataFrame(historical_data['quotes'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.dropna().set_index('date')
            return df
            
        except Exception as e:
            raise Exception(f"Failed to fetch historical data: {str(e)}")