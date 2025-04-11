import pandas as pd
import random
import os 
from datetime import datetime, timedelta, timezone, date
import numpy as np # Needed for pd.NaT
from pathlib import Path # Import Path
from typing import List, Dict, Union
import sys
import math

# --- Determine the script's directory ---
# This ensures files are saved *inside* the mock_data folder,
# regardless of where you run the script from.
SCRIPT_DIR = Path(__file__).parent

# --- Configuration ---
# Files will be saved in the same directory as the script
MERCHANT_FILENAME = Path("mock_data\merchant.csv")
ITEMS_FILENAME = Path("mock_data\items.csv")
INVENTORY_FILENAME = Path("mock_data\inventory.csv")
TRANSACTION_DATA_FILENAME = Path("mock_data\\transaction_data.csv")
TRANSACTION_ITEMS_FILENAME = Path("mock_data\\transaction_items.csv")
HOLIDAY_FILENAME = Path("mock_data\\holidays.csv") # *** New Filename ***

NUM_MERCHANTS = 5 # Used ONLY if merchant.csv doesn't exist
NUM_PRODUCTS_PER_MERCHANT = 10
NUM_DAYS_OF_ORDERS = 14
ORDERS_PER_DAY_RANGE = (30, 80)
ITEMS_PER_ORDER_RANGE = (1, 4)
QUANTITY_PER_ITEM_RANGE = (1, 3)
START_ORDER_ID = 5000

# --- Master Lists ---
MERCHANT_TYPES = ["Hawker Stall", "Restaurant", "Cafe", "Home-Based", "Cloud Kitchen"]
CUISINE_TYPES = ["Malay", "Chinese", "Indian", "Western", "Thai", "Japanese", "Healthy", "Mixed"]
LOCATION_ZONES = ["Central", "East", "West", "North", "Northeast"] # Geographic zone within a city
MERCHANT_SIZES = ["Small", "Medium", "Large"]

CITY_MAP = {
    1: "Singapore",
    2: "Kuala Lumpur", # Malaysia
    3: "Jakarta",      # Indonesia
    4: "Manila",       # Philippines
    5: "Naypyidaw",    # Myanmar
    6: "Vientiane",    # Laos
    7: "Phnom Penh",   # Cambodia
    8: "Bandar Seri Begawan" # Brunei
}
VALID_CITY_IDS = list(CITY_MAP.keys())

PRODUCT_CATEGORIES = ["Main Course", "Beverage", "Dessert", "Side Dish", "Snack"]
ACCEPTANCE_STATUS_OPTIONS = ["Accepted", "Accepted", "Accepted", "Accepted", "Missed"]
ORDER_TYPES = ["Delivery", "Self Pick-up"]
ISSUE_REPORTED_OPTIONS = ["None"]

# --- Time/Date Configuration ---
NOW_UTC = date(2023, 12, 31)
TODAY_DATE = date(2023, 12, 31)
# Use a specific year for consistent holiday dates in mock data
HOLIDAY_YEAR = 2023 # Or 2023 if preferred
ORDER_PEAK_HOURS = [11, 12, 13, 18, 19, 20]
ORDER_OFFPEAK_HOURS = list(range(9, 22))
ORDER_HOURS_DISTRIBUTION = ORDER_PEAK_HOURS * 3 + ORDER_OFFPEAK_HOURS
PREP_TIME_RANGE_MIN = (5, 25)
QUANTITY_RANGE = (1, 3)
M1002_RECENT_PREP_TIME_RANGE = (15, 35)

