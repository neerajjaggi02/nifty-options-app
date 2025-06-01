### File: app.py

import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from option_chain_utils import get_nifty_option_chain
from strategies import apply_ema_strategy

st.set_page_config(page_title="Nifty 50 Options Trade Helper", layout="wide")
st.title(u"\U0001F4CA Nifty 50 Options Trade Entry/Exit Signal App")

# Date range for historical data
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=30)

# Fetch historical Nifty spot data
nifty = yf.download("^NSEI", start=start_date, end=end_date, interval='15m')

if not nifty.empty:
    df = nifty.copy()
    df = apply_ema_strategy(df)

    # Display chart
    st.subheader(u"\U0001F4CA Nifty Spot Data with EMA Strategy")
    st.line_chart(df[["Close", "EMA5", "EMA20"]])

    # Identify trade signals
    signals = df[df["Trade"].isin([1, -1])][["Close", "Trade"]]
    signals["Action"] = signals["Trade"].apply(lambda x: "BUY CALL" if x == 1 else "BUY PUT")

    st.subheader(u"\U0001F4CA Trade Signals")
    st.dataframe(signals.tail(10))

    latest_signal = signals.iloc[-1]["Action"] if not signals.empty else "No Signal"
    st.markdown(f"### \u2705 Latest Signal: `{latest_signal}`")

    # --- Option Chain Integration ---
    option_chain = get_nifty_option_chain()
    spot_price = df["Close"].iloc[-1]
    atm_strike = round(spot_price / 50) * 50

    atm_options = option_chain[option_chain["strikePrice"] == atm_strike]

    # Fetch CE/PE based on signal
    if latest_signal == "BUY CALL":
        option_row = atm_options[atm_options["type"] == "CE"]
    elif latest_signal == "BUY PUT":
        option_row = atm_options[atm_options["type"] == "PE"]
    else:
        option_row = pd.DataFrame()

    if not option_row.empty:
        entry_price = option_row.iloc[0]["lastPrice"]
        sl = round(entry_price * 0.75, 2)
        target = round(entry_price * 1.5, 2)

        st.subheader("u"\U0001F4CA Suggested Option Trade")
        st.write(f"**Strike Price:** {atm_strike} | **Type:** {latest_signal.split()[-1]}")
        st.write(f"**Entry Price:** ₹{entry_price}")
        st.write(f"**Stop Loss:** ₹{sl}")
        st.write(f"**Target:** ₹{target}")
    else:
        st.info("No matching ATM option found.")
else:
    st.error("Failed to fetch Nifty data. Try again later.")


### File: strategies.py

def apply_ema_strategy(df):
    df["EMA5"] = df["Close"].ewm(span=5).mean()
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["Signal"] = 0
    df.loc[df["EMA5"] > df["EMA20"], "Signal"] = 1
    df.loc[df["EMA5"] < df["EMA20"], "Signal"] = -1
    df["Trade"] = df["Signal"].diff()
    return df


### File: option_chain_utils.py

import requests
import pandas as pd

def get_nifty_option_chain():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    session = requests.Session()
    session.headers.update(headers)

    # Required to get cookies first
    session.get("https://www.nseindia.com", timeout=5)
    response = session.get(url, timeout=10)
    data = response.json()

    records = data["records"]["data"]
    df_ce = []
    df_pe = []

    for record in records:
        strike = record.get("strikePrice")
        ce = record.get("CE")
        pe = record.get("PE")
        if ce:
            ce["type"] = "CE"
            df_ce.append(ce)
        if pe:
            pe["type"] = "PE"
            df_pe.append(pe)

    df = pd.DataFrame(df_ce + df_pe)
    df = df[["strikePrice", "type", "lastPrice", "change", "openInterest", "impliedVolatility"]]
    return df


### File: requirements.txt

streamlit
yfinance
pandas
requests
