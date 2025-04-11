from datetime import datetime, date, timedelta
import pandas as pd
from typing import Optional, Union, Dict, Any
import logging
import os
from functools import lru_cache # For caching the loaded DataFrame
import requests
import json
from dotenv import load_dotenv # Import the function

# --- Load environment variables from .env file ---
# This should be called early in your script execution
load_dotenv()


def format_currency(amount, currency="SGD"):
    """ Basic currency formatting (replace with locale-specific if needed). """
    # Placeholder - implement proper formatting
    return f"{currency} {amount:.2f}"

def get_date_range_for_day(target_date):
    """ Returns start and end timestamps for a given date. """
    if isinstance(target_date, datetime):
        target_date = target_date.date()
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    return start, end

# utils/holiday_checker.py  (or wherever you keep utility functions)
# Configure logging (use your project's logging setup if available)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# It's best to manage this path via a config file or environment variable
# Assumes the CSV is in a 'data' folder relative to the project root, adjust as needed
HOLIDAY_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'public_holidays.csv')
# --- OR --- use an absolute path if required
# HOLIDAY_CSV_PATH = '/path/to/your/data/public_holidays.csv'

@lru_cache(maxsize=1) # Cache the DataFrame after first load
def _load_holidays_df(filepath: str) -> Optional[pd.DataFrame]:
    """Loads the holiday CSV into a DataFrame, handling dates and types."""
    logging.info(f"Attempting to load holiday data from: {filepath}")
    try:
        df = pd.read_csv(
            filepath,
            dtype={'city_id': str}, # Read city_id as string for consistent matching
            parse_dates=['date'],   # Parse the 'date' column automatically
            infer_datetime_format=True # Can speed up parsing if format is consistent
        )
        # Convert date column to actual date objects (stripping time if any)
        df['date'] = df['date'].dt.date
        logging.info(f"Successfully loaded and processed holiday data. Shape: {df.shape}")
        return df
    except FileNotFoundError:
        logging.error(f"Holiday CSV file not found: {filepath}")
        return None
    except Exception as e:
        logging.error(f"Error loading or processing holiday CSV {filepath}: {e}", exc_info=True)
        return None

def get_public_holiday_name(
    target_city_id: Union[str, int],
    target_date: Union[str, date, datetime],
    holiday_file_path: str = HOLIDAY_CSV_PATH,
    city_id_col: str = 'city_id',
    date_col: str = 'date',
    name_col: str = 'holiday_name'
) -> Optional[str]:
    """
    Checks if a given date is a public holiday for a specific city_id
    based on data loaded from a CSV file.

    Args:
        target_city_id: The city ID to check for (should match CSV).
        target_date: The specific date to check (string, date, or datetime).
        holiday_file_path: Path to the public holidays CSV file.
        city_id_col: Column name for city ID in the CSV.
        date_col: Column name for the date in the CSV.
        name_col: Column name for the holiday name in the CSV.

    Returns:
        The name of the holiday (string) if found for the city_id and date.
        Returns None if no holiday is found or if an error occurs.
    """
    holidays_df = _load_holidays_df(holiday_file_path)

    if holidays_df is None or holidays_df.empty:
        logging.warning("Holiday DataFrame is not available or empty. Cannot check for holidays.")
        return None

    # --- Validate and Standardize Inputs ---
    try:
        target_city_id_str = str(target_city_id).strip() # Use string comparison

        # Convert target_date to a date object
        if isinstance(target_date, str):
            target_date_obj = pd.to_datetime(target_date).date()
        elif isinstance(target_date, datetime):
            target_date_obj = target_date.date()
        elif isinstance(target_date, date):
            target_date_obj = target_date
        else:
            logging.error(f"Invalid type for target_date: {type(target_date)}")
            return None
        logging.debug(f"Checking for holiday in city '{target_city_id_str}' on {target_date_obj}")

    except Exception as e:
        logging.error(f"Error parsing target date '{target_date}': {e}")
        return None

    # --- Check for Column Existence ---
    required_cols = {city_id_col, date_col, name_col}
    if not required_cols.issubset(holidays_df.columns):
         missing = required_cols - set(holidays_df.columns)
         logging.error(f"Holiday CSV is missing required columns: {missing}")
         return None

    # --- Find Match ---
    try:
        match = holidays_df[
            (holidays_df[city_id_col] == target_city_id_str) &
            (holidays_df[date_col] == target_date_obj)
        ]

        if len(match) == 1:
            holiday_name = match.iloc[0][name_col]
            logging.info(f"Found holiday: {holiday_name} for city {target_city_id_str} on {target_date_obj}")
            return str(holiday_name).strip()
        elif len(match) > 1:
            # Should ideally not happen if CSV is clean, but handle it
            holiday_name = match.iloc[0][name_col]
            logging.warning(f"Multiple holidays found for city {target_city_id_str} on {target_date_obj}. Returning first: {holiday_name}")
            return str(holiday_name).strip()
        else:
            # No holiday found for this specific city/date combination
            logging.debug(f"No public holiday found for city {target_city_id_str} on {target_date_obj}.")
            return None

    except Exception as e:
        logging.error(f"Error during holiday lookup: {e}", exc_info=True)
        return None