# --- Holiday Data ---
# Note: Dates for variable holidays are approximate examples for HOLIDAY_YEAR
# Actual dates vary. Add more or adjust as needed.
HOLIDAY_DATA = [
    # Singapore (City ID: 1)
    {"city_id": 1, "holiday_date": f"{HOLIDAY_YEAR}-01-01", "holiday_name": "New Year's Day"},
    {"city_id": 1, "holiday_date": f"{HOLIDAY_YEAR}-02-10", "holiday_name": "Chinese New Year (Day 1)"}, # Example date
    {"city_id": 1, "holiday_date": f"{HOLIDAY_YEAR}-05-01", "holiday_name": "Labour Day"},
    {"city_id": 1, "holiday_date": f"{HOLIDAY_YEAR}-08-09", "holiday_name": "National Day"},
    {"city_id": 1, "holiday_date": f"{HOLIDAY_YEAR}-12-25", "holiday_name": "Christmas Day"},
    # Malaysia (City ID: 2)
    {"city_id": 2, "holiday_date": f"{HOLIDAY_YEAR}-02-10", "holiday_name": "Chinese New Year (Day 1)"}, # Example date
    {"city_id": 2, "holiday_date": f"{HOLIDAY_YEAR}-04-10", "holiday_name": "Hari Raya Aidilfitri (Day 1)"}, # Example date
    {"city_id": 2, "holiday_date": f"{HOLIDAY_YEAR}-05-01", "holiday_name": "Labour Day"},
    {"city_id": 2, "holiday_date": f"{HOLIDAY_YEAR}-08-31", "holiday_name": "Merdeka Day (National Day)"},
    {"city_id": 2, "holiday_date": f"{HOLIDAY_YEAR}-09-16", "holiday_name": "Malaysia Day"},
    # Indonesia (City ID: 3)
    {"city_id": 3, "holiday_date": f"{HOLIDAY_YEAR}-01-01", "holiday_name": "New Year's Day"},
    {"city_id": 3, "holiday_date": f"{HOLIDAY_YEAR}-04-10", "holiday_name": "Idul Fitri (Day 1)"}, # Example date
    {"city_id": 3, "holiday_date": f"{HOLIDAY_YEAR}-06-01", "holiday_name": "Pancasila Day"},
    {"city_id": 3, "holiday_date": f"{HOLIDAY_YEAR}-08-17", "holiday_name": "Independence Day"},
    {"city_id": 3, "holiday_date": f"{HOLIDAY_YEAR}-12-25", "holiday_name": "Christmas Day"},
    # Philippines (City ID: 4)
    {"city_id": 4, "holiday_date": f"{HOLIDAY_YEAR}-01-01", "holiday_name": "New Year's Day"},
    {"city_id": 4, "holiday_date": f"{HOLIDAY_YEAR}-03-29", "holiday_name": "Good Friday"}, # Example date
    {"city_id": 4, "holiday_date": f"{HOLIDAY_YEAR}-05-01", "holiday_name": "Labor Day"},
    {"city_id": 4, "holiday_date": f"{HOLIDAY_YEAR}-06-12", "holiday_name": "Independence Day"},
    {"city_id": 4, "holiday_date": f"{HOLIDAY_YEAR}-12-25", "holiday_name": "Christmas Day"},
    # Myanmar (City ID: 5)
    {"city_id": 5, "holiday_date": f"{HOLIDAY_YEAR}-01-04", "holiday_name": "Independence Day"},
    {"city_id": 5, "holiday_date": f"{HOLIDAY_YEAR}-02-12", "holiday_name": "Union Day"},
    {"city_id": 5, "holiday_date": f"{HOLIDAY_YEAR}-04-13", "holiday_name": "Thingyan (Water Festival Start)"}, # Example
    {"city_id": 5, "holiday_date": f"{HOLIDAY_YEAR}-05-01", "holiday_name": "Labour Day"},
    {"city_id": 5, "holiday_date": f"{HOLIDAY_YEAR}-07-19", "holiday_name": "Martyrs' Day"},
    # Laos (City ID: 6)
    {"city_id": 6, "holiday_date": f"{HOLIDAY_YEAR}-01-01", "holiday_name": "International New Year's Day"},
    {"city_id": 6, "holiday_date": f"{HOLIDAY_YEAR}-03-08", "holiday_name": "International Women's Day"},
    {"city_id": 6, "holiday_date": f"{HOLIDAY_YEAR}-04-14", "holiday_name": "Pi Mai Lao (Lao New Year)"}, # Example Day 1
    {"city_id": 6, "holiday_date": f"{HOLIDAY_YEAR}-05-01", "holiday_name": "Labour Day"},
    {"city_id": 6, "holiday_date": f"{HOLIDAY_YEAR}-12-02", "holiday_name": "Lao National Day"},
    # Cambodia (City ID: 7)
    {"city_id": 7, "holiday_date": f"{HOLIDAY_YEAR}-01-07", "holiday_name": "Victory Over Genocide Day"},
    {"city_id": 7, "holiday_date": f"{HOLIDAY_YEAR}-04-14", "holiday_name": "Khmer New Year (Day 1)"}, # Example
    {"city_id": 7, "holiday_date": f"{HOLIDAY_YEAR}-05-14", "holiday_name": "King Norodom Sihamoni's Birthday"},
    {"city_id": 7, "holiday_date": f"{HOLIDAY_YEAR}-09-24", "holiday_name": "Constitution Day"},
    {"city_id": 7, "holiday_date": f"{HOLIDAY_YEAR}-11-09", "holiday_name": "Independence Day"},
    # Brunei (City ID: 8)
    {"city_id": 8, "holiday_date": f"{HOLIDAY_YEAR}-01-01", "holiday_name": "New Year's Day"},
    {"city_id": 8, "holiday_date": f"{HOLIDAY_YEAR}-02-23", "holiday_name": "National Day"},
    {"city_id": 8, "holiday_date": f"{HOLIDAY_YEAR}-04-10", "holiday_name": "Hari Raya Aidilfitri (Day 1)"}, # Example date
    {"city_id": 8, "holiday_date": f"{HOLIDAY_YEAR}-07-15", "holiday_name": "Sultan's Birthday"},
    {"city_id": 8, "holiday_date": f"{HOLIDAY_YEAR}-12-25", "holiday_name": "Christmas Day"},
]


# --- Functions ---

