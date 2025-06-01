# option_chain_utils.py

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

    # Step 1: Hit NSE home page to set cookies
    session.get("https://www.nseindia.com", timeout=5)

    # Step 2: Call the option chain endpoint
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
            ce["strikePrice"] = strike
            df_ce.append(ce)

        if pe:
            pe["type"] = "PE"
            pe["strikePrice"] = strike
            df_pe.append(pe)

    df = pd.DataFra
