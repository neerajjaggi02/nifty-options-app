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
    def calc_sl_target(row):
        signal = row["Signal"]
        entry = row["Close"]  # Use Close price for entry
        if signal == "Buy":
            return entry * (1 - STOP_LOSS_PCT), entry * (1 + TARGET_PCT)
        elif signal == "Sell":
            return entry * (1 + STOP_LOSS_PCT), entry * (1 - TARGET_PCT)
        else:
            return None, None

    sl_target = df.apply(calc_sl_target, axis=1)
    df["StopLoss"] = sl_target.apply(lambda x: x[0])
    df["Target"] = sl_target.apply(lambda x: x[1])
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
st.subheader("📥 Export Signals to Excel")
signal_df = df[df["Signal"].isin(["Buy", "Sell"])]
if not signal_df.empty:
    excel_data = convert_df_to_excel(signal_df)
    st.download_button("📤 Download Signals", excel_data, file_name="nifty_signals.xlsx")
else:
    st.info("No signals to export.")

# Option Chain
st.subheader("📄 Option Chain Data (OI > 100K)")
try:
    oc = get_nifty_option_chain()
    st.dataframe(oc[oc["openInterest"] > 100000].head(20))
except Exception as e:
    st.error("❌ Failed to load option chain")
    st.exception(e)
