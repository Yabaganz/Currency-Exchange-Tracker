"""
Main Streamlit application for Currency Exchange Tracker.

Features:
- Currency conversion via TraderMade API
- Cached API calls to reduce network usage
- Historical OHLC plotting with pivot overlays
  - Primary: hvplot / Holoviews interactive chart
  - Fallback: matplotlib static chart
- Streamlit UI and CSS injection support
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

from api_service import APIService
from data_processor import DataProcessor

# Chart library import for a native lightweight chart (optional)
# Keep as a soft dependency; import guarded in plotting functions if needed
try:
    from streamlit_lightweight_charts import StreamlitChart  # type: ignore
    LIGHTWEIGHT_CHARTS_AVAILABLE = True
except Exception:
    LIGHTWEIGHT_CHARTS_AVAILABLE = False

# Load API key from Streamlit secrets (or environment via Streamlit secrets)
API_KEY: str = st.secrets.get("GVM9PgfkeLrGqXoK_uEV", "")  # type: ignore


def get_currency_codes(currency_label: str) -> str:
    """Extract the 3-letter currency code from a label like "USD (US Dollar)\"."""
    if not currency_label:
        return ""
    return currency_label.split()[0].strip()


# -------------------------
# Caching wrappers
# -------------------------
@st.cache_data(ttl=3600)
def cached_currency_list(api_service: APIService) -> List[str]:
    """Return available currencies (cached for 1 hour)."""
    return api_service.get_currency_list()


@st.cache_data(ttl=300)
def cached_historical_data(api_service: APIService, pair: str, start: date, end: date) -> pd.DataFrame:
    """Return historical OHLC data (cached for 5 minutes)."""
    return api_service.get_historical_data(pair, start, end)


# -------------------------
# UI helpers
# -------------------------
def display_conversion_result(
    base_currency: str,
    target_currency: str,
    amount: float,
    converted_total: float,
    rate: float,
) -> None:
    """
    Render a single conversion result as a centered card.

    The card is placed in the middle of three equal columns to ensure horizontal centering.
    """
    left_col, center_col, right_col = st.columns([1, 1, 1])

    card_html = f"""
    <div class="conversion_card" role="group" aria-label="conversion-result">
      <p class="converted_currency">{target_currency}</p>
      <p class="converted_total">{converted_total}</p>
      <p class="details_text">( {base_currency} = {rate} {target_currency} )</p>
    </div>
    """

    with center_col:
        st.markdown(card_html, unsafe_allow_html=True)


def configure_lightweight_chart(df: pd.DataFrame, pair: str):
    """
    Configure a StreamlitChart instance if the lightweight charts package is available.

    Returns:
        chart instance or None if not available.
    """
    if not LIGHTWEIGHT_CHARTS_AVAILABLE:
        return None

    chart = StreamlitChart(height=450, width=950)
    chart.grid(vert_enabled=True, horz_enabled=True)
    chart.layout(background_color="#131722", font_family="Trebuchet MS", font_size=16)
    chart.candle_style(
        up_color="#2962ff",
        down_color="#e91e63",
        border_up_color="#2962ffcb",
        border_down_color="#e91e63cb",
        wick_up_color="#2962ffcb",
        wick_down_color="#e91e63cb",
    )
    chart.watermark(f"{pair} 1D")
    chart.legend(visible=True, font_family="Trebuchet MS", ohlc=True, percent=True)
    return chart


# -------------------------
# Plotting: hvplot primary, matplotlib fallback
# -------------------------
# Detect hvplot/holoviews availability
try:
    import hvplot.pandas  # noqa: F401
    import holoviews as hv  # type: ignore
    HV_AVAILABLE = True
