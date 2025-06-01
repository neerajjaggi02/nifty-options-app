def apply_ema_strategy(df):
    df["EMA5"] = df["Close"].ewm(span=5).mean()
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["Signal"] = 0
    df.loc[df["EMA5"] > df["EMA20"], "Signal"] = 1
    df.loc[df["EMA5"] < df["EMA20"], "Signal"] = -1
    df["Trade"] = df["Signal"].diff()
    return df
