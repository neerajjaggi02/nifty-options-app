import streamlit as st
import pandas as pd
import yfinance as yf
from option_chain_utils import get_nifty_option_chain # Assuming this utility exists and works
from io import BytesIO
import requests
from datetime import datetime, time
import pytz

# --- Settings ---
STOP_LOSS_PCT = 0.01  # 1%
TARGET_PCT = 0.02     # 2%

# --- Streamlit Title ---
st.title("📌 Nifty 50 Options Trade Signal App with SL/Target & Export")

# --- Utility Functions ---

def is_market_open():
    """
    Checks if the NSE market is currently open.
    Market hours: 9:15 AM to 3:30 PM IST, Monday to Friday.
    """
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    market_open_time = time(9, 15)
    market_close_time = time(15, 30)

    # Market open Mon-Fri and within specified hours
    if now.weekday() < 5 and market_open_time <= now.time() <= market_close_time:
        return True
    return False

# --- Data Fetching Functions ---

def fetch_live_data_from_api():
    """
    Attempts to fetch live intraday (5-minute interval) Nifty 50 data.
    **IMPORTANT:** For truly live, real-time data, you should replace the yfinance call
    here with an integration to a dedicated live data API (e.g., from a broker like Zerodha,
    Upstox, or a data vendor).
    """
    try:
        # --- REPLACE THIS SECTION WITH YOUR ACTUAL LIVE DATA API CALL ---
        # Example using yfinance as a placeholder (may not be truly real-time):
        df_yf = yf.download("^NSEI", period="1d", interval="5m")

        if df_yf.empty:
            st.warning("⚠️ yfinance returned empty data for intraday period.")
            return None

        # Ensure 'Close' is numeric and handle potential missing values
        df_yf['Close'] = pd.to_numeric(df_yf['Close'], errors='coerce')
        df_yf.dropna(subset=['Close'], inplace=True)

        if df_yf.empty:
            st.warning("⚠️ No valid 'Close' prices in intraday data after cleaning.")
            return None

        # Ensure enough data points for EMA calculation (at least 20 for EMA20)
        if len(df_yf) < 20:
            st.warning(f"⚠️ Insufficient live intraday data points ({len(df_yf)} rows) for EMA calculation.")
            return None

        df_yf["EMA5"] = df_yf["Close"].ewm(span=5, adjust=False).mean()
        df_yf["EMA20"] = df_yf["Close"].ewm(span=20, adjust=False).mean()
        return df_yf
        # --- END OF REPLACEABLE SECTION ---

    except Exception as e:
        st.error(f"❌ Error fetching live intraday Nifty data (using yfinance fallback): {e}")
        return None