def load_or_generate_merchants(filename, num_merchants_if_new, types, cuisines, zones, sizes, city_map):
    """
    Loads existing merchant data or generates new if file not found.
    Adds 'merchant_type', 'cuisine_type', 'city_id', and 'city_name' columns if missing.
    Ensures 'city_name' is consistent with 'city_id' based on city_map.
    """
    valid_city_ids = list(city_map.keys())
    try:
        merchants_df = pd.read_csv(filename)
        print(f"Loaded existing data from '{filename}' ({len(merchants_df)} rows).")
        if merchants_df.empty: raise FileNotFoundError("File is empty")

        modified = False
        city_id_added = False
        city_name_added = False

        # Check and add 'merchant_type'
        if 'merchant_type' not in merchants_df.columns:
            print(f"Adding missing column 'merchant_type' to {filename}...")
            if len(merchants_df) > 0: merchants_df['merchant_type'] = [random.choice(types) for _ in range(len(merchants_df))]
            else: merchants_df['merchant_type'] = []
            modified = True
        else: print("'merchant_type' column already exists.")

        # Check and add 'cuisine_type'
        if 'cuisine_type' not in merchants_df.columns:
            print(f"Adding missing column 'cuisine_type' to {filename}...")
            if len(merchants_df) > 0: merchants_df['cuisine_type'] = [random.choice(cuisines) for _ in range(len(merchants_df))]
            else: merchants_df['cuisine_type'] = []
            modified = True
        else: print("'cuisine_type' column already exists.")

        # Check and add 'city_id'
        if 'city_id' not in merchants_df.columns:
            print(f"Adding missing column 'city_id' to {filename}...")
            if len(merchants_df) > 0: merchants_df['city_id'] = [random.choice(valid_city_ids) for _ in range(len(merchants_df))]
            else: merchants_df['city_id'] = []
            city_id_added = True
            modified = True
        else: print("'city_id' column already exists.")

        # Check 'city_name'
        if 'city_name' not in merchants_df.columns:
            print(f"Adding missing column 'city_name' to {filename}...")
            city_name_added = True
            modified = True
        else: print("'city_name' column already exists.")

        # Ensure city_name consistency
        if city_id_added or city_name_added:
            print("Ensuring 'city_name' consistency based on 'city_id'...")
            if 'city_id' in merchants_df.columns:
                 merchants_df['city_name'] = merchants_df['city_id'].map(city_map).fillna("Unknown City")
            else:
                 print("Warning: Cannot derive 'city_name'; 'city_id' column missing.")
                 merchants_df['city_name'] = "Unknown City"

        if modified: print(f"'{filename}' has been modified.")
        else: print(f"No columns needed to be added or modified in '{filename}'.")

    except (FileNotFoundError, pd.errors.EmptyDataError) as e:
        print(f"'{filename}' not found or is empty ({e}). Generating {num_merchants_if_new} new merchants...")
        merchants_list = []
        for i in range(num_merchants_if_new):
            merch_id = f"M{1001 + i}"
            join_date_obj = datetime.datetime(random.randint(2018, TODAY_DATE.year), random.randint(1, 12), random.randint(1, 28))
            if join_date_obj.date() > TODAY_DATE: join_date_obj = join_date_obj.replace(year=TODAY_DATE.year -1 if TODAY_DATE.month == 1 and TODAY_DATE.day == 1 else TODAY_DATE.year, day=1)
            join_date_formatted = join_date_obj.strftime('%Y-%m-%d')
            random_city_id = random.choice(valid_city_ids)
            city_name = city_map[random_city_id]
            merchants_list.append({
                "merchant_id": merch_id, "merchant_name": f"Test Merchant {i+1}",
                "merchant_type": random.choice(types), "cuisine_type": random.choice(cuisines),
                "location_zone": random.choice(zones), "size": random.choice(sizes),
                "business_maturity_years": random.randint(1, 6), "average_rating": round(random.uniform(3.5, 5.0), 1),
                "join_date": join_date_formatted, "city_id": random_city_id, "city_name": city_name
            })
        merchants_df = pd.DataFrame(merchants_list)
        print("New merchant data generation complete.")

    if 'city_id' in merchants_df.columns:
        merchants_df['city_id'] = pd.to_numeric(merchants_df['city_id'], errors='coerce').fillna(0).astype(int)

    return merchants_df


def generate_merchant(filename: Path, city_map: Dict[int, str]) -> pd.DataFrame:
    """
    Reads a merchant CSV file, adds merchant_type and city_name columns.

    Assumes the input CSV file has columns: 'merchant_id', 'merchant_name',
    'join_date', 'city_id'.

    Args:
        filename: The Path object pointing to the merchant CSV file.
        city_map: A dictionary mapping city_id (int) to city_name (str).

    Returns:
        A pandas DataFrame with the original data plus 'merchant_type'
        and 'city_name' columns. Returns an empty DataFrame if the file
        cannot be read or is empty.
    """
    # Define 5 typical merchant types for an online food store
    merchant_types: List[str] = [
        'Restaurant',
        'Cafe',
        'Hawker Stall',
        'Home-Based Kitchen',
        'Cloud Kitchen'
    ]

    try:
        # Read the CSV file
        df = pd.read_csv(filename)
        print(f"Successfully loaded data from '{filename}'.")

        if df.empty:
            print(f"Warning: '{filename}' is empty. Returning an empty DataFrame.")
            return pd.DataFrame(columns=df.columns.tolist() + ['merchant_type', 'city_name'])

        # --- Add 'merchant_type' column ---
        if 'merchant_type' not in df.columns:
            print("Adding 'merchant_type' column...")
            df['merchant_type'] = [random.choice(merchant_types) for _ in range(len(df))]
        else:
            print("'merchant_type' column already exists. Skipping addition.")

        # --- Add 'city_name' column ---
        if 'city_name' not in df.columns:
            print("Adding 'city_name' column...")
            if 'city_id' in df.columns:
                # Ensure city_id is numeric, coercing errors to NaN
                df['city_id_numeric'] = pd.to_numeric(df['city_id'], errors='coerce')
                # Map city_id to city_name, fill missing values
                df['city_name'] = df['city_id_numeric'].map(city_map).fillna('Unknown City')
                # Drop the temporary numeric column
                df = df.drop(columns=['city_id_numeric'])
                print("Mapped 'city_id' to 'city_name'.")
            else:
                print("Warning: 'city_id' column not found. Cannot add 'city_name'. Setting to 'Unknown City'.")
                df['city_name'] = 'Unknown City'
        else:
            print("'city_name' column already exists. Skipping addition.")
            # Optional: Ensure existing city_name is consistent if city_id exists
            if 'city_id' in df.columns:
                 df['city_id_numeric'] = pd.to_numeric(df['city_id'], errors='coerce')
                 expected_city_name = df['city_id_numeric'].map(city_map).fillna('Unknown City')
                 # Check if existing names match expected ones where city_id is valid
                 mismatches = df.loc[df['city_id_numeric'].notna() & (df['city_name'] != expected_city_name), 'city_name'].count()
                 if mismatches > 0:
                     print(f"Warning: Found {mismatches} existing 'city_name' entries inconsistent with 'city_id' and city_map. Consider reviewing.")
                 df = df.drop(columns=['city_id_numeric'])


        return df

    except FileNotFoundError:
        print(f"Error: File not found at '{filename}'. Returning an empty DataFrame.")
        # Return an empty DataFrame with expected columns
        expected_columns = ['merchant_id', 'merchant_name', 'join_date', 'city_id', 'merchant_type', 'city_name']
        return pd.DataFrame(columns=expected_columns)
    except pd.errors.EmptyDataError:
        print(f"Error: File '{filename}' is empty. Returning an empty DataFrame.")
        expected_columns = ['merchant_id', 'merchant_name', 'join_date', 'city_id', 'merchant_type', 'city_name']
        return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        print(f"An unexpected error occurred while processing '{filename}': {e}")
        expected_columns = ['merchant_id', 'merchant_name', 'join_date', 'city_id', 'merchant_type', 'city_name']
        return pd.DataFrame(columns=expected_columns)

