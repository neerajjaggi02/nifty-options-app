import streamlit as st
import pandas as pd
import yfinance as yf
from option_chain_utils import get_nifty_option_chain
from io import BytesIO

# ---------------------------
# Settings
STOP_LOSS_PCT = 0.01  # 1%
TARGET_PCT = 0.02     # 2%

# ---------------------------
st.title("📌 Nifty 50 Options Trade Signal App with SL/Target & Export")

@st.cache_data(ttl=3600)
def fetch_data():
    try:
        df = yf.download("^NSEI", period="3mo", interval="1d")
        if df.empty:
            st.error("❌ No data downloaded from Yahoo Finance. Please check the ticker symbol or your internet connection.")
            return pd.DataFrame() # Return an empty DataFrame
        
        # Ensure 'Close' column exists before proceeding
        if 'Close' not in df.columns:
            st.error("❌ 'Close' column not found in the downloaded data. Data might be incomplete or malformed.")
            return pd.DataFrame()
            
        df.dropna(inplace=True)
        if df.empty:
            st.warning("⚠️ All rows were dropped after `dropna()`. This might indicate significant missing data.")
            return pd.DataFrame()

        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        return df
    except Exception as e:
        st.error(f"❌ Error fetching data: {e}. Please ensure '^NSEI' is a valid ticker and you have an internet connection.")
        return pd.DataFrame()

def generate_signals(df):
    df["Signal"] = ""
    df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
    df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    return df

def apply_sl_target(df):
    df["Entry"] = df["Close"]
    df["StopLoss"] = df.apply(
        lambda row: row["Entry"] * (1 - STOP_LOSS_PCT) if str(row.get("Signal", "")) == "Buy" 
        else row["Entry"] * (1 + STOP_LOSS_PCT) if str(row.get("Signal", "")) == "Sell" 
        else None,
        axis=1
    )
    df["Target"] = df.apply(
        lambda row: row["Entry"] * (1 + TARGET_PCT) if str(row.get("Signal", "")) == "Buy" 
        else row["Entry"] * (1 - TARGET_PCT) if str(row.get("Signal", "")) == "Sell" 
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

# Only proceed if DataFrame is not empty and has required columns
if not df.empty and all(col in df.columns for col in ["Close", "EMA5", "EMA20"]):
    df = generate_signals(df)
    df = apply_sl_target(df)

    # Charts
    st.subheader("📈 EMA Strategy Chart")
    st.line_chart(df[["Close", "EMA5", "EMA20"]])

    # Show Latest Signal
    last = df[df["Signal"].isin(["Buy", "Sell"])].tail(1)
    if not last.empty:
        st.success(f"💡 Last Signal: {last['Signal'].values[0]} on {last.index[-1].date()}")
        st.write(last[["Close", "EMA5", "EMA20", "Signal", "StopLoss", "Target"]])
    else:
        st.info("No buy/sell signals generated yet.")

    # Export to Excel
    st.subheader("📥 Export Signals to Excel")
    signal_df = df[df["Signal"].isin(["Buy", "Sell"])]
    if not signal_df.empty:
        excel_data = convert_df_to_excel(signal_df)
        st.download_button("📤 Download Signals", excel_data, file_name="nifty_signals.xlsx")
    else:
        st.info("No signals to export.")
else:
    st.error("📉 Could not generate charts or signals due to data issues.")

---

# Option Chain
st.subheader("📄 Option Chain Data (OI > 100K)")
try:
    oc = get_nifty_option_chain()
    if not oc.empty:
        st.dataframe(oc[oc["openInterest"] > 100000].head(20))
    else:
        st.info("No option chain data available or conditions not met.")
except Exception as e:
    st.error("❌ Failed to load option chain")
    st.exception(e)
