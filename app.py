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
    df = yf.download("^NSEI", period="3mo", interval="1d")
    df.dropna(inplace=True)
    df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    return df

def generate_signals(df):
    df["Signal"] = ""
    df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
    df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    return df

def apply_sl_target(df):
    stop_losses = []
    targets = []

    for _, row in df.iterrows():
        signal = str(row["Signal"]) if pd.notna(row["Signal"]) else ""
        entry = row["Close"]

        if signal == "Buy":
            stop_losses.append(entry * (1 - STOP_LOSS_PCT))
            targets.append(entry * (1 + TARGET_PCT))
        elif signal == "Sell":
            stop_losses.append(entry * (1 + STOP_LOSS_PCT))
            targets.append(entry * (1 - TARGET_PCT))
        else:
            stop_losses.append(None)
            targets.append(None)

    df["StopLoss"] = stop_losses
    df["Target"] = targets
    return df

def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True, sheet_name='Signals')
        writer.save()
    return output.getvalue()

# Load & Process Data
df = fetch_data()
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

# Export to Excel
st.subh