# *** New Function for Holidays ***
def generate_holidays(holiday_data_list):
    """Creates a DataFrame from the predefined holiday data list."""
    print(f"Generating holiday data for {len(set(h['city_id'] for h in holiday_data_list))} cities...")
    if not holiday_data_list:
        print("Warning: HOLIDAY_DATA is empty. Cannot generate holidays.")
        return pd.DataFrame(columns=['city_id', 'holiday_date', 'holiday_name'])

    holidays_df = pd.DataFrame(holiday_data_list)
    # Convert date strings to datetime objects for sorting/consistency
    holidays_df['holiday_date'] = pd.to_datetime(holidays_df['holiday_date'], errors='coerce')
    # Ensure city_id is integer
    holidays_df['city_id'] = pd.to_numeric(holidays_df['city_id'], errors='coerce').fillna(0).astype(int)
    # Sort by city and date
    holidays_df = holidays_df.sort_values(by=['city_id', 'holiday_date']).dropna(subset=['holiday_date'])
    # Convert date back to string YYYY-MM-DD format for CSV consistency
    holidays_df['holiday_date'] = holidays_df['holiday_date'].dt.strftime('%Y-%m-%d')
    print("Holiday data generation complete.")
    return holidays_df[['city_id', 'holiday_date', 'holiday_name']] # Ensure column order


# --- Other Generation Functions (Unchanged) ---

def generate_products(merchants_df, num_per_merchant, cuisines, categories):
    """Generates products based on the provided merchants DataFrame."""
    products_list = []
    product_lookup = {}
    print(f"Generating products for {len(merchants_df)} merchants...")
    required_cols = ['merchant_id', 'cuisine_type', 'merchant_type']
    if not all(col in merchants_df.columns for col in required_cols):
         print(f"Error: merchants_df is missing required columns ({required_cols}). Cannot generate products.")
         return [], pd.DataFrame(), {}

    for _, merchant in merchants_df.iterrows():
        merchant_id = merchant["merchant_id"]
        merchant_cuisine = merchant["cuisine_type"]
        merchant_type = merchant["merchant_type"]
        product_lookup[merchant_id] = {}
        for j in range(num_per_merchant):
            prod_id = f"{merchant_id}-P{j+1:03d}"
            price = round(random.uniform(2.5, 25.0), 2)
            cuisine_tag = random.choice(cuisines)
            cat = random.choice(categories)
            if merchant_type == "Cafe" and cat == "Main Course": cat = random.choice(["Beverage", "Dessert", "Snack"])
            products_list.append({
                "product_id": prod_id, "merchant_id": merchant_id,
                "product_name": f"{merchant_cuisine} Item {j+1}", "category": cat, "price": price,
                "is_new": random.choices([True, False], weights=[0.2, 0.8], k=1)[0],
                "dietary_tags": "", "cuisine_tag": cuisine_tag
            })
            product_lookup[merchant_id][prod_id] = price
    products_df = pd.DataFrame(products_list)
    print("Product generation complete.")
    return products_list, products_df, product_lookup

