import pandas as pd
import streamlit as st
import requests
import numpy as np
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Tuple
from lightweight_charts.widgets import StreamlitChart # type: ignore

# API Configuration
API_KEY: str = "GVM9PgfkeLrGqXoK_uEV"  # Replace with your actual API key
LIST_URL: str = "https://marketdata.tradermade.com/api/v1/live_currencies_list"
CONVERT_URL: str = "https://marketdata.tradermade.com/api/v1/convert"
TIMESERIES_URL: str = "https://marketdata.tradermade.com/api/v1/timeseries"

# Initialize session state for currency list
if "currency_list" not in st.session_state:
    st.session_state.currency_list = None

# Page configuration
st.set_page_config(
    page_title='Currency Converter',
    layout='wide'
)

# Custom CSS styling
st.markdown(
    """
    <style>
        footer {display: none}
        [data-testid="stHeader"] {display: none}
    </style>
    """, 
    unsafe_allow_html=True
)

with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Main container layout
with st.container():
    # Currency selection columns
    from_col, amount_col, emp_col, text_col, emp_col, to_col = st.columns([0.5,0.5,0.05,0.08,0.05,0.5])
    
    with from_col:
        # Fetch currency list if not already loaded
        if st.session_state.currency_list is None:
            try:
                currency_json: Dict = requests.get(f'{LIST_URL}?api_key={API_KEY}').json()
                if "available_currencies" in currency_json:
                    currencies: List[str] = []
                    for key in currency_json["available_currencies"].keys():
                        currency = f'{key} ({currency_json["available_currencies"].get(key)})'
                        currencies.append(currency)
                    st.session_state.currency_list = currencies
                else:
                    st.error(f"API response missing 'available_currencies': {currency_json}")
            except Exception as e:
                st.error(f"Error fetching currency list: {str(e)}")
        
        base_currency: str = st.selectbox(
            'From', 
            st.session_state.currency_list or ["USD (US Dollar)"], 
            index=0, 
            key='base_currency'
        )
        
    with amount_col:
        amount: float = st.number_input(
            f'Amount (in {base_currency[:3]})', 
            min_value=1.0, 
            key='amount'
        )
        
    with to_col:
        quote_currency: List[str] = st.multiselect(
            'To', 
            st.session_state.currency_list or ["EUR (Euro)"], 
            default=[st.session_state.currency_list[1] if st.session_state.currency_list else "EUR (Euro)"], 
            key='quote_currency'
        )

    # Conversion section
    st.markdown('')
    currency_col, conversion_col, details_col, emp_col, button_col = st.columns([0.06, 0.16, 0.26, 0.6, 0.1])
    
    with button_col:
        convert: bool = st.button('Convert')
        
        if convert and quote_currency:
            try:
                for target in quote_currency:
                    url = f"{CONVERT_URL}?api_key={API_KEY}&from={base_currency[:3]}&to={target[:3]}&amount={amount}"
                    response = requests.get(url)
                    response.raise_for_status()
                    data = response.json()

                    if "total" not in data or "quote" not in data:
                        st.error(f"No conversion data found for {base_currency[:3]} to {target[:3]}")
                        continue

                    converted_total = round(data["total"], 4)
                    rate = data["quote"]

                    with currency_col:
                        st.markdown(f'<p class="converted_currency">{target[:3]}</p>', unsafe_allow_html=True)

                    with conversion_col:
                        st.markdown(f'<p class="converted_total">{converted_total}</p>', unsafe_allow_html=True)

                    with details_col:
                        st.markdown(f'<p class="details_text">( {base_currency[:3]} = {rate} {target[:3]})</p>', unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Conversion error: {str(e)}")


    # Historical data section
    st.markdown('')
    hist_col, chart_col = st.columns([0.3,0.7])

    with hist_col:
        st.markdown(
            f'<p><b>1 {base_currency[:3]} to {quote_currency[:3]} exchange rate for previous days</b></p>', 
            unsafe_allow_html=True
        )
        st.markdown('')
        
        # Date range selection
        start_date: date = st.date_input(
            "Start Date", 
            date.today() - timedelta(days=90)
        )
        end_date: date = st.date_input(
            "End Date", 
            date.today() - timedelta(days=1)  # Avoid future dates
        )

        if start_date > end_date:
            st.error("Start date must be before end date.")
        else:
            try:
                # Fetch historical data
                paired_currency: str = f"{base_currency[:3]}{quote_currency[0][:3]}"
                url: str = (
                    f"{TIMESERIES_URL}?currency={paired_currency}"
                    f"&api_key={API_KEY}"
                    f"&start_date={start_date.strftime('%Y-%m-%d')}"
                    f"&end_date={end_date.strftime('%Y-%m-%d')}"
                    f"&format=records"
                )
                response = requests.get(url)
                response.raise_for_status()
                historical_data: Dict = response.json()
                
                # Process historical data
                historical_df: pd.DataFrame = pd.DataFrame(historical_data['quotes'])
                historical_df = historical_df.dropna().reset_index().drop('index', axis=1)
                historical_df['date'] = pd.to_datetime(historical_df['date'])
                historical_df = historical_df.set_index('date')
                
                # Display last 10 days
                st.dataframe(historical_df.tail(10), use_container_width=True)
                
            except Exception as e:
                st.error(f"can't fetching historical data: {str(e)}")

    with chart_col:
        if 'historical_df' in locals():
            try:
                # Configure chart
                chart = StreamlitChart(height=450, width=950)
                chart.grid(vert_enabled=True, horz_enabled=True)
                chart.layout(
                    background_color='#131722', 
                    font_family='Trebuchet MS', 
                    font_size=16
                )
                chart.candle_style(
                    up_color='#2962ff', 
                    down_color='#e91e63', 
                    border_up_color='#2962ffcb', 
                    border_down_color='#e91e63cb', 
                    wick_up_color='#2962ffcb', 
                    wick_down_color='#e91e63cb'
                )
                chart.watermark(f'{base_currency[:3]}/{quote_currency[0][:3]} 1D')
                chart.legend(visible=True, font_family='Trebuchet MS', ohlc=True, percent=True)
                
                # Set chart data
                chart_df = historical_df.reset_index()
                chart.set(chart_df)
                chart.load()

            except Exception as e:
                st.error(f"Chart error: {str(e)}")

    # Volatility and Pivot Points section
    with st.container():
        st.markdown('')
        
        if 'historical_df' in locals():
            # Historical Volatility
            st.markdown(
                f'<p class="section_title"><b>{base_currency[:3]}/{quote_currency[0][:3]} Historical Volatility</b> (length = 20)</p>', 
                unsafe_allow_html=True
            )
            st.markdown('')
            
            hv_data_col, hv_chart_col = st.columns([0.4,0.6])
            
            with hv_data_col:
                historical_df['log_ret'] = np.log(historical_df['close'] / historical_df['close'].shift(1))
                window_size = 20
                rolling_volatility = historical_df['log_ret'].rolling(window=window_size).std()
                historical_df['hv'] = rolling_volatility * np.sqrt(365) * 100
                historical_df = historical_df.dropna()
                st.dataframe(historical_df[['close','log_ret','hv']], use_container_width=True)
            
            with hv_chart_col:
                st.line_chart(historical_df.hv, height=450)
            
            # Pivot Points
            st.markdown('')
            st.markdown(
                f'<p class="section_title"><b>{base_currency[:3]}/{quote_currency[0][:3]} Pivot Points</b></p>', 
                unsafe_allow_html=True
            )
            st.markdown('')
            
            pivot_data_col, pivot_chart_col = st.columns([0.4,0.6])
            
            with pivot_data_col:
                historical_df['pivot'] = (historical_df['high'].shift(1) + historical_df['low'].shift(1) + historical_df['close'].shift(1)) / 3
                historical_df['r1'] = 2 * historical_df['pivot'] - historical_df['low'].shift(1)
                historical_df['s1'] = 2 * historical_df['pivot'] - historical_df['high'].shift(1)
                historical_df['r2'] = historical_df['pivot'] + (historical_df['high'].shift(1) - historical_df['low'].shift(1))
                historical_df['s2'] = historical_df['pivot'] - (historical_df['high'].shift(1) - historical_df['low'].shift(1))
                historical_df['r3'] = historical_df['high'].shift(1) + 2 * (historical_df['pivot'] - historical_df['low'].shift(1))
                historical_df['s3'] = historical_df['low'].shift(1) - 2 * (historical_df['high'].shift(1) - historical_df['pivot'])
                historical_df = historical_df.dropna()
                st.dataframe(historical_df.iloc[:,-6:], use_container_width=True)

            with pivot_chart_col:     
                try:
                    chart = StreamlitChart(height=450, width=800)
                    chart.grid(vert_enabled=True, horz_enabled=True)
                    chart.layout(background_color='#131722', font_family='Trebuchet MS', font_size=16)
                    chart.candle_style(
                        up_color='#2962ff', 
                        down_color='#e91e63',
                        border_up_color='#2962ffcb', 
                        border_down_color='#e91e63cb',
                        wick_up_color='#2962ffcb', 
                        wick_down_color='#e91e63cb'
                    )
                    
                    # Add pivot lines
                    chart.horizontal_line(price=historical_df['r1'].iloc[-1], color='darkorange', text='R1', style='dotted')
                    chart.horizontal_line(price=historical_df['r2'].iloc[-1], color='darkorange', text='R2', style='dotted')
                    chart.horizontal_line(price=historical_df['r3'].iloc[-1], color='darkorange', text='R3', style='dotted')
                    chart.horizontal_line(price=historical_df['s1'].iloc[-1], color='darkorange', text='S1', style='dotted')
                    chart.horizontal_line(price=historical_df['s2'].iloc[-1], color='darkorange', text='S2', style='dotted')
                    chart.horizontal_line(price=historical_df['s3'].iloc[-1], color='darkorange', text='S3', style='dotted')

                    chart.legend(visible=True, font_family='Trebuchet MS', ohlc=True, percent=True)
                    chart_df = historical_df.reset_index()
                    chart.set(chart_df)
                    chart.load()
                
                except Exception as e:
                    st.error(f"Pivot chart error: {str(e)}")