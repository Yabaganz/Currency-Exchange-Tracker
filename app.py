from __future__ import annotations
from datetime import date
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st  # type: ignore
from api_service import APIService
from data_processor import DataProcessor

# CONFIGURATION: Load API key from Streamlit secrets (secure)
API_KEY: str = st.secrets.get("TRADERMADE_API_KEY", "")  # type: ignore

# LIBRARY DETECTION: Soft dependencies for optional chart libraries
LIGHTWEIGHT_CHARTS_AVAILABLE: bool = False
try:
    import streamlit_lightweight_charts  # type: ignore
    LIGHTWEIGHT_CHARTS_AVAILABLE = True
except ImportError:
    pass  # Graceful fallback

HV_AVAILABLE: bool = False
try:
    import hvplot.pandas  # type: ignore
    import holoviews as hv  # type: ignore
    HV_AVAILABLE = True
except ImportError:
    pass

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def get_currency_codes(currency_label: str) -> str:
    """Extract 3-letter currency code from label like 'USD (US Dollar)'."""
    if not isinstance(currency_label, str) or not currency_label:
        return ""
    return currency_label.split()[0].strip()


# CACHING LAYER: Streamlit cache decorators for performance
@st.cache_data(ttl=3600)  # Cache currencies for 1 hour
def cached_currency_list(api_service: APIService) -> List[str]:
    """Fetch and cache available currency list."""
    return api_service.get_currency_list()


@st.cache_data(ttl=300)  # Cache historical data for 5 minutes
def cached_historical_data(
    api_service: APIService, pair: str, start: date, end: date
) -> pd.DataFrame:
    """Fetch and cache historical OHLC data."""
    return api_service.get_historical_data(pair, start, end)


def display_conversion_result(
    base_currency: str,
    target_currency: str,
    amount: float,
    converted_total: float,
    rate: float,
) -> None:
    """Render centered conversion result card with accessibility."""
    # Type check inputs
    if not all(isinstance(x, str) for x in [base_currency, target_currency]):
        st.error("Invalid currency codes")
        return
    
    left_col, center_col, right_col = st.columns([1, 2, 1])
    card_html: str = f"""
    <div class="conversion_card" style="
        text-align: center; padding: 20px; 
        border: 2px solid #2962ff; border-radius: 12px; 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
        color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    " role="group" aria-label="conversion-result">
      <h3 style="margin: 0 0 10px 0; font-size: 1.4em;">{target_currency}</h3>
      <h1 style="margin: 0 0 15px 0; font-size: 2.5em;">{converted_total:,.4f}</h1>
      <p style="margin: 0; font-size: 1em; opacity: 0.9;">
        {amount:,.0f} {base_currency} = <strong>{rate:.5f}</strong> {target_currency}
      </p>
    </div>
    """
    with center_col:
        st.markdown(card_html, unsafe_allow_html=True)


def configure_lightweight_chart(df: pd.DataFrame, pair: str) -> Optional['StreamlitChart']:
    """Configure lightweight TradingView chart if available."""
    if not LIGHTWEIGHT_CHARTS_AVAILABLE or not isinstance(df, pd.DataFrame):
        return None
    
    try:
        chart = streamlit_lightweight_charts.StreamlitChart(height=500, width="100%")  # type: ignore
        chart.layout(background_color="#0f1419", font_size=14, font_family="Roboto")
        chart.candle_style(
            up_color="#26a69a", down_color="#ef5350",
            border_up_color="#26a69acb", border_down_color="#ef5350cb"
        )
        chart.grid(vert_enabled=True, horz_enabled=True)
        chart.legend(visible=True, ohlc=True)
        chart.watermark(f"{pair} Daily")
        return chart
    except Exception:
        return None