def generate_inventory(
    merchant_ids: Union[List[str], pd.Series], # Updated type hint
    unique_stocks_per_merchant: List[int]
) -> pd.DataFrame:
    """
    Generates a mock inventory DataFrame for multiple merchants with specific stock items.

    Args:
        merchant_ids: A list or pandas Series of merchant IDs (strings). # Updated docstring
        unique_stocks_per_merchant: A list containing the number of unique stock items
                                    each corresponding merchant should have. Must be the
                                    same length as merchant_ids.

    Returns:
        A pandas DataFrame with columns: merchant_id, stock_name, stock_quantity,
        units, last_updated.

    Raises:
        ValueError: If the lengths of merchant_ids and unique_stocks_per_merchant differ.
    """
    if len(merchant_ids) != len(unique_stocks_per_merchant):
        raise ValueError("merchant_ids and unique_stocks_per_merchant inputs must have the same length.")

    # Dictionary of dummy stock items and their units (20 items)
    dummy_stock_units: Dict[str, str] = {
        'Flour': 'kg', 'Sugar': 'kg', 'Eggs': 'dozen', 'Milk': 'liter',
        'Cooking Oil': 'liter', 'Salt': 'kg', 'Pepper': 'g', 'Onions': 'kg',
        'Garlic': 'kg', 'Tomatoes': 'kg', 'Potatoes': 'kg', 'Rice': 'kg',
        'Chicken': 'kg', 'Beef': 'kg', 'Fish': 'kg', 'Butter': 'kg',
        'Cheese': 'kg', 'Bread': 'loaf', 'Coffee Beans': 'kg', 'Tea Leaves': 'g'
    }
    available_stock_names = list(dummy_stock_units.keys())

    inventory_data = []
    print(f"Generating inventory data for {len(merchant_ids)} merchants...")

    # Define the date range for 'last_updated' (end of 2023)
    start_date = datetime(2023, 10, 1, tzinfo=timezone.utc) # Start Q4 2023
    end_date = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc) # End of 2023
    time_delta_seconds = int((end_date - start_date).total_seconds())

    # zip works correctly with both lists and pandas Series
    for merchant_id, num_unique_stocks in zip(merchant_ids, unique_stocks_per_merchant):
        # Ensure merchant_id is treated as a string (important if Series contains non-strings)
        merchant_id_str = str(merchant_id)

        if num_unique_stocks > len(available_stock_names):
            print(f"Warning: Merchant {merchant_id_str} requested {num_unique_stocks} unique stocks, but only {len(available_stock_names)} are available. Using {len(available_stock_names)}.")
            num_unique_stocks = len(available_stock_names)
        elif num_unique_stocks < 0:
            print(f"Warning: Merchant {merchant_id_str} requested a negative number of stocks ({num_unique_stocks}). Setting to 0.")
            num_unique_stocks = 0

        if num_unique_stocks == 0:
            continue # Skip if merchant has 0 stocks requested

        # Select unique stock names for this merchant
        selected_stock_names = random.sample(available_stock_names, num_unique_stocks)

        for stock_name in selected_stock_names:
            unit = dummy_stock_units[stock_name]
            stock_quantity = random.randint(0, 100)

            # Generate random timestamp towards the end of 2023
            random_seconds = random.randint(0, time_delta_seconds)
            last_updated_dt = start_date + timedelta(seconds=random_seconds)
            # Ensure consistent timezone-aware ISO 8601 format with Z for UTC
            last_updated_str = last_updated_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            inventory_data.append({
                'merchant_id': merchant_id_str, # Use the string version
                'stock_name': stock_name,
                'stock_quantity': stock_quantity,
                'units': unit,
                'last_updated': last_updated_str
            })

    inventory_df = pd.DataFrame(inventory_data)
    print("Inventory generation complete.")
    # Ensure correct dtypes (optional but good practice)
    if not inventory_df.empty:
        inventory_df['merchant_id'] = inventory_df['merchant_id'].astype(str) # Ensure merchant_id is string
        inventory_df['stock_quantity'] = inventory_df['stock_quantity'].astype(int)
        # Convert to datetime objects, coercing errors and handling timezone
        inventory_df['last_updated'] = pd.to_datetime(inventory_df['last_updated'], errors='coerce', utc=True)


    return inventory_df

def generate_inventory_history(
    merchant_ids: Union[List[str], pd.Series],
    unique_stocks_per_merchant: List[int],
    start_date: date, # Use date object for start
    end_date: date    # Use date object for end
) -> pd.DataFrame:
    """
    Generates a mock historical inventory DataFrame for multiple merchants.

    For each stock item assigned to a merchant, it generates historical stock
    levels between start_date and end_date with random gaps (1-7 days).
    Stock levels follow a positive sinusoidal pattern over time with added
    Gaussian noise and are represented as integers.

    Args:
        merchant_ids: A list or pandas Series of merchant IDs (strings).
        unique_stocks_per_merchant: A list containing the number of unique stock items
                                    each corresponding merchant should have. Must be the
                                    same length as merchant_ids.
        start_date: The starting date for the historical data generation.
        end_date: The ending date for the historical data generation.

    Returns:
        A pandas DataFrame with columns: merchant_id, stock_name,
        stock_quantity, units, date_updated.

    Raises:
        ValueError: If the lengths of merchant_ids and unique_stocks_per_merchant differ,
                    or if start_date is after end_date.
    """
    if len(merchant_ids) != len(unique_stocks_per_merchant):
        raise ValueError("merchant_ids and unique_stocks_per_merchant inputs must have the same length.")
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date.")

    # Dictionary of dummy stock items and their units
    dummy_stock_units: Dict[str, str] = {
        'Flour': 'kg', 'Sugar': 'kg', 'Eggs': 'dozen', 'Milk': 'liter',
        'Cooking Oil': 'liter', 'Salt': 'kg', 'Pepper': 'g', 'Onions': 'kg',
        'Garlic': 'kg', 'Tomatoes': 'kg', 'Potatoes': 'kg', 'Rice': 'kg',
        'Chicken': 'kg', 'Beef': 'kg', 'Fish': 'kg', 'Butter': 'kg',
        'Cheese': 'kg', 'Bread': 'loaf', 'Coffee Beans': 'kg', 'Tea Leaves': 'g'
    }
    available_stock_names = list(dummy_stock_units.keys())

    inventory_data = []
    total_days = (end_date - start_date).days
    print(f"Generating historical inventory data for {len(merchant_ids)} merchants from {start_date} to {end_date}...")

    # zip works correctly with both lists and pandas Series
    for merchant_id, num_unique_stocks in zip(merchant_ids, unique_stocks_per_merchant):
        merchant_id_str = str(merchant_id)

        # Validate and select unique stock names for this merchant (same logic as before)
        if num_unique_stocks > len(available_stock_names):
            print(f"Warning: Merchant {merchant_id_str} requested {num_unique_stocks} unique stocks, but only {len(available_stock_names)} are available. Using {len(available_stock_names)}.")
            num_unique_stocks = len(available_stock_names)
        elif num_unique_stocks < 0:
            print(f"Warning: Merchant {merchant_id_str} requested negative stocks ({num_unique_stocks}). Setting to 0.")
            num_unique_stocks = 0

        if num_unique_stocks == 0:
            continue

        selected_stock_names = random.sample(available_stock_names, num_unique_stocks)

        for stock_name in selected_stock_names:
            unit = dummy_stock_units[stock_name]
            current_date = start_date

            # --- Sine wave parameters (can be randomized per item) ---
            # Ensure vertical_shift > amplitude for positive values
            amplitude = random.uniform(20, 40)  # Fluctuation range
            vertical_shift = random.uniform(amplitude + 5, 60) # Base stock level ensure positive
            # Period determines how often the cycle repeats (e.g., over 30-90 days)
            period_days = random.uniform(30, 90)
            frequency = (2 * math.pi) / period_days if period_days > 0 else 0
            phase_shift = random.uniform(0, 2 * math.pi) # Random start point in cycle
            noise_std_dev = random.uniform(3, 10) # Gaussian noise level

            while current_date <= end_date:
                # Calculate time elapsed in days for sine wave input
                time_elapsed = (current_date - start_date).days

                # Calculate base stock using sine wave
                base_stock = amplitude * math.sin(frequency * time_elapsed + phase_shift) + vertical_shift

                # Add Gaussian noise
                noisy_stock = base_stock + random.gauss(0, noise_std_dev)

                # Ensure stock is integer and non-negative
                stock_quantity = max(0, int(round(noisy_stock)))

                inventory_data.append({
                    'merchant_id': merchant_id_str,
                    'stock_name': stock_name,
                    'stock_quantity': stock_quantity,
                    'units': unit,
                    'date_updated': current_date # Use the current date in the loop
                })

                # Increment date by a random gap (1-7 days)
                gap_days = random.randint(1, 7)
                current_date += timedelta(days=gap_days)

    inventory_df = pd.DataFrame(inventory_data)
    print("Historical inventory generation complete.")

    # Ensure correct dtypes
    if not inventory_df.empty:
        inventory_df['merchant_id'] = inventory_df['merchant_id'].astype(str)
        inventory_df['stock_quantity'] = inventory_df['stock_quantity'].astype(int)
        # Ensure date_updated is just the date part if needed, though it should be already
        inventory_df['date_updated'] = pd.to_datetime(inventory_df['date_updated']).dt.date

    # Sort for better readability (optional)
    inventory_df = inventory_df.sort_values(by=['merchant_id', 'stock_name', 'date_updated'])

    return inventory_df


