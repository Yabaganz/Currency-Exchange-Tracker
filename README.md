# Currency-Exchange-Tracker
A robust and modular Streamlit app for tracking live currency exchange rates, analyzing historical trends, and computing financial indicators like volatility and pivot points.
A Streamlit app that fetches currency lists, converts amounts, and displays historical OHLC charts with pivot overlays.

## Features

- Fetches available currencies and performs live conversions via the TraderMade API.
- Displays conversion results as centered cards.
- Loads historical OHLC data and plots candlesticks with pivot levels (pivot, R1/R2/R3, S1/S2/S3).
- Interactive plotting via **hvplot / Holoviews** with a **matplotlib** fallback.
- Caching of API responses using Streamlit's `@st.cache_data` to reduce network calls.
- Simple, reusable modules: `app.py`, `api_service.py`, `data_processor.py`, and `style.css`.

## Files

- `app.py` — main Streamlit application and UI.
- `api_service.py` — TraderMade API wrapper (requests with timeouts and validation).
- `data_processor.py` — volatility, pivot calculations, and chart data preparation.
- `style.css` — custom styles for conversion cards and layout.
- `requirements.txt` — pinned dependencies for reproducible installs.
- `Procfile` (optional) — `web: streamlit run app.py` for some deployment platforms.

## Setup

1. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   .venv\Scripts\activate      # Windows
##contributors
* *Abdullahi Yusuf* ([yabaganz](https://github.com/Yabaganz))
* *Charles I Ella* ([Karldrogo-art](https://github.com/kaldrogo-art))
* *Alamin Abdullatif* ([Gebeks](https://gist.github.com/Gebeks))
* *Sijuwola E. Olatiilu* ([Siju](https://github.com/Sijuwola))