def plot_history_with_pivots(
    df: pd.DataFrame,
    pivots_df: pd.DataFrame,
    title: Optional[str] = None,
) -> None:
    """
    Plot OHLC with pivot overlays using fallback hierarchy:
    1. Lightweight charts (fastest)
    2. Hvplot/Bokeh (interactive)
    3. Matplotlib (reliable baseline)
    """
    # Input validation
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.warning("No valid OHLC data for plotting")
        return
    
    # Ensure date column exists
    if "date" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={df.index.name: "date"})
        else:
            st.error("DataFrame missing date column or datetime index")
            return
    
    df_work = df.copy()
    df_work["date"] = pd.to_datetime(df_work["date"], errors="coerce")
    df_work = df_work.dropna(subset=["date"])
    
    # Process pivots
    pivots_work = pivots_df.copy()
    if "date" not in pivots_work.columns:
        if isinstance(pivots_work.index, pd.DatetimeIndex):
            pivots_work = pivots_work.reset_index().rename(columns={pivots_work.index.name: "date"})
    
    pivots_work["date"] = pd.to_datetime(pivots_work["date"], errors="coerce")
    merge_cols = ["pivot", "r1", "r2", "r3", "s1", "s2", "s3"]
    available_pivots = [col for col in merge_cols if col in pivots_work.columns]
    
    merged = df_work.merge(
        pivots_work[["date"] + available_pivots], 
        on="date", how="left"
    )
    
    # PRIORITY 1: Lightweight charts
    lw_chart = configure_lightweight_chart(merged, title or "Currency Pair")
    if lw_chart is not None:
        try:
            ohlc_data = merged[["date", "open", "high", "low", "close"]].copy()
            ohlc_data["time"] = ohlc_data["date"].astype(str)
            lw_chart.candlestick(ohlc_data.drop("date", axis=1).to_dict("records"))
            return
        except Exception as e:
            st.info(f"Lightweight charts failed: {e}")
    
    # PRIORITY 2: Hvplot interactive
    if HV_AVAILABLE:
        try:
            cs = merged.hvplot.candlestick(
                x="date", open="open", high="high", low="low", close="close",
                title=title or "OHLC with Pivot Levels",
                width=950, height=500, color="green"
            )
            
            # Simple pivot overlays
            for level in available_pivots:
                if level in merged.columns:
                    series = merged.set_index("date")[[level]].ffill()
                    overlay = series.hvplot.line(y=level, color="gold", line_width=2)
                    cs = cs * overlay
                    break  # Just one for stability
            
            st.bokeh_chart(cs, use_container_width=True)
            return
        except Exception as e:
            st.info(f"Hvplot failed: {e}")
    
    # PRIORITY 3: Matplotlib (bulletproof)
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Close price line
    ax.plot(merged["date"], merged["close"], color="#2962ff", linewidth=3, 
            label="Close Price", alpha=0.9)
    
    # Pivot levels
    colors: dict[str, str] = {
        "pivot": "#FFD700", "r1": "#FF9800", "r2": "#F57C00", "r3": "#E65100",
        "s1": "#4DB6AC", "s2": "#26A69A", "s3": "#00796B"
    }
    
    for level in available_pivots:
        if level in merged.columns and merged[level].notna().any():
            series = merged[level].ffill().bfill()
            ax.plot(merged["date"], series, color=colors.get(level, "#999"),
                   linestyle="--", linewidth=2, alpha=0.8, label=level)
    
    # Formatting
    ax.set_title(title or "Currency OHLC with Pivot Levels", fontsize=16, fontweight="bold", pad=20)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Price", fontsize=12)
    ax.legend(loc="upper left", framealpha=0.9)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    fig.autofmt_xdate()
    plt.tight_layout()
    st.pyplot(fig)