def generate_orders_and_items(merchants_df, product_lookup, num_days, orders_range,
                              items_range, quantity_range, acceptance_options,
                              prep_time_range, start_order_id):
    """Generates orders and items based on merchants and product lookup."""
    orders_data = []
    order_items_data = []
    order_id_counter = start_order_id
    print(f"Generating orders for {num_days} days...")
    if merchants_df.empty:
        print("No merchants found to generate orders for.")
        return [], []

    for day_offset in range(num_days):
        current_date = TODAY_DATE - datetime.timedelta(days=day_offset)
        is_recent_day = (day_offset < 7)
        for _, merchant in merchants_df.iterrows():
            merchant_id = merchant["merchant_id"]
            num_orders_today = random.randint(orders_range[0], orders_range[1])
            merchant_products = product_lookup.get(merchant_id, {})
            available_product_ids = list(merchant_products.keys())
            if not available_product_ids: continue
            for _ in range(num_orders_today):
                order_id = f"O{order_id_counter}"; order_id_counter += 1
                hour = random.choice(ORDER_HOURS_DISTRIBUTION); minute = random.randint(0, 59); second = random.randint(0, 59)
                naive_timestamp = datetime.datetime(current_date.year, current_date.month, current_date.day, hour, minute, second)
                utc_timestamp = naive_timestamp.replace(tzinfo=datetime.timezone.utc)
                timestamp_str = utc_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
                acceptance = random.choice(acceptance_options)
                prep_time = None
                if acceptance == "Accepted":
                    if merchant_id == "M1002" and is_recent_day: prep_time = random.randint(M1002_RECENT_PREP_TIME_RANGE[0], M1002_RECENT_PREP_TIME_RANGE[1])
                    else: prep_time = random.randint(prep_time_range[0], prep_time_range[1])
                order_type = random.choice(ORDER_TYPES); issue_reported = random.choice(ISSUE_REPORTED_OPTIONS)
                total_order_amount = 0.0
                max_items = min(items_range[1], len(available_product_ids)); min_items = min(items_range[0], max_items)
                if min_items > max_items: continue
                num_items_in_order = random.randint(min_items, max_items)
                items_added_this_order = random.sample(available_product_ids, num_items_in_order)
                order_has_items = False
                for prod_id in items_added_this_order:
                    item_price = merchant_products.get(prod_id)
                    if item_price is None: continue
                    quantity = random.randint(quantity_range[0], quantity_range[1])
                    order_items_data.append({"order_id": order_id, "product_id": prod_id, "quantity": quantity, "item_price": item_price})
                    total_order_amount += item_price * quantity; order_has_items = True
                if order_has_items:
                    orders_data.append({
                        "order_id": order_id, "merchant_id": merchant_id, "timestamp": timestamp_str,
                        "total_amount": round(total_order_amount, 2), "order_type": order_type,
                        "prep_time_minutes": prep_time, "acceptance_status": acceptance, "issue_reported": issue_reported
                    })
    print(f"Order generation complete. Generated {len(orders_data)} orders and {len(order_items_data)} items.")
    return orders_data, order_items_data

def save_dataframe(df, filename):
    """Saves a DataFrame to a CSV file in the current directory, overwriting if it exists."""
    try:
        df.to_csv(filename, index=False)
        print(f"Saved '{filename}' ({len(df)} rows) to current directory.")
    except Exception as e:
        print(f"Error saving dataframe to '{filename}': {e}")