except Exception:
    HV_AVAILABLE = False

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_history_with_pivots(
    df: pd.DataFrame,
    pivots_df: pd.DataFrame,
    title: Optional[str] = None,
) -> None:
    """
    Plot OHLC history with pivot levels overlaid.

    Primary method: hvplot (interactive). Fallback: matplotlib static plot.

    Args:
        df: DataFrame with columns ['date','open','high','low','close'] or datetime index.
        pivots_df: DataFrame with pivot columns (pivot, r1, r2, r3, s1, s2, s3) indexed by date.
        title: Optional chart title.
    """
    # Ensure date column exists
    if "date" not in df.columns:
        df = df.reset_index().rename(columns={"index": "date"}) if df.index.name else df.reset_index()
    df["date"] = pd.to_datetime(df["date"])

    # Align pivots to the same date column
    pivots = pivots_df.copy()
    if "date" not in pivots.columns:
        pivots = pivots.reset_index().rename(columns={"index": "date"}) if pivots.index.name else pivots.reset_index()
    pivots["date"] = pd.to_datetime(pivots["date"])

    merged = df.merge(
        pivots[["date", "pivot", "r1", "r2", "r3", "s1", "s2", "s3"]],
        on="date",
        how="left",
    )

    # Primary: hvplot interactive candlestick + pivot overlays
    if HV_AVAILABLE:
        try:
            cs = merged.hvplot.candlestick(
                x="date",
                open="open",
                high="high",
                low="low",
                close="close",
                title=title or "OHLC with Pivot Levels",
                width=900,
                height=450,
            )

            curves = []
            # Define colors and widths for pivot lines
            pivot_specs = [
                ("pivot", "#FFD700", 2),
                ("r1", "#FF7F50", 1),
                ("r2", "#FF4500", 1),
                ("r3", "#FF0000", 1),
                ("s1", "#7FFFD4", 1),
                ("s2", "#40E0D0", 1),
                ("s3", "#008B8B", 1),
            ]

            for col, color, lw in pivot_specs:
                if col in merged.columns:
                    series = merged[["date", col]].set_index("date")[col].ffill().bfill()
                    curve = series.hvplot.line(x=series.index, y=series.name, color=color, line_width=lw, legend_label=col)
                    curves.append(curve)

            overlay = cs * hv.NdOverlay({i: c for i, c in enumerate(curves)})
            bokeh_obj = hv.render(overlay, backend="bokeh")
            st.bokeh_chart(bokeh_obj, use_container_width=True)
            return
        except Exception:
            # If hvplot rendering fails, fall through to matplotlib fallback
            pass

    # Fallback: matplotlib static plot
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(merged["date"], merged["close"], color="#1f77b4", label="Close")

    # Draw high-low vertical lines and open-close rectangles
    for _, row in merged.iterrows():
        ax.vlines(row["date"], row["low"], row["high"], color="#333333", alpha=0.6, linewidth=1)
        o, c = row["open"], row["close"]
        color = "#2ca02c" if c >= o else "#d62728"
        ax.add_patch(
            plt.Rectangle(
                (mdates.date2num(row["date"]) - 0.2, min(o, c)),
                0.4,
                abs(c - o) if abs(c - o) > 0 else 0.00001,
                color=color,
                alpha=0.8,
            )
        )

    # Plot pivot lines
    colors = {
        "pivot": "#FFD700",
        "r1": "#FF7F50",
        "r2": "#FF4500",
        "r3": "#FF0000",
        "s1": "#7FFFD4",
        "s2": "#40E0D0",
        "s3": "#008B8B",
    }
    for level in ["pivot", "r1", "r2", "r3", "s1", "s2", "s3"]:
        if level in merged.columns:
            series = merged[level].ffill().bfill()
            ax.plot(merged["date"], series, color=colors.get(level, "#999999"), linestyle="--", linewidth=1.2, label=level)

    ax.set_title(title or "OHLC with Pivot Levels")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left", fontsize="small")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    st.pyplot(fig)


# -------------------------
# App initialization and main
# -------------------------
def initialize_app() -> None:
    """Set page config and title. Load CSS if present."""
    st.set_page_config(page_title="Currency Exchange Tracker", layout="wide")
    st.title("Currency Exchange Tracker")
    # Optionally load style.css if present in repo root
    try:
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # No CSS file found; continue without custom styles
        pass


