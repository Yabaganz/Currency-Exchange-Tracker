"""
Main Streamlit application for currency conversion and analysis.

This application provides:
- Real-time currency conversion
- Historical exchange rate data
- Volatility analysis
- Pivot point calculations
- Interactive charts
"""

import streamlit as st
from datetime import date, timedelta
from typing import List, Optional 
import pandas as pd
from lightweight_charts.widgets import StreamlitChart # type: ignore
from utilities import APIService
from analytics import DataProcessor

# Configuration
API_KEY = "GVM9PgfkeLrGqXoK_uEV"  # Replace with your actual API key

def initialize_app() -> None:
    """
    Initializes the Streamlit application with page config and styles.
    """
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

def get_currency_codes(currency_str: str) -> str:
    """
    Extracts 3-letter currency code from formatted string.
    Returns:
        3-letter currency code
    """
    return currency_str[:3]

def display_conversion_result(base_currency: str, target_currency: str, amount: float, converted_total: float, rate: float) -> None:
    """
    Displays currency conversion results in the UI.
    
    Args:
        base_currency: Original currency code
        target_currency: Target currency code
        amount: Original amount
        converted_total: Converted amount
        rate: Exchange rate
    """
    currency_col, conversion_col, details_col, _, _ = st.columns([0.06, 0.16, 0.26, 0.6, 0.1])
    
    with currency_col:
        st.markdown(f'<p class="converted_currency">{target_currency}</p>', unsafe_allow_html=True)
    
    with conversion_col:
        st.markdown(f'<p class="converted_total">{converted_total}</p>', unsafe_allow_html=True)
    
    with details_col:
        st.markdown(
            f'<p class="details_text">( {base_currency} = {rate} {target_currency})</p>',
            unsafe_allow_html=True
        )

def configure_chart(df: pd.DataFrame, pair: str) -> StreamlitChart:
    """
    Configures and returns a Lightweight Charts instance with OHLC data.
    
    Args:
        df: DataFrame with OHLC data
        pair: Currency pair being displayed
        
    Returns:
        Configured StreamlitChart instance
    """
    chart = StreamlitChart(height=450, width=1500)
    chart.grid(vert_enabled=True, horz_enabled=True)
    chart.layout(
        background_color='#131722', 
        font_family='Trebuchet MS', 
        font_size=16
    )
    chart.candle_style(
        up_color='#12D900', 
        down_color='#e91e63', 
        border_up_color='#2962ffcb', 
        border_down_color='#e91e63cb', 
        wick_up_color='#12D900', 
        wick_down_color='#e91e63cb'
    )
    chart.watermark(f'{pair} 1D')
    chart.legend(visible=True, font_family='Trebuchet MS', ohlc=True, percent=True)
    return chart