def generate_transaction_data(filename: Path) -> pd.DataFrame:
    """
    Reads transaction data, calculates preparation, delivery, and total durations.

    Assumes the input CSV file has columns: 'order_id', 'order_time',
    'driver_arrival_time', 'driver_pickup_time', 'delivery_time',
    'order_value', 'eater_id', 'merchant_id'.

    Args:
        filename: The Path object pointing to the transaction data CSV file.

    Returns:
        A pandas DataFrame with the original data plus columns for:
        'prep_duration_minutes', 'delivery_duration_minutes',
        'total_duration_minutes'. Returns an empty DataFrame if the file
        cannot be read, is empty, or lacks required time columns.
    """
    try:
        df = pd.read_csv(filename)
        print(f"Successfully loaded data from '{filename}'.")

        if df.empty:
            print(f"Warning: '{filename}' is empty. Returning an empty DataFrame.")
            # Define expected columns including new duration ones
            expected_cols = df.columns.tolist() + [
                'prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes'
            ]
            return pd.DataFrame(columns=expected_cols)

        # --- Define required time columns ---
        required_time_cols = ['order_time', 'driver_pickup_time', 'delivery_time']

        # --- Check if required time columns exist ---
        missing_cols = [col for col in required_time_cols if col not in df.columns]
        if missing_cols:
            print(f"Error: Missing required time columns: {missing_cols}. Cannot calculate durations.")
            # Return original columns plus empty duration columns
            expected_cols = df.columns.tolist() + [
                'prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes'
            ]
            # Add NaN columns if they don't exist, before returning
            for col in ['prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes']:
                if col not in df.columns:
                    df[col] = np.nan
            return df[expected_cols] # Return with original + empty duration columns

        # --- Convert time columns to datetime objects ---
        print("Converting time columns to datetime objects...")
        for col in required_time_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce') # NaT for errors

        # --- Calculate Durations (in minutes) ---
        print("Calculating durations...")

        # Food Preparation Duration: driver_pickup_time - order_time
        df['prep_duration'] = df['driver_pickup_time'] - df['order_time']
        # Convert timedelta to total minutes, result is NaN if calculation involves NaT
        df['prep_duration_minutes'] = df['prep_duration'].dt.total_seconds() / 60

        # Delivery Duration: delivery_time - driver_pickup_time
        df['delivery_duration'] = df['delivery_time'] - df['driver_pickup_time']
        df['delivery_duration_minutes'] = df['delivery_duration'].dt.total_seconds() / 60

        # Total Duration: delivery_time - order_time
        df['total_duration'] = df['delivery_time'] - df['order_time']
        df['total_duration_minutes'] = df['total_duration'].dt.total_seconds() / 60

        # --- Clean up intermediate timedelta columns ---
        df = df.drop(columns=['prep_duration', 'delivery_duration', 'total_duration'])

        print("Duration calculations complete.")
        return df

    except FileNotFoundError:
        print(f"Error: File not found at '{filename}'. Returning an empty DataFrame.")
        # Define expected columns for an empty DataFrame structure
        expected_columns = [
            'order_id', 'order_time', 'driver_arrival_time', 'driver_pickup_time',
            'delivery_time', 'order_value', 'eater_id', 'merchant_id',
            'prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes'
        ]
        return pd.DataFrame(columns=expected_columns)
    except pd.errors.EmptyDataError:
        print(f"Error: File '{filename}' is empty. Returning an empty DataFrame.")
        expected_columns = [
            'order_id', 'order_time', 'driver_arrival_time', 'driver_pickup_time',
            'delivery_time', 'order_value', 'eater_id', 'merchant_id',
            'prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes'
        ]
        return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        print(f"An unexpected error occurred while processing '{filename}': {e}")
        expected_columns = [
            'order_id', 'order_time', 'driver_arrival_time', 'driver_pickup_time',
            'delivery_time', 'order_value', 'eater_id', 'merchant_id',
            'prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes'
        ]
        # Attempt to return original columns plus NaN duration columns if df was loaded
        try:
             if 'df' in locals() and isinstance(df, pd.DataFrame):
                 for col in ['prep_duration_minutes', 'delivery_duration_minutes', 'total_duration_minutes']:
                     if col not in df.columns: df[col] = np.nan
                 return df.reindex(columns=expected_columns, fill_value=np.nan)
             else:
                 return pd.DataFrame(columns=expected_columns)
        except: # Fallback if df doesn't exist or reindex fails
             return pd.DataFrame(columns=expected_columns)


def add_price_to_transaction_items(transaction_items_df: pd.DataFrame, price_dict: Dict[int, float]) -> pd.DataFrame:
    """
    Adds an 'item_price' column to the transaction items DataFrame based on a price dictionary.

    Assumes the input DataFrame has an 'item_id' column whose values correspond
    to keys in the price_dict.

    Args:
        transaction_items_df: DataFrame containing transaction items,
                              including an 'item_id' column.
        price_dict: A dictionary mapping item_id (str) to its price (float).
                    Note: Based on the example, item_id is treated as a string.

    Returns:
        A pandas DataFrame with the original data plus an 'item_price' column.
        Returns the original DataFrame with a warning if 'item_id' column is missing
        or if the input is not a DataFrame. Returns the DataFrame with NaN for
        item_ids not found in the price_dict.
    """
    # --- Input Validation ---
    if not isinstance(transaction_items_df, pd.DataFrame):
        print("Error: Input 'transaction_items_df' is not a pandas DataFrame.")
        # Return an empty DataFrame or raise an error, depending on desired behavior
        return pd.DataFrame() # Or raise TypeError

    if 'item_id' not in transaction_items_df.columns:
        print("Warning: 'item_id' column not found in the DataFrame. Cannot add prices.")
        return transaction_items_df # Return original DF

    if not isinstance(price_dict, dict):
        print("Error: Input 'price_dict' is not a dictionary.")
        # Optionally add an empty price column before returning
        if 'item_price' not in transaction_items_df.columns:
             transaction_items_df['item_price'] = np.nan
        return transaction_items_df # Or raise TypeError

    # --- Add 'item_price' column ---
    print(f"Mapping 'item_id' to 'item_price' using the provided dictionary...")

    # Ensure item_id is treated as string for mapping, matching typical product IDs
    # If your item_ids are truly integers, you might need to adjust this or the dict keys
    item_ids_str = transaction_items_df['item_id'].astype(int)

    # Map item_id to price using the dictionary. Fill missing values with NaN.
    transaction_items_df['item_price'] = item_ids_str.map(price_dict).fillna(np.nan)

    # Check how many items couldn't be mapped (optional)
    missing_prices = transaction_items_df['item_price'].isna().sum()
    if missing_prices > 0:
        print(f"Warning: Could not find prices for {missing_prices} item_ids in the price_dict. 'item_price' set to NaN for these.")

    print("Added 'item_price' column.")
    return transaction_items_df


