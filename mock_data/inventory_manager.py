# inventory_manager.py
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

# --- Constants ---
# Assumes this script is in the same directory as the mock_data folder
# Or adjust as needed relative to your project structure
SCRIPT_DIR = Path(__file__).resolve().parent
# Default path assumes mock_data is a subdirectory relative to this script
# Change this if your structure is different
MOCK_DATA_DIR = SCRIPT_DIR / "mock_data"
INVENTORY_FILEPATH = MOCK_DATA_DIR / "inventory.csv" # Default Path to the inventory file

# Expected columns in the inventory CSV
EXPECTED_COLS = ['product_id', 'current_stock', 'last_updated']

# --- Helper Functions ---

def _ensure_directory_exists(filepath: Path):
    """Creates the parent directory for the filepath if it doesn't exist."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create directory {filepath.parent}. Saving might fail. Error: {e}")

def _read_inventory(filepath: Path = INVENTORY_FILEPATH) -> pd.DataFrame:
    """
    Reads the inventory CSV file into a DataFrame.
    Handles file not found and empty file scenarios.
    Ensures correct data types.

    Args:
        filepath: Path to the inventory CSV file.

    Returns:
        A pandas DataFrame with inventory data, or an empty DataFrame
        with expected columns if the file is not found or empty.
    """
    _ensure_directory_exists(filepath) # Ensure directory exists before trying to read
    try:
        df = pd.read_csv(filepath)
        # Basic validation: check if essential columns exist
        if not all(col in df.columns for col in ['product_id', 'current_stock']):
             print(f"Warning: File '{filepath}' is missing required columns ('product_id', 'current_stock'). Returning empty.")
             return pd.DataFrame(columns=EXPECTED_COLS)

        # Ensure correct data types after loading
        if not df.empty:
            df['product_id'] = df['product_id'].astype(str)
            df['current_stock'] = pd.to_numeric(df['current_stock'], errors='coerce').fillna(0).astype(int)
            # Read timestamp as UTC, coerce errors to NaT (Not a Time)
            if 'last_updated' in df.columns:
                df['last_updated'] = pd.to_datetime(df['last_updated'], errors='coerce', utc=True)
            else:
                # If column missing, add it with NaT
                print(f"Warning: 'last_updated' column missing in '{filepath}'. Adding column with NaT.")
                df['last_updated'] = pd.NaT

        print(f"Read {len(df)} items from '{filepath}'")
        return df

    except FileNotFoundError:
        print(f"Inventory file '{filepath}' not found. Returning empty DataFrame.")
        return pd.DataFrame(columns=EXPECTED_COLS)
    except pd.errors.EmptyDataError:
         print(f"Inventory file '{filepath}' is empty. Returning empty DataFrame.")
         return pd.DataFrame(columns=EXPECTED_COLS)
    except Exception as e:
        print(f"Error reading inventory file '{filepath}': {e}")
        return pd.DataFrame(columns=EXPECTED_COLS)

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
                 else:
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
        df_to_save.to_csv(filepath, index=False, date_format='%Y-%m-%dT%H:%M:%SZ') # Specify format again just in case
        print(f"Inventory saved successfully to '{filepath}' ({len(df_to_save)} rows)")

    except Exception as e:
        print(f"Error saving inventory file '{filepath}': {e}")

# --- Public Functions for Modifying Inventory ---

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
    # Add other details if provided and columns exist/are expected
    # if other_details:
    #     for key, value in other_details.items():
    #         if key in EXPECTED_COLS: # Or a predefined list of allowed extra columns
    #             new_item_data[key] = value

    new_item = pd.DataFrame([new_item_data])

    # Append new item
    # Use pd.concat instead of append (which is deprecated)
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
        print(f"Warning: Multiple entries found for product '{product_id}'. Updating all found entries.")
        # Update all matching rows

    # Update stock and timestamp for all matched indices
    now_ts = datetime.now(timezone.utc) # Use timezone-aware UTC time
    inventory_df.loc[product_mask, 'current_stock'] = new_stock_level
    inventory_df.loc[product_mask, 'last_updated'] = now_ts # Store as datetime

    # Save updated inventory
    _save_inventory(inventory_df, filepath)
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
    df_display = df.copy()

    # Format the timestamp column if it exists and has datetime objects
    if 'last_updated' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['last_updated']):
         # Format timestamp for display, handling potential NaT values
         # Example format: 'YYYY-MM-DD HH:MM:SS UTC'
         df_display['last_updated'] = df_display['last_updated'].apply(
             lambda x: x.strftime('%Y-%m-%d %H:%M:%S %Z') if pd.notna(x) and hasattr(x, 'strftime') else 'N/A'
        )
    elif 'last_updated' in df_display.columns:
        # If it's not datetime, just ensure it's string and handle None/NaN
        df_display['last_updated'] = df_display['last_updated'].astype(str).fillna('N/A')


    # Return only expected columns in the desired order
    return df_display[EXPECTED_COLS]


# --- Example Usage (for testing this script directly) ---
if __name__ == "__main__":
    print("-" * 30)
    print("Testing Inventory Manager Functions...")
    print(f"Using inventory file: {INVENTORY_FILEPATH}")
    print("-" * 30)

    # Ensure the mock_data directory and potentially an empty inventory file exist for testing
    _ensure_directory_exists(INVENTORY_FILEPATH)
    # Optional: Create an empty file if it doesn't exist for a clean test start
    # if not INVENTORY_FILEPATH.exists():
    #      pd.DataFrame(columns=EXPECTED_COLS).to_csv(INVENTORY_FILEPATH, index=False)


    # Example 1: Add a new product
    test_prod_id_1 = "TEST-P001"
    print(f"\nAttempting to add '{test_prod_id_1}'...")
    success_add = add_new_product_stock(product_id=test_prod_id_1, initial_stock=50)
    print(f"Add result: {success_add}")

    # Example 2: Try adding the same product again (should fail)
    print(f"\nAttempting to add '{test_prod_id_1}' again...")
    success_add_again = add_new_product_stock(product_id=test_prod_id_1, initial_stock=10)
    print(f"Add again result: {success_add_again}")

    # Example 3: Update the newly added product
    new_level = 75
    print(f"\nAttempting to update '{test_prod_id_1}' to {new_level}...")
    success_update = update_product_stock(product_id=test_prod_id_1, new_stock_level=new_level)
    print(f"Update result: {success_update}")

    # Example 4: Update a non-existent product (should fail)
    product_non_existent = "MXXXX-PXXXX"
    print(f"\nAttempting to update non-existent '{product_non_existent}'...")
    success_update_fail = update_product_stock(product_id=product_non_existent, new_stock_level=10)
    print(f"Update non-existent result: {success_update_fail}")

     # Example 5: Add another product
    test_prod_id_2 = "TEST-P002"
    print(f"\nAttempting to add '{test_prod_id_2}'...")
    success_add_2 = add_new_product_stock(product_id=test_prod_id_2, initial_stock=0)
    print(f"Add result 2: {success_add_2}")

    # Example 6: Update product with negative stock (should fail)
    print(f"\nAttempting to update '{test_prod_id_1}' to -5...")
    success_update_neg = update_product_stock(product_id=test_prod_id_1, new_stock_level=-5)
    print(f"Update negative result: {success_update_neg}")


    # Example 7: Display current inventory
    print("\n--- Current Inventory (Formatted for Display) ---")
    current_inv_df = get_inventory_display()
    if not current_inv_df.empty:
        print(current_inv_df.to_string(index=False))
    else:
        print("Inventory is empty or could not be read.")
    print("-" * 30)