def main() -> None:
    """
    Main application function that orchestrates the UI and data flow.
    """
    initialize_app()
    api_service = APIService(API_KEY)
    data_processor = DataProcessor()
    
    # Initialize session state for currency list
    if "currency_list" not in st.session_state:
        st.session_state.currency_list = None
    
    # Main container layout
    with st.container():
        # Currency selection columns
        from_col, amount_col, _, text_col, _, to_col = st.columns([0.5,0.5,0.05,0.08,0.05,0.5])
        
        with from_col:
            # Fetch currency list if not already loaded
            if st.session_state.currency_list is None:
                try:
                    st.session_state.currency_list = api_service.get_currency_list()
                except Exception as e:
                    st.error(str(e))
                    st.session_state.currency_list = ["USD (US Dollar)"]
            
            base_currency = st.selectbox(
                'From', 
                st.session_state.currency_list, 
                index=0, 
                key='base_currency'
            )
            base_code = get_currency_codes(base_currency)
            
        with amount_col:
            amount = st.number_input(
                f'Amount (in {base_code})', 
                min_value=1.0, 
                key='amount'
            )
            
        with to_col:
            quote_currency = st.multiselect(
                'To', 
                st.session_state.currency_list, 
                default=[st.session_state.currency_list[1] if st.session_state.currency_list else "EUR (Euro)"], 
                key='quote_currency'
            )
            quote_codes = [get_currency_codes(q) for q in quote_currency]
    
        # Conversion section
        st.markdown('')
        currency_col, conversion_col, details_col, _, button_col = st.columns([0.2, 0.2, 0.3, 0.2, 0.1])

        with button_col:
            convert = st.button('Convert')

        if convert and quote_currency:
            for target_code in quote_codes:
                try:
                    converted_total, rate = api_service.convert_currency(
                        base_code,
                        target_code,
                        amount
                    )
                    with currency_col:
                        st.markdown(f'<p class="converted_currency">{target_code}</p>', unsafe_allow_html=True)
                    with conversion_col:
                        st.markdown(f'<p class="converted_total">{converted_total}</p>', unsafe_allow_html=True)
                    with details_col:
                        st.markdown(
                            f'<p class="details_text">( {base_code} = {rate} {target_code})</p>',
                            unsafe_allow_html=True
                        )
                except Exception as e:
                    st.error(str(e))
    
        # Historical data section
        st.markdown('')
        history_col, chart_col = st.columns([0.3,0.7])
    
        with history_col:
            if quote_currency:
                target_pair = f"{base_code}{quote_codes[0]}"
                st.markdown(
                    f'<p><b>1 {base_code} to {quote_codes[0]} exchange rate for previous days</b></p>', 
                    unsafe_allow_html=True
                )
                st.markdown('')
                
                # Date range selection
                start_date = st.date_input(
                    "Start Date", 
                    date.today() - timedelta(days=90)
                )
                end_date = st.date_input(
                    "End Date", 
                    date.today() - timedelta(days=1)  # Avoid future dates
                )
    
                if start_date > end_date:
                    st.error("Start date must be before end date.")
                else:
                    try:
                        # Fetch and display historical data
                        historical_df = api_service.get_historical_data(
                            target_pair,
                            start_date,
                            end_date
                        )
                        st.dataframe(historical_df.tail(10), use_container_width=True)
                        
                        # Process data for analysis
                        historical_df = data_processor.calculate_historical_volatility(historical_df)
                        historical_df = data_processor.calculate_pivot_points(historical_df)
                        
                        # Display in chart column
                        with chart_col:
                            try:
                                chart = configure_chart(historical_df, target_pair)
                                chart.set(data_processor.prepare_chart_data(historical_df))
                                chart.load()
                            except Exception as e:
                                st.error(f"Chart error: {str(e)}")
                    except Exception as e:
                        st.error(f"")    
                        # Historical Volatility section
        with st.container():
            st.markdown('')
                            
                            # Centered title
            st.markdown(
                f'<div style="text-align: center;">'
                f'<p class="section_title"><b>{base_code}/{quote_codes[0]} Historical Volatility</b> (length = 20)</p>'
                f'</div>',
                unsafe_allow_html=True)
            st.markdown('')
                            
                            # Full width container with centered content
            with st.container():
                col_1, col_2 = st.columns([0.4, 0.6])
                                
                with col_1:
                    st.dataframe(historical_df[['close','log_ret','hv']], use_container_width=True)
                                
                with col_2:
                    st.line_chart(historical_df.hv, height=450, use_container_width=True)
                            
                            
                            # Pivot Points section 
        with st.container():
            st.markdown('')
                            

            st.markdown(
                f'<div style="text-align: center;">'
                f'<p class="section_title"><b>{base_code}/{quote_codes[0]} Pivot Points</b></p>'
                f'</div>',
                unsafe_allow_html=True
                )
            st.markdown('')
                            
                            # Full width container with centered content
            with st.container():
                col1, col2 = st.columns([0.4, 0.6])
                                
                with col1:
                    st.dataframe(historical_df.iloc[:,-6:], use_container_width=True)
                                
                with col2:
                    try:
                        chart = configure_chart(historical_df, target_pair)
                                        
                                        # Add pivot lines
                        last_row = historical_df.iloc[-1]
                        chart.horizontal_line(price=last_row['r1'], color='darkorange', text='R1', style='dotted')
                        chart.horizontal_line(price=last_row['r2'], color='darkorange', text='R2', style='dotted')
                        chart.horizontal_line(price=last_row['r3'], color='darkorange', text='R3', style='dotted')
                        chart.horizontal_line(price=last_row['s1'], color='darkorange', text='S1', style='dotted')
                        chart.horizontal_line(price=last_row['s2'], color='darkorange', text='S2', style='dotted')
                        chart.horizontal_line(price=last_row['s3'], color='darkorange', text='S3', style='dotted')
                        chart.set(data_processor.prepare_chart_data(historical_df))
                        chart.load()
                                    
                    except Exception as e:
                        st.error(f"Pivot chart error: {str(e)}")                    
if __name__ == "__main__":
    main()