# --- Main Execution ---
def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


    # Merchant data
    merchants_df = pd.read_csv(MERCHANT_FILENAME)

   
    # Inventory data
    inventory_df = generate_inventory_history(merchant_ids= merchants_df.merchant_id, 
                                      unique_stocks_per_merchant= np.random.randint(3, 10, size = len(merchants_df.merchant_id)),
                                      start_date= date(year = 2023, month = 1, day = 1), end_date= date(year = 2024, month = 1, day = 1))
    
    print(inventory_df)
    # print(inventory_df.loc[(inventory_df.merchant_id == "0c2d7") & (inventory_df.stock_name == "Beef")])
    inventory_df.to_csv(INVENTORY_FILENAME, index = False)


    # # PROCESS RAW DATA
    # # Merchant data
    # merchants_df = generate_merchant(MERCHANT_FILENAME, CITY_MAP)
    # merchants_df.to_csv(MERCHANT_FILENAME.with_name("merchant_appended.csv"), index = False)
    
    # # Inventory data
    # inventory_df = generate_inventory(merchant_ids= merchants_df.merchant_id, 
    #                                   unique_stocks_per_merchant= np.random.randint(3, 10, size = len(merchants_df.merchant_id)))
    # inventory_df.to_csv(INVENTORY_FILENAME, index = False)


    # # Generate Transaction data
    # transaction_data_df = generate_transaction_data(TRANSACTION_DATA_FILENAME)
    # transaction_data_df = transaction_data_df.drop(transaction_data_df.columns[0], axis = 1)
    # transaction_data_df.to_csv(TRANSACTION_DATA_FILENAME.with_name("transaction_data_appended.csv"), index = False)

    
    # items_df = pd.read_csv(ITEMS_FILENAME)


    # # Drop index col Transaction items
    # transaction_item_df = pd.read_csv(TRANSACTION_ITEMS_FILENAME, index_col = 0)
    
    # price_dict = items_df[["item_id", "item_price"]].set_index("item_id").to_dict()["item_price"]
    # transaction_item_df = add_price_to_transaction_items(transaction_item_df, price_dict)
    # transaction_item_df.to_csv(TRANSACTION_ITEMS_FILENAME.with_name("transaction_items_appended.csv"), index = False)


    # # holiday dataframe
    # holidays_df = generate_holidays(HOLIDAY_DATA)   
    # save_dataframe(holidays_df, HOLIDAY_FILENAME)



    

    # """Main function to generate all data and save CSV files."""
    # print("Starting mock data generation...")
    # print(f"Will attempt to load/modify '{MERCHANT_FILENAME}' or generate new.")
    # print(f"'{HOLIDAY_FILENAME}' will be generated/overwritten.")
    # print("Other files will be overwritten.")

    # # 1. Load or Generate Merchants
    # merchants_df = load_or_generate_merchants(
    #     MERCHANT_FILENAME, NUM_MERCHANTS, MERCHANT_TYPES, CUISINE_TYPES,
    #     LOCATION_ZONES, MERCHANT_SIZES, CITY_MAP
    # )
    # if merchants_df is None or merchants_df.empty:
    #     print("Error: Could not load or generate merchant data. Aborting.")
    #     return

    # # 2. Generate Holidays (New Step)
    # holidays_df = generate_holidays(HOLIDAY_DATA)

    # # 3. Generate Products
    # products_list, products_df, product_lookup = generate_products(
    #     merchants_df, NUM_PRODUCTS_PER_MERCHANT, CUISINE_TYPES, PRODUCT_CATEGORIES
    # )

    # # 4. Generate Inventory
    # inventory_df = generate_inventory(products_df)

    # # 5. Generate Orders and Order Items
    # orders_data, order_items_data = generate_orders_and_items(
    #     merchants_df, product_lookup, NUM_DAYS_OF_ORDERS, ORDERS_PER_DAY_RANGE,
    #     ITEMS_PER_ORDER_RANGE, QUANTITY_PER_ITEM_RANGE, ACCEPTANCE_STATUS_OPTIONS,
    #     PREP_TIME_RANGE_MIN, START_ORDER_ID
    # )

    # # 6. Save DataFrames
    # print("\nSaving DataFrames to CSV...")
    # save_dataframe(merchants_df, MERCHANT_FILENAME)
    # save_dataframe(holidays_df, HOLIDAY_FILENAME) # Save holidays
    # save_dataframe(products_df, ITEMS_FILENAME)
    # save_dataframe(inventory_df, INVENTORY_FILENAME)

    # if orders_data:
    #     orders_df = pd.DataFrame(orders_data)
    #     orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])
    #     orders_df = orders_df.sort_values(by='timestamp', ascending=False)
    #     save_dataframe(orders_df, TRANSACTION_DATA_FILENAME)
    # else: print(f"No order data generated, skipping save for {TRANSACTION_DATA_FILENAME}.")

    # if order_items_data:
    #     order_items_df = pd.DataFrame(order_items_data)
    #     save_dataframe(order_items_df, TRANSACTION_ITEMS_FILENAME)
    # else: print(f"No order item data generated, skipping save for {TRANSACTION_ITEMS_FILENAME}.")

    # print("\nMock data generation complete.")
    # print("CSV files saved in the current directory.")




if __name__ == "__main__":
    main()