def initialize_app() -> None:
    """Configure Streamlit page and load custom CSS."""
    st.set_page_config(
        page_title="Currency Exchange Tracker",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown("""
    <style>
    .conversion_card { transition: all 0.3s ease; }
    .conversion_card:hover { transform: scale(1.02); }
    </style>
    """, unsafe_allow_html=True)


def main() -> None:
    """Main application entrypoint with error handling."""
    initialize_app()
    st.title("🌍 Currency Exchange Tracker")
    st.markdown("---")
    
    # VALIDATION: Check API key first
    if not API_KEY or not isinstance(API_KEY, str) or len(API_KEY) < 10:
        st.error("""
        ❌ **Missing TraderMade API Key!**
        
        **Fix:** Create `.streamlit/secrets.toml`:
        ```toml
        TRADERMADE_API_KEY = "your_key_from_tradermade.com"
        ```
        Get free key: https://tradermade.com
        """)
        st.stop()
    
    # Initialize services
    api_service: APIService = APIService(API_KEY)
    data_processor: DataProcessor = DataProcessor()
    
    # Load currency list
    if "currency_list" not in st.session_state:
        try:
            st.session_state.currency_list = cached_currency_list(api_service)
        except Exception as e:
            st.error(f"❌ Failed to load currencies: {str(e)}")
            st.session_state.currency_list: List[str] = [
                "USD (US Dollar)", "EUR (Euro)", "GBP (Pound Sterling)"
            ]
    
    # CONVERSION UI
    st.header("💱 Live Currency Conversion")
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        base_currency: str = st.selectbox(
            "From", st.session_state.currency_list, index=0, key="base_currency"
        )
        base_code: str = get_currency_codes(base_currency)
    
    with col2:
        amount: float = st.number_input(
            f"Amount ({base_code or 'USD'})", 
            min_value=0.01, value=1000.0, step=100.0, key="amount"
        )
    
    with col3:
        quote_currency: List[str] = st.multiselect(
            "To",
            st.session_state.currency_list,
            default=st.session_state.currency_list[1:3] if len(st.session_state.currency_list) > 2 
            else [st.session_state.currency_list[0]],
            key="quote_currency"
        )
    
    # Convert button
    if st.button("🔄 Convert Currencies", type="primary", use_container_width=True):
        for target_currency in quote_currency:
            target_code: str = get_currency_codes(target_currency)
            if not target_code or target_code == base_code:
                continue
                
            try:
                converted_total: float
                rate: float
                converted_total, rate = api_service.convert_currency(base_code, target_code, amount)
                display_conversion_result(base_code, target_code, amount, converted_total, rate)
            except Exception as e:
                st.error(f"❌ {target_code}: {str(e)}")
    
    # HISTORICAL DATA
    st.markdown("---")
    st.header("📈 Historical Analysis")
    
    col4, col5, col6 = st.columns([2, 2, 2])
    with col4:
        pair_input: str = st.text_input("Currency Pair (e.g., EURUSD)", value="EURUSD", help="No spaces, 6 chars")
    with col5:
        start: date = st.date_input("Start Date", value=date.today().replace(year=date.today().year - 1))
    with col6:
        end: date = st.date_input("End Date", value=date.today())
    
    if start > end:
        st.warning("Start date must be before end date")
    
    if st.button("📊 Load Historical Data & Pivots", type="secondary"):
        try:
            with st.spinner("Fetching data from TraderMade..."):
                df: pd.DataFrame = cached_historical_data(api_service, pair_input, start, end)
            
            if df.empty:
                st.warning("No historical data returned for this pair/range")
            else:
                # Process data
                processed: pd.DataFrame = data_processor.prepare_chart_data(df)
                pivots: pd.DataFrame = data_processor.calculate_pivot_points(processed)
                volatility: pd.DataFrame = data_processor.calculate_historical_volatility(processed)
                
                # Display tables
                col_table1, col_table2 = st.columns(2)
                with col_table1:
                    st.subheader("Recent OHLC")
                    st.dataframe(processed[["date", "open", "high", "low", "close"]].tail(10), 
                               use_container_width=True)
                with col_table2:
                    st.subheader("Recent Pivot Levels")
                    pivot_cols = ["date", "pivot", "r1", "s1", "r2", "s2"]
                    st.dataframe(pivots[pivot_cols].tail(10), use_container_width=True)
                
                st.subheader(f"📉 {pair_input} Chart with Pivot Points")
                plot_history_with_pivots(processed, pivots, f"{pair_input} Daily Pivots")
                
                # Volatility metric
                latest_vol: float = volatility["hv"].iloc[-1] if "hv" in volatility.columns else 0
                st.metric("Latest Volatility (Annualized)", f"{latest_vol:.1f}%")
                
        except Exception as e:
            st.error(f"❌ Data loading failed: {str(e)}")
            st.info("Try: EURUSD, GBPUSD, USDJPY")


if __name__ == "__main__":
    main()
