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
    """
    Fetches historical Nifty 50 data from Yahoo Finance,
    calculates EMA5 and EMA20, and handles potential data issues.
    """
    try:
        df = yf.download("^NSEI", period="3mo", interval="1d")
        
        # Check if any data was downloaded
        if df.empty:
            st.error("❌ No data downloaded from Yahoo Finance. Please check the ticker symbol or your internet connection.")
            return pd.DataFrame() # Return an empty DataFrame
        
        # Ensure 'Close' column exists before proceeding
        if 'Close' not in df.columns:
            st.error("❌ 'Close' column not found in the downloaded data. Data might be incomplete or malformed.")
            return pd.DataFrame()
            
        df.dropna(inplace=True) # Remove rows with any missing values
        
        # Check if all rows were dropped after dropna()
        if df.empty:
            st.warning("⚠️ All rows were dropped after `dropna()`. This might indicate significant missing data.")
            return pd.DataFrame()

        # Calculate Exponential Moving Averages (EMA)
        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        
        return df
    except Exception as e:
        # Catch any errors during data fetching and display a message
        st.error(f"❌ Error fetching data: {e}. Please ensure '^NSEI' is a valid ticker and you have an internet connection.")
        return pd.DataFrame()

def generate_signals(df):
    """
    Generates 'Buy' or 'Sell' signals based on EMA crossover strategy.
    """
    df["Signal"] = "" # Initialize 'Signal' column
    # Generate Buy signal: EMA5 crosses above EMA20
    df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
    # Generate Sell signal: EMA5 crosses below EMA20
    df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    return df

def apply_sl_target(df):
    """
    Applies Stop Loss (SL) and Target Price based on signals.
    """
    df["Entry"] = df["Close"] # Entry price is the closing price
    
    # Calculate Stop Loss
    df["StopLoss"] = df.apply(
        lambda row: row["Entry"] * (1 - STOP_LOSS_PCT) if str(row.get("Signal", "")) == "Buy" 
        else row["Entry"] * (1 + STOP_LOSS_PCT) if str(row.get("Signal", "")) == "Sell" 
        else None,
        axis=1
    )
    
    # Calculate Target Price
    df["Target"] = df.apply(
        lambda row: row["Entry"] * (1 + TARGET_PCT) if str(row.get("Signal", "")) == "Buy" 
        else row["Entry"] * (1 - TARGET_PCT) if str(row.get("Signal", "")) == "Sell" 
        else None,
        axis=1
    )
    return df

def convert_df_to_excel(df):
    """
    Converts a Pandas DataFrame to an Excel file in BytesIO format.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True, sheet_name='Signals')
    return output.getvalue()

# --- Main Application Logic ---

# Load & Process Data
df = fetch_data()

# Only proceed with charting and signal generation if DataFrame is not empty
# and has all required columns for plotting and calculations.
if not df.empty and all(col in df.columns for col in ["Close", "EMA5", "EMA20"]):
    df = generate_signals(df)
    df = apply_sl_target(df)

    # Charts
    st.subheader("📈 EMA Strategy Chart")
    # Define the columns expected for the chart
    chart_columns_to_check = ["Close", "EMA5", "EMA20"]
    # Filter out any columns that might be missing from the list
    actual_chart_columns = [col for col in chart_columns_to_check if col in df.columns]

    if actual_chart_columns: # Check if there are any columns left to plot
        st.line_chart(df[actual_chart_columns])
    else:
        st.warning("⚠️ Cannot plot EMA Strategy Chart: Required columns (Close, EMA5, EMA20) are missing from the data after processing.")


    # Show Latest Signal
    # Filter for rows where a Buy or Sell signal was generated
    last = df[df["Signal"].isin(["Buy", "Sell"])].tail(1)
    if not last.empty:
        # Display the last signal and its details
        st.success(f"💡 Last Signal: {last['Signal'].values[0]} on {last.index[-1].date()}")
        st.write(last[["Close", "EMA5", "EMA20", "Signal", "StopLoss", "Target"]])
    else:
        st.info("No buy/sell signals generated yet based on the current data and strategy.")

    # Export to Excel
    st.subheader("📥 Export Signals to Excel")
    # Filter DataFrame to include only rows with signals
    signal_df = df[df["Signal"].isin(["Buy", "Sell"])]
    if not signal_df.empty:
        excel_data = convert_df_to_excel(signal_df)
        st.download_button(
            label="📤 Download Signals", 
            data=excel_data, 
            file_name="nifty_signals.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No signals to export.")
else:
    # Display an error if data fetching or initial processing failed
    st.error("📉 Could not generate charts or signals due to data issues. Please check the error messages above.")

# --- Option Chain Section ---
st.subheader("📄 Option Chain Data (OI > 100K)")
try:
    # Attempt to fetch Nifty option chain data
    oc = get_nifty_option_chain()
    if not oc.empty:
        # Display top 20 rows where Open Interest (OI) is greater than 100,000
        st.dataframe(oc[oc["openInterest"] > 100000].head(20))
    else:
        st.info("No option chain data available or conditions not met (e.g., no OI > 100K).")
except Exception as e:
    # Catch and display any errors during option chain loading
    st.error("❌ Failed to load option chain")
    st.exception(e) # Show the full exception details for debugging
