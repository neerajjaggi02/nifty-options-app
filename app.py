import streamlit as st
import pandas as pd
import yfinance as yf
from io import BytesIO

# ---------------------------
# Settings
STOP_LOSS_PCT = 0.01  # 1%
TARGET_PCT = 0.02     # 2%

# ---------------------------
st.title("📌 Nifty 50 Options Trade Signal App with SL/Target & Export")

@st.cache_data(ttl=3600)
def fetch_data():
    """Fetches Nifty 50 historical data for the last 3 months."""
    try:
        df = yf.download("^NSEI", period="3mo", interval="1d")
        if df.empty:
            st.error("❌ Failed to fetch data. Check your internet connection or ticker symbol.")
            return pd.DataFrame()  # Return empty DataFrame to prevent errors
        df.dropna(inplace=True)
        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        return df
    except Exception as e:
        st.error(f"❌ Error fetching data: {e}")
        return pd.DataFrame()

def generate_signals(df):
    """Generates Buy/Sell signals based on EMA crossover strategy."""
    if df.empty:
        return df  # Prevent further errors

    df["Signal"] = ""
    df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
    df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    return df

def apply_sl_target(df):
    """Calculates stop-loss and target prices based on signal type."""
    if df.empty:
        return df

    df["StopLoss"] = None
    df["Target"] = None

    for i in df.index:
        signal = df.at[i, "Signal"]
        entry = df.at[i, "Close"]

        if pd.notna(signal) and signal in ["Buy", "Sell"]:
            if signal == "Buy":
                df.at[i, "StopLoss"] = entry * (1 - STOP_LOSS_PCT)
                df.at[i, "Target"] = entry * (1 + TARGET_PCT)
            else:
                df.at[i, "StopLoss"] = entry * (1 + STOP_LOSS_PCT)
                df.at[i, "Target"] = entry * (1 - TARGET_PCT)

    return df

def convert_df_to_excel(df):
    """Converts DataFrame to an Excel file format."""
    if df.empty:
        return None
    
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=True, sheet_name='Signals')
        return output.getvalue()
    except Exception as e:
        st.error(f"❌ Error creating Excel file: {e}")
        return None

# Load & Process Data
df = fetch_data()
df = generate_signals(df)
df = apply_sl_target(df)

if df.empty:
    st.warning("⚠ No data available for processing.")
else:
    # Charts
    st.subheader("📈 EMA Strategy Chart")
    st.line_chart(df[["Close", "EMA5", "EMA20"]])

    # Show Latest Signal
    last = df[df["Signal"].isin(["Buy", "Sell"])].tail(1)
    if not last.empty:
        st.success(f"💡 Last Signal: {last['Signal'].values[0]} on {last.index[-1].date()}")
        st.write(last[["Close", "EMA5", "EMA20", "Signal", "StopLoss", "Target"]])

    # Export to Excel
    st.subheader("📊 Export Signals to Excel")
    excel_data = convert_df_to_excel(df)
    if excel_data:
        st.download_button(label="Download Excel File", data=excel_data, file_name="nifty_signals.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
