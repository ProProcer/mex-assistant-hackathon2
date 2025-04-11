# inventory_manager.py
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np # Ensure numpy is imported
import logging # Using logging is generally better than print for libraries/modules
import os
import traceback

# --- Constants ---
SCRIPT_DIR = Path(__file__).resolve().parent
# Correct path assuming mock_data is in the parent directory of the script's location
# If generate_data.py and inventory_manager.py are both INSIDE mock_data, this needs adjustment.
# Assuming inventory_manager.py might be *outside* mock_data, pointing inwards:
MOCK_DATA_DIR = SCRIPT_DIR.parent / "mock_data" # Adjust if manager is inside mock_data
INVENTORY_FILEPATH = MOCK_DATA_DIR / "inventory.csv" # Default Path

EXPECTED_COLS = ['product_id', 'current_stock', 'last_updated'] # Ensure this matches product ID column name from items.csv

# --- Helper Functions ---

def _ensure_directory_exists(filepath: Path):
    """Creates the parent directory for the filepath if it doesn't exist."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create directory {filepath.parent}. File operations might fail. Error: {e}")

def _read_inventory(filepath: Path = INVENTORY_FILEPATH) -> pd.DataFrame:
    """
    Reads the inventory CSV file into a DataFrame.
    Handles file not found, empty files, and ensures required columns and data types.

    Args:
        filepath: Path to the inventory CSV file.

    Returns:
        A pandas DataFrame with inventory data, or an empty DataFrame
        with expected columns if the file is not found, empty, or invalid.
    """
    _ensure_directory_exists(filepath) # Ensure directory exists
    print(f"Attempting to read inventory from: {filepath}")

    try:
        df = pd.read_csv(filepath)
        print(f"Successfully read {len(df)} rows from '{filepath}'. Validating columns...")

        if df.empty:
            print(f"File '{filepath}' is empty. Returning empty DataFrame with expected columns.")
            return pd.DataFrame(columns=EXPECTED_COLS)

        # --- Column and Type Validation ---
        is_valid = True
        # Check/Add 'product_id'
        if 'product_id' not in df.columns:
            print(f"Warning: File '{filepath}' missing 'product_id' column. Cannot process.")
            # If product_id is missing, the file is fundamentally unusable for stock updates
            return pd.DataFrame(columns=EXPECTED_COLS)
        else:
            df['product_id'] = df['product_id'].astype(str)

        # Check/Add 'current_stock'
        if 'current_stock' not in df.columns:
            print(f"Warning: File '{filepath}' missing 'current_stock' column. Adding with default 0.")
            df['current_stock'] = 0
        else:
            df['current_stock'] = pd.to_numeric(df['current_stock'], errors='coerce').fillna(0).astype(int)
            # Ensure no negative stock values read from file (optional sanity check)
            # df['current_stock'] = df['current_stock'].apply(lambda x: max(0, x))


        # Check/Add 'last_updated'
        if 'last_updated' not in df.columns:
            print(f"Warning: File '{filepath}' missing 'last_updated' column. Adding with NaT.")
            df['last_updated'] = pd.NaT
        else:
            # Read timestamp as UTC, coerce errors to NaT (Not a Time)
            df['last_updated'] = pd.to_datetime(df['last_updated'], errors='coerce', utc=True)

        print("Column validation and type conversion complete.")
        # Return only expected columns, in case extra columns were read
        return df[EXPECTED_COLS]


    except FileNotFoundError:
        print(f"Inventory file '{filepath}' not found. Returning empty DataFrame.")
        return pd.DataFrame(columns=EXPECTED_COLS)
    except pd.errors.EmptyDataError:
         print(f"Inventory file '{filepath}' is empty. Returning empty DataFrame.")
         return pd.DataFrame(columns=EXPECTED_COLS)
    except Exception as e:
        print(f"Error reading or processing inventory file '{filepath}': {e}")
        import traceback
        traceback.print_exc() # Print stack trace for debugging
        return pd.DataFrame(columns=EXPECTED_COLS)

# --- Rest of inventory_manager.py remains the same ---
# ( _save_inventory, add_new_product_stock, update_product_stock, get_inventory_display )
# Make sure update_product_stock uses the correct product_id column name

def _save_inventory(df: pd.DataFrame, filepath: Path = INVENTORY_FILEPATH):
    """
    Saves the inventory DataFrame back to the CSV file.
    Formats timestamps correctly before saving.

    Args:
        df: The pandas DataFrame containing inventory data.
        filepath: Path to the inventory CSV file.
    """
    _ensure_directory_exists(filepath) # Ensure directory exists before saving
    try:
        df_to_save = df.copy() # Work on a copy

        # Ensure all expected columns exist before saving
        for col in EXPECTED_COLS:
            if col not in df_to_save.columns:
                 print(f"Warning: Column '{col}' missing before save. Adding with default values.")
                 if col == 'current_stock':
                     df_to_save[col] = 0
                 elif col == 'last_updated':
                     df_to_save[col] = pd.NaT # Use NaT for missing time
                 else: # Assume product_id must exist based on _read_inventory logic
                     df_to_save[col] = None

        # Format the 'last_updated' column to ISO string with 'Z' for UTC
        if 'last_updated' in df_to_save.columns and pd.api.types.is_datetime64_any_dtype(df_to_save['last_updated']):
            # Apply formatting only to valid datetime objects, keep NaT as empty string or similar
             df_to_save['last_updated'] = df_to_save['last_updated'].apply(
                 lambda dt: dt.strftime('%Y-%m-%dT%H:%M:%SZ') if pd.notna(dt) and hasattr(dt, 'strftime') else ''
            )
        elif 'last_updated' in df_to_save.columns:
             # If column exists but isn't datetime, convert to string or empty
             df_to_save['last_updated'] = df_to_save['last_updated'].astype(str).fillna('')


        # Ensure column order and save
        df_to_save = df_to_save[EXPECTED_COLS] # Select only expected columns in order
        df_to_save.to_csv(filepath, index=False) # date_format handled by lambda now
        print(f"Inventory saved successfully to '{filepath}' ({len(df_to_save)} rows)")

    except Exception as e:
        print(f"Error saving inventory file '{filepath}': {e}")


def add_new_product_stock(
    product_id: str,
    initial_stock: int,
    other_details: Optional[Dict[str, Any]] = None, # For potential future columns
    filepath: Path = INVENTORY_FILEPATH
    ) -> bool:
    """
    Adds a new product row to the inventory CSV.

    Args:
        product_id: The unique ID of the new product (string).
        initial_stock: The starting stock quantity (integer, must be non-negative).
        other_details: Optional dictionary for future columns (not used currently).
        filepath: Path to the inventory CSV file.

    Returns:
        True if the item was added successfully, False otherwise.
    """
    if not isinstance(product_id, str) or not product_id:
        print("Error: Invalid product_id provided.")
        return False
    if not isinstance(initial_stock, int) or initial_stock < 0:
        print(f"Error: Initial stock for '{product_id}' must be a non-negative integer.")
        return False

    print(f"Attempting to add new product: '{product_id}' with stock: {initial_stock}")
    inventory_df = _read_inventory(filepath)

    # Check if product already exists
    if product_id in inventory_df['product_id'].values:
        print(f"Error: Product '{product_id}' already exists. Use 'update_product_stock' instead.")
        return False

    # Create new item data
    now_ts = datetime.now(timezone.utc) # Use timezone-aware UTC time
    new_item_data = {
        'product_id': product_id,
        'current_stock': initial_stock,
        'last_updated': now_ts # Store as datetime object internally
    }

    new_item = pd.DataFrame([new_item_data])

    # Append new item
    updated_df = pd.concat([inventory_df, new_item], ignore_index=True)

    # Ensure data types are correct before saving (especially if df was empty)
    updated_df['product_id'] = updated_df['product_id'].astype(str)
    updated_df['current_stock'] = pd.to_numeric(updated_df['current_stock'], errors='coerce').fillna(0).astype(int)
    updated_df['last_updated'] = pd.to_datetime(updated_df['last_updated'], errors='coerce', utc=True)


    # Save updated inventory
    _save_inventory(updated_df, filepath)
    return True

def update_product_stock(
    product_id: str,
    new_stock_level: int,
    filepath: Path = INVENTORY_FILEPATH
    ) -> bool:
    """
    Updates the stock level for an existing product in the inventory CSV.

    Args:
        product_id: The unique ID of the product to update (string).
        new_stock_level: The new stock quantity (integer, must be non-negative).
        filepath: Path to the inventory CSV file.

    Returns:
        True if the item was updated successfully, False otherwise.
    """
    if not isinstance(product_id, str) or not product_id:
        print("Error: Invalid product_id provided.")
        return False
    if not isinstance(new_stock_level, int) or new_stock_level < 0:
        print(f"Error: New stock level for '{product_id}' must be a non-negative integer.")
        return False

    print(f"Attempting to update product: '{product_id}' to stock level: {new_stock_level}")
    inventory_df = _read_inventory(filepath)

    # Find the product index/indices
    product_mask = inventory_df['product_id'] == product_id
    indices_to_update = inventory_df.index[product_mask].tolist()

    if not indices_to_update:
        print(f"Error: Product '{product_id}' not found in inventory. Cannot update.")
        return False

    if len(indices_to_update) > 1:
        print(f"Warning: Multiple entries found for product '{product_id}'. Updating first found entry.")
        # Update only the first matching row to avoid unintended consequences if duplicates exist
        first_index = indices_to_update[0]
        product_mask = inventory_df.index == first_index # Redefine mask to single index

    # Update stock and timestamp
    now_ts = datetime.now(timezone.utc) # Use timezone-aware UTC time
    inventory_df.loc[product_mask, 'current_stock'] = new_stock_level
    inventory_df.loc[product_mask, 'last_updated'] = now_ts # Store as datetime

    # Save updated inventory
    _save_inventory(inventory_df, filepath)
    print(f"Successfully updated stock for product '{product_id}'.")
    return True

def get_inventory_display(filepath: Path = INVENTORY_FILEPATH) -> pd.DataFrame:
    """
    Reads inventory and formats it nicely for display purposes.
    Converts timestamp to a readable string format.

    Args:
        filepath: Path to the inventory CSV file.

    Returns:
        A pandas DataFrame formatted for display, or an empty DataFrame.
    """
    df = _read_inventory(filepath)
    if df.empty:
        return df # Return empty if read failed

    df_display = df.copy()

    # Format the timestamp column if it exists and has datetime objects
    if 'last_updated' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['last_updated']):
         # Format timestamp for display, handling potential NaT values
         # Example format: 'YYYY-MM-DD HH:MM:SS UTC'
         df_display['last_updated_display'] = df_display['last_updated'].apply(
             lambda x: x.strftime('%Y-%m-%d %H:%M:%S %Z') if pd.notna(x) and hasattr(x, 'strftime') else 'N/A'
        )
    elif 'last_updated' in df_display.columns:
        # If it's not datetime, just ensure it's string and handle None/NaN
        df_display['last_updated_display'] = df_display['last_updated'].astype(str).fillna('N/A')
    else:
        df_display['last_updated_display'] = 'N/A'


    # Return relevant columns (including the display-formatted date)
    return df_display[['product_id', 'current_stock', 'last_updated_display']]

# --- Configuration ---
# Define the standard columns for the inventory log
INVENTORY_COLUMNS = ['merchant_id', 'stock_name', 'stock_quantity', 'units', 'date_updated']

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


# --- Functions ---

def add_stock_log_entry(merchant_id: str,
                        stock_name: str,
                        new_stock_level: int,
                        units: str,
                        date_updated_str: str,
                        filepath: str) -> bool:
    """
    Appends a new stock update entry (a single row) to the specified CSV log file.

    Ensures the CSV exists and writes the header only if the file is new or empty.

    Args:
        merchant_id (str): The ID of the merchant performing the update.
        stock_name (str): The name of the stock item being updated.
        new_stock_level (int): The new quantity recorded for the stock item.
        units (str): The unit of measurement (e.g., 'kg', 'pcs', 'litre').
        date_updated_str (str): The date of the update in 'YYYY-MM-DD' string format.
        filepath (str): The full path to the inventory CSV file.

    Returns:
        bool: True if the entry was successfully appended, False otherwise.
    """
    log.info(f"Attempting to add log entry to {filepath}: "
             f"Merchant={merchant_id}, Stock={stock_name}, Qty={new_stock_level}, "
             f"Units={units}, Date={date_updated_str}")

    try:
        # 1. Prepare the data for the new row as a DataFrame
        #    Using a DataFrame simplifies writing with pandas
        new_entry_data = {
            'merchant_id': [merchant_id],
            'stock_name': [stock_name],
            'stock_quantity': [new_stock_level], # Use the correct column name for the CSV
            'units': [units],
            'date_updated': [date_updated_str]
        }
        # Ensure the DataFrame uses the standard column order
        new_entry_df = pd.DataFrame(new_entry_data, columns=INVENTORY_COLUMNS)

        # 2. Determine if the CSV header needs to be written
        #    This is true if the file doesn't exist or if it exists but is empty.
        write_header = False
        if not os.path.exists(filepath):
            log.info(f"File {filepath} does not exist. Will create and write header.")
            write_header = True
            # Ensure directory exists if filepath includes directories
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
            except FileNotFoundError: # Handle cases where filepath is just a filename
                 pass
            except Exception as dir_err:
                log.error(f"Could not create directory for {filepath}: {dir_err}")
                return False # Cannot proceed if directory can't be created
        elif os.path.getsize(filepath) == 0:
            log.info(f"File {filepath} exists but is empty. Will write header.")
            write_header = True

        # 3. Append the DataFrame row to the CSV file
        new_entry_df.to_csv(
            filepath,
            mode='a',           # 'a' for append mode
            header=write_header,# Write header only if determined above
            index=False         # Don't write the DataFrame index as a column
        )

        log.info(f"Successfully appended entry for '{stock_name}' to {filepath}")
        return True

    except PermissionError:
        log.error(f"Permission denied when trying to write to {filepath}.")
        traceback.print_exc()
        return False
    except Exception as e:
        # Catch other potential errors (e.g., disk full, invalid filepath format)
        log.error(f"An unexpected error occurred while appending to {filepath}: {e}")
        traceback.print_exc() # Log the full traceback for debugging help
        return False



# --- Example Usage ---
if __name__ == "__main__":
    print("-" * 30)
    print("Testing Inventory Manager Functions...")
    print(f"Using inventory file: {INVENTORY_FILEPATH}")
    print("-" * 30)

    # Ensure the mock_data directory and potentially an empty inventory file exist for testing
    _ensure_directory_exists(INVENTORY_FILEPATH)

    # Example: Add a new product if it doesn't exist
    test_prod_id_new = "NEW-TEST-001"
    if not (INVENTORY_FILEPATH.exists() and test_prod_id_new in _read_inventory(INVENTORY_FILEPATH)['product_id'].values):
         print(f"\nAttempting to add '{test_prod_id_new}'...")
         success_add = add_new_product_stock(product_id=test_prod_id_new, initial_stock=25)
         print(f"Add result: {success_add}")
    else:
         print(f"Product '{test_prod_id_new}' already exists or file issue.")

    # Example: Update an existing product (use an ID known from your items.csv/inventory.csv)
    test_prod_id_existing = "1d4f2-P001" # CHANGE THIS to a valid ID from your items.csv
    new_level = 99
    print(f"\nAttempting to update '{test_prod_id_existing}' to {new_level}...")
    success_update = update_product_stock(product_id=test_prod_id_existing, new_stock_level=new_level)
    print(f"Update result: {success_update}")

    # Example: Display current inventory
    print("\n--- Current Inventory (Formatted for Display) ---")
    current_inv_df = get_inventory_display()
    if not current_inv_df.empty:
        print(current_inv_df.to_string(index=False))
    else:
        print("Inventory is empty or could not be read.")
    print("-" * 30)