def main() -> None:
    """Main application entrypoint."""
    initialize_app()
    api_service = APIService(API_KEY)
    data_processor = DataProcessor()

    # Load currency list (cached)
    if "currency_list" not in st.session_state:
        try:
            st.session_state.currency_list = cached_currency_list(api_service)
        except Exception as e:
            st.error(f"Failed to load currency list: {str(e)}")
            st.session_state.currency_list = ["USD (US Dollar)", "EUR (Euro)"]

    if not st.session_state.currency_list:
        st.session_state.currency_list = ["USD (US Dollar)", "EUR (Euro)"]

    # Conversion UI
    with st.container():
        from_col, amount_col, _, text_col, _, to_col = st.columns([0.5, 0.5, 0.05, 0.08, 0.05, 0.5])

        with from_col:
            base_currency = st.selectbox("From", st.session_state.currency_list, index=0, key="base_currency")
            base_code = get_currency_codes(base_currency)

        with amount_col:
            amount = st.number_input(f"Amount (in {base_code})", min_value=1.0, value=1.0, key="amount")

        with to_col:
            quote_currency = st.multiselect(
                "To",
                st.session_state.currency_list,
                default=[st.session_state.currency_list[1] if len(st.session_state.currency_list) > 1 else st.session_state.currency_list[0]],
                key="quote_currency",
            )
            quote_codes: List[str] = [get_currency_codes(q) for q in quote_currency]

        st.markdown("")
        _, _, _, _, button_col = st.columns([0.06, 0.16, 0.26, 0.6, 0.1])

        with button_col:
            convert = st.button("Convert")

            if convert and quote_currency:
                for target, target_code in zip(quote_currency, quote_codes):
                    try:
                        converted_total, rate = api_service.convert_currency(base_code, target_code, amount)
                        display_conversion_result(base_code, target_code, amount, converted_total, rate)
                    except Exception as e:
                        st.error(str(e))

    # Historical data and charting
    st.markdown("---")
    st.subheader("Historical Data & Chart")
    pair_input = st.text_input("Enter currency pair (e.g., EURUSD)", value="EURUSD")
    start = st.date_input("Start date", value=date.today().replace(year=date.today().year - 1))
    end = st.date_input("End date", value=date.today())

    if st.button("Load Historical Data"):
        try:
            df = cached_historical_data(api_service, pair_input, start, end)
            if df.empty:
                st.warning("No historical data returned.")
            else:
                # Ensure expected column names (rename if API uses different casing)
                # Example mapping (uncomment and adapt if needed):
                # df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close'}, inplace=True)

                # Compute pivots and volatility
                pivots = data_processor.calculate_pivot_points(df)
                hv = data_processor.calculate_historical_volatility(df)

                # Prepare data for plotting (reset index so 'date' is a column)
                processed = data_processor.prepare_chart_data(df)

                st.subheader("Recent Data")
                st.dataframe(processed.tail(5))

                st.subheader("Pivot Levels (recent)")
                st.dataframe(pivots[["pivot", "r1", "r2", "r3", "s1", "s2", "s3"]].tail(5))

                # Try lightweight chart first if available and compatible
                lw_chart = configure_lightweight_chart(processed, pair_input)
                if lw_chart is not None:
                    try:
                        # Some versions of the lightweight chart expect a specific method; try .plot then fallback
                        try:
                            lw_chart.plot(processed)
                        except Exception:
                            # If .plot is not available, attempt to set data and render (best-effort)
                            if hasattr(lw_chart, "set_data"):
                                lw_chart.set_data(processed)
                            else:
                                # If API mismatch, fallback to hvplot/matplotlib
                                raise RuntimeError("lightweight chart API mismatch")
                        st.success("Rendered with lightweight chart")
                    except Exception:
                        # Fallback to hvplot/matplotlib plotting helper
                        plot_history_with_pivots(processed, pivots, title=f"{pair_input} - OHLC & Pivots")
                else:
                    # No lightweight charts available; use hvplot/matplotlib helper
                    plot_history_with_pivots(processed, pivots, title=f"{pair_input} - OHLC & Pivots")

        except Exception as e:
            st.error(str(e))


if __name__ == "__main__":
    main()
