import streamlit as st
import pandas as pd
import yfinance as yf
from option_chain_utils import get_nifty_option_chain
from io import BytesIO
import requests
from datetime import datetime, time
import pytz

# ---------------------------
# Settings
STOP_LOSS_PCT = 0.01  # 1%
TARGET_PCT = 0.02     # 2%

# ---------------------------
st.title("📌 Nifty 50 Options Trade Signal App with SL/Target & Export")

# Function to check if market is open (NSE market hours: 9:15 AM to 3:30 PM IST on weekdays)
def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    market_open_time = time(9, 15)
    market_close_time = time(15, 30)
    # Market open Mon-Fri
    if now.weekday() < 5 and market_open_time <= now.time() <= market_close_time:
        return True
    return False

def fetch_live_data():
    try:
        df = yf.download("^NSEI", period="1d", interval="5m")
        if df.empty:
            return None
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df.dropna(subset=['Close'], inplace=True)
        if len(df) < 20:
            return None
        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        return df
    except Exception:
        return None

def fetch_daily_data():
    try:
        df = yf.download("^NSEI", period="3mo", interval="1d")
        if df.empty:
            st.error("❌ No daily data downloaded from Yahoo Finance.")
            return pd.DataFrame()
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df.dropna(subset=['Close'], inplace=True)
        if len(df) < 20:
            st.warning(f"⚠️ Insufficient daily data points ({len(df)} rows) to calculate EMA20.")
            return pd.DataFrame()
        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        return df
    except Exception as e:
        st.error(f"❌ Error fetching or processing daily Nifty data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_data():
    if is_market_open():
        st.info("⏳ Market is OPEN: Trying to fetch live intraday 5-minute data.")
        df = fetch_live_data()
        if df is None or df.empty:
            st.warning("⚠️ Live intraday data not available, falling back to daily historical data.")
            df = fetch_daily_data()
        else:
            st.success("✅ Live intraday data fetched successfully.")
    else:
        st.info("⏳ Market is CLOSED: Fetching daily historical data.")
        df = fetch_daily_data()
    return df

def generate_signals(df):
    df["Signal"] = ""
    if "EMA5" in df.columns and "EMA20" in df.columns and not df["EMA5"].isnull().all() and not df["EMA20"].isnull().all():
        df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
        df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    else:
        st.warning("⚠️ EMA columns not found or invalid for signal generation.")
    return df

def apply_sl_target(df):
    if 'Close' in df.columns and pd.api.types.is_numeric_dtype(df['Close']):
        df["Entry"] = df["Close"]
    else:
        df["Entry"] = None
        st.warning("⚠️ 'Close' column not valid for Entry price.")

    df["StopLoss"] = df.apply(
        lambda row: row["Entry"] * (1 - STOP_LOSS_PCT) if row.get("Signal") == "Buy" and pd.notna(row["Entry"])
        else row["Entry"] * (1 + STOP_LOSS_PCT) if row.get("Signal") == "Sell" and pd.notna(row["Entry"])
        else None,
        axis=1
    )

    df["Target"] = df.apply(
        lambda row: row["Entry"] * (1 + TARGET_PCT) if row.get("Signal") == "Buy" and pd.notna(row["Entry"])
        else row["Entry"] * (1 - TARGET_PCT) if row.get("Signal") == "Sell" and pd.notna(row["Entry"])
        else None,
        axis=1
    )
    return df

def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True, sheet_name='Signals')
    return output.getvalue()

# Load & Process Data
df = fetch_data()
if not df.empty and all(col in df.columns for col in ["Close", "EMA5", "EMA20"]):
    df = generate_signals(df)
    df = apply_sl_target(df)

    st.subheader("📈 EMA Strategy Chart")
    chart_columns = [col for col in ["Close", "EMA5", "EMA20"] if col in df.columns]
    if chart_columns:
        st.line_chart(df[chart_columns])
    else:
        st.warning("⚠️ Cannot plot chart. Required columns missing.")

    last = df[df["Signal"].isin(["Buy", "Sell"])].tail(1)
    if not last.empty:
        signal_cols = [col for col in ["Close", "EMA5", "EMA20", "Signal", "StopLoss", "Target"] if col in last.columns]
        st.success(f"💡 Last Signal: {last['Signal'].values[0]} on {last.index[-1].date()}")
        if signal_cols:
            st.write(last[signal_cols])
        else:
            st.info("Details for last signal are missing.")
    else:
        st.info("No buy/sell signals generated yet.")

    st.subheader("📥 Export Signals to Excel")
    signal_df = df[df["Signal"].isin(["Buy", "Sell"])]
    if not signal_df.empty:
        excel_data = convert_df_to_excel(signal_df)
        st.download_button("📤 Download Signals", excel_data, file_name="nifty_signals.xlsx")
    else:
        st.info("No signals to export.")
else:
    st.error("📉 Could not generate signals or charts due to data issues.")

# Option Chain
st.subheader("📄 Option Chain Data (OI > 100K)")
try:
    oc = get_nifty_option_chain()
    if isinstance(oc, pd.DataFrame) and not oc.empty:
        if 'openInterest' in oc.columns:
            oc['openInterest'] = pd.to_numeric(oc['openInterest'], errors='coerce')
            oc.dropna(subset=['openInterest'], inplace=True)
            filtered_oc = oc[oc["openInterest"] > 100000]
            if not filtered_oc.empty:
                st.dataframe(filtered_oc.head(20))
            else:
                st.info("Option chain has no entries with OI > 100K after cleaning.")
        else:
            st.info("'openInterest' column missing in option chain.")
            st.dataframe(oc.head(20))
    elif oc is None:
        st.warning("⚠️ Option chain API returned None.")
    else:
        st.info("No option chain data available.")
except requests.exceptions.JSONDecodeError as json_e:
    st.error("❌ Invalid JSON response for option chain.")
    st.exception(json_e)
except Exception as e:
    st.error("❌ Unexpected error loading option chain")
    st.exception(e)