"""
=================================================================================================================================
CSV FILE FORMAT:

city_id,country,date,holiday_name
1,Singapore,2024-01-01,New Year's Day
1,Singapore,2024-02-10,Chinese New Year
1,Singapore,2024-02-11,Chinese New Year Holiday
1,Singapore,2024-03-29,Good Friday
1,Singapore,2024-04-10,Hari Raya Puasa

Example Case:

# Test cases
city_1 = "1"
city_2 = 2 # Test with integer input
date_holiday_sg = date(2024, 8, 9)
date_holiday_my = "2024-08-31"
date_no_holiday = "2024-08-10"
date_other_year = datetime(2025, 1, 1, 10, 30) # Test datetime input

# Test 1: Holiday found for city 1
holiday = get_public_holiday_name(city_1, date_holiday_sg, holiday_file_path=DUMMY_CSV_PATH)
print(f"City {city_1} on {date_holiday_sg}: Holiday = {holiday}") # Expected: National Day
================================================================================================================================
"""

# --- Constants ---
WEATHERAPI_BASE_URL = "http://api.weatherapi.com/v1"
WEATHERAPI_CURRENT_ENDPOINT = "/current.json"

def get_current_weather_weatherapi(
    location: str,
    api_key: Optional[str] = None,
    include_aqi: bool = False  # WeatherAPI can include Air Quality Index
) -> Optional[Dict[str, Any]]:
    """
    Fetches the current weather for a specified location using the WeatherAPI.com API.

    Args:
        location: The location query (e.g., "London", "Paris, FR", "90210",
                  "latitude,longitude").
        api_key: Your WeatherAPI.com API key. If None, attempts to read from
                 the 'WEATHERAPI_API_KEY' environment variable.
        include_aqi: Whether to request Air Quality Index data (default: False).

    Returns:
        A dictionary containing key weather information (temp C/F, condition,
        humidity, wind kph/mph, etc.) if successful.
        Returns None if the API key is missing, the location is not found,
        or another API error occurs.
    """
    if api_key is None:
        # Use a distinct environment variable name for this specific API
        api_key = os.getenv("WEATHERAPI_API_KEY")

    if not api_key:
        logging.error("WeatherAPI.com API key not provided and not found in environment variable WEATHERAPI_API_KEY.")
        return None

    # --- Prepare API Request ---
    url = f"{WEATHERAPI_BASE_URL}{WEATHERAPI_CURRENT_ENDPOINT}"
    params = {
        'key': api_key,
        'q': location,
        'aqi': 'yes' if include_aqi else 'no'
    }

    # --- Make API Call ---
    try:
        logging.info(f"Requesting weather from WeatherAPI.com for '{location}' (AQI: {'Yes' if include_aqi else 'No'})")
        response = requests.get(url, params=params, timeout=10) # 10-second timeout

        # Check for HTTP errors (WeatherAPI uses standard codes)
        # 400 can mean location not found or bad query
        # 401 means invalid API key
        # 403 means API key disabled or exceeded quota
        response.raise_for_status()

        # --- Parse Response ---
        data = response.json()
        logging.debug(f"Raw WeatherAPI.com response: {json.dumps(data, indent=2)}")

        # --- Extract Relevant Information (Safely access nested data) ---
        location_data = data.get("location", {})
        current_data = data.get("current", {})
        condition_data = current_data.get("condition", {})
        aqi_data = current_data.get("air_quality", {}) # Will be empty if include_aqi=False

        # Basic validation: Check if essential 'current' data is present
        if not current_data or not condition_data or current_data.get('temp_c') is None:
            logging.warning(f"Essential current weather data missing in response for '{location}'.")
            return None

        # --- Format Output Dictionary for the AI Agent ---
        weather_info = {
            "location_requested": location,
            "location_name": location_data.get("name"),
            "region": location_data.get("region"),
            "country": location_data.get("country"),
            "latitude": location_data.get("lat"),
            "longitude": location_data.get("lon"),
            "localtime": location_data.get("localtime"), # Local time at location
            "last_updated": current_data.get("last_updated"), # Time of observation

            "temperature_c": current_data.get("temp_c"),
            "temperature_f": current_data.get("temp_f"),
            "is_day": bool(current_data.get("is_day", 1)), # 1 for day, 0 for night
            "condition_text": condition_data.get("text"),
            "condition_icon": condition_data.get("icon"), # URL to weather icon
            "condition_code": condition_data.get("code"), # Weather condition code

            "wind_kph": current_data.get("wind_kph"),
            "wind_mph": current_data.get("wind_mph"),
            "wind_degree": current_data.get("wind_degree"),
            "wind_direction": current_data.get("wind_dir"),

            "pressure_mb": current_data.get("pressure_mb"), # Millibars
            "pressure_in": current_data.get("pressure_in"), # Inches
            "precip_mm": current_data.get("precip_mm"), # Precipitation mm
            "precip_in": current_data.get("precip_in"), # Precipitation inches
            "humidity": current_data.get("humidity"), # Percentage
            "cloud_cover": current_data.get("cloud"), # Percentage
            "feelslike_c": current_data.get("feelslike_c"),
            "feelslike_f": current_data.get("feelslike_f"),
            "visibility_km": current_data.get("vis_km"),
            "visibility_miles": current_data.get("vis_miles"),
            "uv_index": current_data.get("uv"),
            "gust_kph": current_data.get("gust_kph"),
            "gust_mph": current_data.get("gust_mph"),
        }

        # Add AQI data if requested and available
        if include_aqi and aqi_data:
            weather_info["air_quality"] = {
                "co": aqi_data.get("co"), # Carbon Monoxide
                "o3": aqi_data.get("o3"), # Ozone
                "no2": aqi_data.get("no2"), # Nitrogen dioxide
                "so2": aqi_data.get("so2"), # Sulphur dioxide
                "pm2_5": aqi_data.get("pm2_5"), # Particulate matter < 2.5 microns
                "pm10": aqi_data.get("pm10"), # Particulate matter < 10 microns
                "us-epa-index": aqi_data.get("us-epa-index"), # US EPA standard AQI index
                "gb-defra-index": aqi_data.get("gb-defra-index") # UK DEFRA Index
            }

        found_location_name = f"{location_data.get('name', 'Unknown')}, {location_data.get('country', 'Unknown')}"
        logging.info(f"Successfully retrieved weather via WeatherAPI.com for '{found_location_name}'")
        return weather_info

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        try: # Try to get error message from API response
            error_info = http_err.response.json().get("error", {})
            error_message = error_info.get("message", str(http_err))
        except: # Fallback if response isn't JSON or format is unexpected
             error_message = str(http_err)

        if status_code == 401:
            logging.error(f"WeatherAPI.com Error: Invalid API key. Please check WEATHERAPI_API_KEY. (Message: {error_message})")
        elif status_code == 400:
             logging.error(f"WeatherAPI.com Error: Bad Request. Location '{location}' likely not found or invalid query. (Message: {error_message})")
        elif status_code == 403:
             logging.error(f"WeatherAPI.com Error: API key disabled or quota exceeded. (Message: {error_message})")
        else:
            logging.error(f"WeatherAPI.com HTTP Error ({status_code}): {error_message}")
        return None
    except requests.exceptions.Timeout:
        logging.error(f"WeatherAPI.com request timed out for location '{location}'.")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"WeatherAPI.com Request Failed: {req_err}")
        return None
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON response from WeatherAPI.com.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred fetching weather from WeatherAPI.com: {e}", exc_info=True)
        return None
    
"""
API KEY WILL BE SENT TO THE GROUP. PLS CONTACT THE BACKEND FOR API KEY

"""
# Add other reusable helper functions (e.g., date comparisons)