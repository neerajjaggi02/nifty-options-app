import streamlit as st
import pandas as pd
import yfinance as yf
from option_chain_utils import get_nifty_option_chain
from io import BytesIO
import requests # Import requests to catch specific exceptions in option chain part

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
            
        # Initial dropna to remove rows with any missing values across all columns
        df.dropna(inplace=True) 
        
        # Check if all rows were dropped after initial dropna()
        if df.empty:
            st.warning("⚠️ All rows were dropped after initial `dropna()`. This might indicate significant missing data.")
            return pd.DataFrame()

        # Ensure 'Close' column has numeric data type before EMA calculation
        # 'errors='coerce'' will turn non-numeric values into NaN
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        # Drop rows where 'Close' became NaN after conversion, as they cannot be used for EMA
        df.dropna(subset=['Close'], inplace=True) 

        # --- CRITICAL CHECKS BEFORE EMA CALCULATION ---
        # Ensure 'Close' column is not empty, is numeric, and has enough non-NaN values
        if df['Close'].empty or not pd.api.types.is_numeric_dtype(df['Close']) or df['Close'].count() == 0:
            st.error("❌ 'Close' column is empty or not numeric after all cleaning, or contains no valid data. Cannot calculate EMAs.")
            return pd.DataFrame() # Return empty DataFrame if 'Close' is invalid

        # Check if there's enough data points for EMA calculation (EMA20 requires at least 20 data points)
        # This check is now placed after ensuring 'Close' is valid and non-empty
        if len(df) < 20: 
            st.warning(f"⚠️ Insufficient data points ({len(df)} rows) to calculate EMA20. At least 20 rows of valid 'Close' data are needed.")
            return pd.DataFrame() # Return empty if not enough data

        # Calculate Exponential Moving Averages (EMA)
        df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()

        # Explicitly check if EMA columns were created successfully
        if 'EMA5' not in df.columns or 'EMA20' not in df.columns:
            st.error("❌ EMA5 or EMA20 columns could not be created. This is unexpected, please review data processing logic.")
            return pd.DataFrame()
        
        return df
    except Exception as e:
        # Catch any errors during data fetching or initial processing and display a message
        st.error(f"❌ Error fetching or processing Nifty data: {e}. Please ensure '^NSEI' is a valid ticker and you have an internet connection.")
        return pd.DataFrame()

def generate_signals(df):
    """
    Generates 'Buy' or 'Sell' signals based on EMA crossover strategy.
    """
    df["Signal"] = "" # Initialize 'Signal' column
    # Ensure EMA5 and EMA20 exist before generating signals
    if "EMA5" in df.columns and "EMA20" in df.columns:
        # Generate Buy signal: EMA5 crosses above EMA20
        df.loc[(df["EMA5"] > df["EMA20"]) & (df["EMA5"].shift(1) <= df["EMA20"].shift(1)), "Signal"] = "Buy"
        # Generate Sell signal: EMA5 crosses below EMA20
        df.loc[(df["EMA5"] < df["EMA20"]) & (df["EMA5"].shift(1) >= df["EMA20"].shift(1)), "Signal"] = "Sell"
    else:
        st.warning("⚠️ EMA columns not found for signal generation. Signals will not be generated.")
    return df

def apply_sl_target(df):
    """
    Applies Stop Loss (SL) and Target Price based on signals.
    """
    # Ensure 'Close' column exists before setting 'Entry'
    if 'Close' in df.columns and pd.api.types.is_numeric_dtype(df['Close']):
        df["Entry"] = df["Close"] # Entry price is the closing price
    else:
        df["Entry"] = None # Set to None if 'Close' is missing or not numeric
        st.warning("⚠️ 'Close' column not found or not numeric for calculating Entry price. SL/Target will be None.")
        
    # Calculate Stop Loss
    df["StopLoss"] = df.apply(
        lambda row: row["Entry"] * (1 - STOP_LOSS_PCT) if str(row.get("Signal", "")) == "Buy" and row["Entry"] is not None
        else row["Entry"] * (1 + STOP_LOSS_PCT) if str(row.get("Signal", "")) == "Sell" and row["Entry"] is not None
        else None,
        axis=1
    )
    
    # Calculate Target Price
    df["Target"] = df.apply(
        lambda row: row["Entry"] * (1 + TARGET_PCT) if str(row.get("Signal", "")) == "Buy" and row["Entry"] is not None
        else row["Entry"] * (1 - TARGET_PCT) if str(row.get("Signal", "")) == "Sell" and row["Entry"] is not None
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
    chart_columns_to_plot = ["Close", "EMA5", "EMA20"]
    # Filter out any columns that might be missing from the list (for extra robustness)
    actual_chart_columns = [col for col in chart_columns_to_plot if col in df.columns]

    if actual_chart_columns: # Check if there are any columns left to plot
        st.line_chart(df[actual_chart_columns])
    else:
        st.warning("⚠️ Cannot plot EMA Strategy Chart: Required columns (Close, EMA5, EMA20) are missing from the data after processing.")


    # Show Latest Signal
    # Filter for rows where a Buy or Sell signal was generated
    last = df[df["Signal"].isin(["Buy", "Sell"])].tail(1)
    if not last.empty:
        # Define columns to display for the last signal, ensuring they exist
        signal_display_columns = ["Close", "EMA5", "EMA20", "Signal", "StopLoss", "Target"]
        actual_signal_display_columns = [col for col in signal_display_columns if col in last.columns]
        
        st.success(f"💡 Last Signal: {last['Signal'].values[0]} on {last.index[-1].date()}")
        if actual_signal_display_columns:
            st.write(last[actual_signal_display_columns])
        else:
            st.info("Details for the last signal could not be displayed due to missing columns.")
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
        # Ensure 'openInterest' column exists before filtering
        if 'openInterest' in oc.columns:
            # Convert 'openInterest' to numeric, coercing errors to NaN, then drop NaNs
            oc['openInterest'] = pd.to_numeric(oc['openInterest'], errors='coerce')
            oc.dropna(subset=['openInterest'], inplace=True)
            
            if not oc.empty:
                st.dataframe(oc[oc["openInterest"] > 100000].head(20))
            else:
                st.info("Option chain data loaded, but no entries meet the 'OI > 100K' criteria after cleaning.")
        else:
            st.info("Option chain data loaded, but 'openInterest' column is missing for filtering.")
            st.dataframe(oc.head(20)) # Display raw top 20 without filtering
    else:
        st.info("No option chain data available or conditions not met (e.g., empty data from API).")
except requests.exceptions.JSONDecodeError as json_e:
    st.error(f"❌ Failed to load option chain: The response was not valid JSON. This usually indicates an issue with the data source or network, or that the API endpoint has changed.")
    st.exception(json_e)
except Exception as e:
    # Catch and display any other errors during option chain loading
    st.error(f"❌ An unexpected error occurred while loading option chain: {e}")
    st.exception(e) # Show the full exception details for debugging