def fetch_daily_data_offline():
    """
    Fetches historical daily Nifty 50 data (last 6 months).
    This is used when the market is closed or live data fetching fails.
    """
    try:
        df = yf.download("^NSEI", period="6mo", interval="1d") # Increased period for more historical context
        if df.empty:
            st.error("❌ No daily data downloaded from Yahoo Finance.")
            return pd.DataFrame()

        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df.dropna(subset=['Close'], inplace=True)

        if df.empty:
            st.warning("⚠️ No valid 'Close' prices in daily data after cleaning.")
            return pd.DataFrame()

        if len(df) < 20:
            st.warning(f"⚠️ Insufficient daily data points ({len(df)} rows) to calculate EMA20.")
            return pd.DataFrame()

        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        return df
    except Exception as e:
        st.error(f"❌ Error fetching or processing daily Nifty data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60) # Cache data for 60 seconds (1 minute) to allow frequent updates during market hours
def fetch_data():
    """
    Orchestrates data fetching: live if market open, otherwise daily historical.
    """
    if is_market_open():
        st.info("⏳ Market is **OPEN**: Attempting to fetch live intraday 5-minute data.")
        df = fetch_live_data_from_api()
        if df is None or df.empty:
            st.warning("⚠️ Live intraday data not available or failed. Falling back to daily historical data.")
            df = fetch_daily_data_offline()
        else:
            st.success("✅ Live intraday data fetched successfully.")
    else:
        st.info("⏳ Market is **CLOSED**: Fetching daily historical data.")
        df = fetch_daily_data_offline()
    return df

# --- Signal Generation and SL/Target Calculation ---

def generate_signals(df):
    """Generates Buy/Sell signals based on EMA crossover strategy."""
    df["Signal"] = ""
    if "EMA5" in df.columns and "EMA20" in df.columns and not df["EMA5"].isnull().all() and not df["EMA20"].isnull().all():
        # Buy signal: EMA5 crosses above EMA20
        df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
        # Sell signal: EMA5 crosses below EMA20
        df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    else:
        st.warning("⚠️ EMA columns not found or invalid for signal generation.")
    return df

def apply_sl_target(df):
    """Calculates Stop Loss and Target prices based on signals and predefined percentages."""
    if 'Close' in df.columns and pd.api.types.is_numeric_dtype(df['Close']):
        df["Entry"] = df["Close"]
    else:
        df["Entry"] = None
        st.warning("⚠️ 'Close' column not valid for Entry price.")

    # Calculate Stop Loss
    df["StopLoss"] = df.apply(
        lambda row: row["Entry"] * (1 - STOP_LOSS_PCT) if row.get("Signal") == "Buy" and pd.notna(row["Entry"])
        else row["Entry"] * (1 + STOP_LOSS_PCT) if row.get("Signal") == "Sell" and pd.notna(row["Entry"])
        else None,
        axis=1
    )

    # Calculate Target
    df["Target"] = df.apply(
        lambda row: row["Entry"] * (1 + TARGET_PCT) if row.get("Signal") == "Buy" and pd.notna(row["Entry"])
        else row["Entry"] * (1 - TARGET_PCT) if row.get("Signal") == "Sell" and pd.notna(row["Entry"])
        else None,
        axis=1
    )
    return df

def convert_df_to_excel(df):
    """Converts a DataFrame to an Excel file in bytes."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True, sheet_name='Signals')
    return output.getvalue()

# --- Main Application Logic ---

# Fetch, process, and display data and signals
df = fetch_data()
if not df.empty and all(col in df.columns for col in ["Close", "EMA5", "EMA20"]):
    df = generate_signals(df)
    df = apply_sl_target(df)

    st.subheader("📈 EMA Strategy Chart")
    chart_columns = [col for col in ["Close", "EMA5", "EMA20"] if col in df.columns]
    if chart_columns:
        st.line_chart(df[chart_columns])
    else:
        st.warning("⚠️ Cannot plot chart. Required columns (Close, EMA5, EMA20) missing.")

    # Display the last generated signal
    last_signal_df = df[df["Signal"].isin(["Buy", "Sell"])].tail(1)
    if not last_signal_df.empty:
        signal_cols = [col for col in ["Close", "EMA5", "EMA20", "Signal", "StopLoss", "Target"] if col in last_signal_df.columns]
        st.success(f"💡 Last Signal: **{last_signal_df['Signal'].values[0]}** on **{last_signal_df.index[-1].date()}**")
        if signal_cols:
            st.dataframe(last_signal_df[signal_cols]) # Using st.dataframe for better display of small tables
        else:
            st.info("Details for the last signal are missing.")
    else:
        st.info("No buy/sell signals generated yet based on the EMA crossover strategy.")

    st.subheader("📥 Export Signals to Excel")
    signal_df_to_export = df[df["Signal"].isin(["Buy", "Sell"])]
    if not signal_df_to_export.empty:
        excel_data = convert_df_to_excel(signal_df_to_export)
        st.download_button("📤 Download Signals", excel_data, file_name="nifty_signals.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No signals to export.")
else:
    st.error("📉 Could not generate signals or charts due to fundamental data issues. Please check data fetching logs.")

---

# Option Chain Data

st.subheader("📄 Option Chain Data (OI > 100K)")
try:
    # Assuming get_nifty_option_chain() fetches the latest option chain data
    oc = get_nifty_option_chain()
    if isinstance(oc, pd.DataFrame) and not oc.empty:
        if 'openInterest' in oc.columns:
            oc['openInterest'] = pd.to_numeric(oc['openInterest'], errors='coerce')
            oc.dropna(subset=['openInterest'], inplace=True)
            # Filter for Open Interest greater than 100,000
            filtered_oc = oc[oc["openInterest"] > 100000]
            if not filtered_oc.empty:
                st.dataframe(filtered_oc.head(20)) # Display top 20 entries
            else:
                st.info("Option chain has no entries with Open Interest > 100K after cleaning.")
        else:
            st.info("'openInterest' column missing in option chain. Displaying full data (first 20 rows).")
            st.dataframe(oc.head(20))
    elif oc is None:
        st.warning("⚠️ Option chain API returned None. Data might be unavailable.")
    else:
        st.info("No option chain data available or DataFrame is empty.")
except requests.exceptions.JSONDecodeError as json_e:
    st.error("❌ Invalid JSON response received for option chain. The source might be returning malformed data.")
    st.exception(json_e)
except Exception as e:
    st.error(f"❌ Unexpected error loading option chain: {e}")
    st.exception(e)
