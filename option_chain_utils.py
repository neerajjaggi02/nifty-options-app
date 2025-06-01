import requests
import pandas as pd

def get_nifty_option_chain():
    """
    Fetches Nifty 50 option chain data from NSE India website.
    Note: The NSE India website's API is dynamic and may change.
    This function attempts to mimic a browser request to fetch the data.
    """
    # This URL is an example and might change or require specific parameters.
    # You might need to inspect network requests on the NSE India website for the exact API endpoint.
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY" 
    
    # Headers to mimic a browser request to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        session = requests.Session()
        # It's often necessary to first hit a main page to get cookies/session data
        # before accessing the API endpoint. This helps avoid 403 Forbidden errors.
        session.get("https://www.nseindia.com/market-data/option-chain", headers=headers, timeout=10) 
        response = session.get(url, headers=headers, timeout=10) # Add timeout for robustness
        
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx status codes)

        # Check if the response content is empty before trying to parse JSON
        if not response.text.strip():
            print("Warning: Empty response received from option chain API. The API might be down or returned no data.")
            return pd.DataFrame() # Return empty DataFrame if response is empty

        data = response.json()

        # Assuming the structure is like {'records': {'data': [...]}}
        # You might need to adjust this parsing logic based on the actual NSE API response structure.
        if 'records' in data and 'data' in data['records']:
            options_data = data['records']['data']
            
            processed_data = []
            for item in options_data:
                # Extract relevant fields for Call Options (CE)
                if 'CE' in item and isinstance(item['CE'], dict): 
                    processed_data.append({
                        'strikePrice': item.get('strikePrice'),
                        'expiryDate': item.get('expiryDate'),
                        'openInterest': item['CE'].get('openInterest'), # Using 'openInterest' for filtering in app.py
                        'changeInOpenInterest': item['CE'].get('changeInOpenInterest'),
                        'impliedVolatility': item['CE'].get('impliedVolatility'),
                        'lastPrice': item['CE'].get('lastPrice'),
                        'bidQty': item['CE'].get('bidQty'),
                        'bidPrice': item['CE'].get('bidprice'),
                        'askPrice': item['CE'].get('askPrice'),
                        'askQty': item['CE'].get('askQty'),
                        'volume': item['CE'].get('totalTradedVolume'),
                        'optionType': 'CE' # Explicitly stating option type
                    })
                # Extract relevant fields for Put Options (PE)
                if 'PE' in item and isinstance(item['PE'], dict):
                    processed_data.append({
                        'strikePrice': item.get('strikePrice'),
                        'expiryDate': item.get('expiryDate'),
                        'openInterest': item['PE'].get('openInterest'), # Using 'openInterest' for filtering in app.py
                        'changeInOpenInterest': item['PE'].get('changeInOpenInterest'),
                        'impliedVolatility': item['PE'].get('impliedVolatility'),
                        'lastPrice': item['PE'].get('lastPrice'),
                        'bidQty': item['PE'].get('bidQty'),
                        'bidPrice': item['PE'].get('bidprice'),
                        'askPrice': item['PE'].get('askPrice'),
                        'askQty': item['PE'].get('askQty'),
                        'volume': item['PE'].get('totalTradedVolume'),
                        'optionType': 'PE' # Explicitly stating option type
                    })
            df = pd.DataFrame(processed_data)
        else:
            print("Warning: Unexpected JSON structure for option chain data. 'records' or 'data' key missing.")
            df = pd.DataFrame() # Return empty DataFrame if structure is unexpected

        return df

    except requests.exceptions.HTTPError as errh:
        print(f"HTTP Error occurred while fetching option chain: {errh}")
        return pd.DataFrame()
    except requests.exceptions.ConnectionError as errc:
        print(f"Connection Error occurred while fetching option chain: {errc}")
        return pd.DataFrame()
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error occurred while fetching option chain: {errt}")
        return pd.DataFrame()
    except requests.exceptions.JSONDecodeError as json_e:
        print(f"JSON Decode Error occurred while fetching option chain: {json_e}. Response content might not be valid JSON.")
        # Optionally print response.text here for debugging: print(response.text)
        return pd.DataFrame()
    except requests.exceptions.RequestException as err:
        print(f"An unknown Requests error occurred while fetching option chain: {err}")
        return pd.DataFrame()
    except Exception as e:
        print(f"An unexpected error occurred in get_nifty_option_chain: {e}")
        return pd.DataFrame()

