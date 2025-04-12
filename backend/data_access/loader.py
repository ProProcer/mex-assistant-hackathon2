import pandas as pd
from backend import config
from datetime import datetime
import os # Import os for path checks and directory creation
import logging # Use logging for better messages

# Global variables to store loaded DataFrames
_merchant_df = None
_items_df = None
_transaction_data_df = None
_inventory_df = None
_transaction_items_df = None  # <-- Add this
_notifications_df = None # <-- NEW global variable


def load_all_data():
    """Loads all data from CSV files into pandas DataFrames."""
    global _merchant_df, _items_df, _transaction_data_df, _inventory_df, _transaction_items_df, _notifications_df

    try:
        # Load Merchant Data
        _merchant_df = pd.read_csv(config.MERCHANT_CSV)
        if 'join_date' in _merchant_df.columns:
            _merchant_df['join_date'] = pd.to_datetime(_merchant_df['join_date'],
                                                       format=config.MERCHANT_JOIN_DATE_FORMAT, errors='coerce',
                                                       utc=True)

        # Load Items Data
        _items_df = pd.read_csv(config.ITEMS_CSV)
        if 'price' in _items_df.columns:
            _items_df['price'] = pd.to_numeric(_items_df['price'], errors='coerce')

        # Load Transaction Data
        _transaction_data_df = pd.read_csv(config.TRANSACTION_DATA_CSV)
        time_columns = [col for col in _transaction_data_df.columns if col.endswith("time")]
        for col in time_columns:
            _transaction_data_df[col] = pd.to_datetime(_transaction_data_df[col], utc=True)

        if 'total_amount' in _transaction_data_df.columns:
            _transaction_data_df['total_amount'] = pd.to_numeric(_transaction_data_df['total_amount'], errors='coerce')
        # Handle potential missing 'acceptance_status'
        if 'acceptance_status' not in _transaction_data_df.columns:
            print("WARNING: 'acceptance_status' column missing in transaction_data.csv. Assuming 'Accepted'.")
            _transaction_data_df['acceptance_status'] = 'Accepted'

        # Load Inventory Data
        _inventory_df = pd.read_csv(config.INVENTORY_CSV)
        if 'quantity' in _inventory_df.columns:
            _inventory_df['quantity'] = pd.to_numeric(_inventory_df['quantity'], errors='coerce')
        if 'date_updated' in _inventory_df.columns:
            _inventory_df['date_updated'] = pd.to_datetime(_inventory_df['date_updated'], errors='coerce', utc=True)

        # Load Transaction Items Data
        _transaction_items_df = pd.read_csv(config.TRANSACTION_ITEMS_CSV)  # <-- Add this block
        # Add any necessary type conversions if needed (e.g., quantity, item_price)
        if 'quantity' in _transaction_items_df.columns:
            _transaction_items_df['quantity'] = pd.to_numeric(_transaction_items_df['quantity'],
                                                              errors='coerce').fillna(0).astype(int)
        if 'item_price' in _transaction_items_df.columns:
            _transaction_items_df['item_price'] = pd.to_numeric(_transaction_items_df['item_price'], errors='coerce')

        print("Data loaded successfully.")

    except FileNotFoundError as e:
        print(f"Error loading data: {e}. Please ensure the CSV files exist at the specified paths in config.py.")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
        raise


# --- Accessor Functions ---
def get_merchant_df():
    """Returns a copy of the merchant DataFrame."""
    if _merchant_df is None:
        load_all_data()
    return _merchant_df.copy()


def get_items_df():
    """Returns a copy of the items DataFrame."""
    if _items_df is None:
        load_all_data()
    return _items_df.copy()


def get_transaction_data_df(merchant_id=None, start_date=None, end_date=None):
    """
    Returns a copy of the transaction data DataFrame, optionally filtered by merchant ID and date range.

    Args:
        merchant_id (str, optional): The ID of the merchant to filter by. Defaults to None.
        start_date (datetime or str, optional): The start date to filter by. Defaults to None.
        end_date (datetime or str, optional): The end date to filter by (exclusive). Defaults to None.
    """
    if _transaction_data_df is None:
        load_all_data()
    df = _transaction_data_df.copy()
    if merchant_id:
        df = df[df['merchant_id'] == merchant_id]
    if start_date:
        if not isinstance(start_date, pd.Timestamp):
            start_date = pd.to_datetime(start_date)
        df = df[df['order_time'] >= start_date]
    if end_date:
        if not isinstance(end_date, pd.Timestamp):
            end_date = pd.to_datetime(end_date)
        df = df[df['order_time'] < end_date]
    return df


def get_inventory_df():
    """Returns a copy of the inventory DataFrame."""
    _inventory_df = pd.read_csv(config.INVENTORY_CSV)
    if 'quantity' in _inventory_df.columns:
        _inventory_df['quantity'] = pd.to_numeric(_inventory_df['quantity'], errors='coerce')
    if 'date_updated' in _inventory_df.columns:
        _inventory_df['date_updated'] = pd.to_datetime(_inventory_df['date_updated'], errors='coerce', utc=True, format = "mixed")
    return _inventory_df.copy()


def get_notifications_df():
    """Returns a copy of the notifications DataFrame. Loads if not already loaded."""
    global _notifications_df
    _notifications_df = pd.read_csv(config.NOTIFICATIONS_CSV)
    return _notifications_df.copy()

# --- NEW Function to Save/Append Notification Rules ---
def save_notification_rule(new_rule_dict):
    """
    Appends a new notification rule dictionary to the notifications CSV file.

    Args:
        new_rule_dict (dict): A dictionary representing the new rule.
                              Must include keys: id, merchant_id, productName,
                              threshold, enabled, units.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    global _notifications_df # Access the global DataFrame to update it too

    required_keys = ['id', 'merchant_id', 'productName', 'threshold', 'enabled', 'units']
    if not all(key in new_rule_dict for key in required_keys):
        logging.error(f"Missing required keys in new_rule_dict for saving. Required: {required_keys}")
        return False

    try:
        # --- Option 1: Append directly to CSV (Simpler for single adds) ---
        # Ensure the directory exists
        os.makedirs(os.path.dirname(config.NOTIFICATIONS_CSV), exist_ok=True)
        # Create a DataFrame from the new rule
        new_rule_df = pd.DataFrame([new_rule_dict])
        # Check if file exists to determine if header should be written
        file_exists = os.path.exists(config.NOTIFICATIONS_CSV)
        # Append to CSV
        new_rule_df.to_csv(config.NOTIFICATIONS_CSV, mode='a', header=not file_exists, index=False)

        # --- Update in-memory DataFrame ---
        if _notifications_df is not None:
            _notifications_df = pd.concat([_notifications_df, new_rule_df], ignore_index=True)
            logging.info("Appended rule to in-memory notifications DataFrame.")
        else:
             # If not loaded yet, load it now so it includes the new rule next time it's accessed
             logging.info("In-memory notifications DataFrame was None, reloading all data.")
             load_all_data() # Reload all might be inefficient, could just load notifications

        logging.info(f"Appended notification rule ID {new_rule_dict.get('id')} to {config.NOTIFICATIONS_CSV}")
        return True

        # --- Option 2: Load, Append DF, Save DF (Safer but slower for single adds) ---
        # current_df = get_notifications_df() # Load current data (ensures loaded)
        # new_rule_df = pd.DataFrame([new_rule_dict])
        # updated_df = pd.concat([current_df, new_rule_df], ignore_index=True)
        # os.makedirs(os.path.dirname(config.NOTIFICATIONS_CSV), exist_ok=True)
        # updated_df.to_csv(config.NOTIFICATIONS_CSV, index=False)
        # _notifications_df = updated_df # Update in-memory version
        # logging.info(f"Saved updated notifications DataFrame ({len(updated_df)} rules) to {config.NOTIFICATIONS_CSV}")
        # return True

    except Exception as e:
        logging.error(f"Error saving notification rule to CSV: {e}", exc_info=True)
        return False

# --- TODO: Add functions for updating/deleting rules in the CSV ---
# These would typically involve loading the DF, modifying it, and saving the whole thing back
def update_notification_rule_in_csv(rule_id, merchant_id, update_data):
    """Loads CSV, updates a rule, saves CSV."""
    # Load
    df = get_notifications_df() # Use accessor to ensure it's loaded
    # Find index
    idx = df[(df['id'] == rule_id) & (df['merchant_id'] == merchant_id)].index
    if idx.empty:
        logging.warning(f"Rule ID {rule_id} for merchant {merchant_id} not found for update.")
        return False, None # Indicate not found

    # Update (add validation!)
    updated = False
    for key, value in update_data.items():
        if key in df.columns and key != 'id' and key != 'merchant_id': # Don't update id/merchant_id
            # Add validation here based on key if necessary
            df.loc[idx[0], key] = value
            updated = True

    if not updated:
        logging.info("No valid fields provided for update.")
        return True, df.loc[idx[0]].to_dict() # Return current rule, indicate no change needed saving

    # Save
    try:
        os.makedirs(os.path.dirname(config.NOTIFICATIONS_CSV), exist_ok=True)
        df.to_csv(config.NOTIFICATIONS_CSV, index=False)
        # Update global variable
        global _notifications_df
        _notifications_df = df.copy() # Update in-memory copy
        logging.info(f"Updated rule ID {rule_id} and saved to CSV.")
        return True, df.loc[idx[0]].to_dict() # Return updated rule
    except Exception as e:
        logging.error(f"Error saving updated notifications CSV: {e}", exc_info=True)
        return False, None # Indicate save failure


def delete_notification_rule_from_csv(rule_id, merchant_id):
    """Loads CSV, removes a rule, saves CSV."""
    # Load
    df = get_notifications_df() # Use accessor
    initial_len = len(df)
    # Filter out the rule
    filtered_df = df[~((df['id'] == rule_id) & (df['merchant_id'] == merchant_id))]

    if len(filtered_df) == initial_len:
        logging.warning(f"Rule ID {rule_id} for merchant {merchant_id} not found for deletion.")
        return False # Indicate not found

    # Save
    try:
        os.makedirs(os.path.dirname(config.NOTIFICATIONS_CSV), exist_ok=True)
        filtered_df.to_csv(config.NOTIFICATIONS_CSV, index=False)
         # Update global variable
        global _notifications_df
        _notifications_df = filtered_df.copy() # Update in-memory copy
        logging.info(f"Deleted rule ID {rule_id} and saved to CSV.")
        return True
    except Exception as e:
        logging.error(f"Error saving notifications CSV after deletion: {e}", exc_info=True)
        return False # Indicate save failure

# --- Helper Functions for Specific Data Retrieval ---
def get_merchants_df():
    """Alias for get_merchant_df for consistency with previous code."""
    return get_merchant_df()


def get_products_df():
    """Alias for get_items_df for consistency with previous code."""
    return get_items_df()


def get_products_df_by_merchant(merchant_id):
    """Returns a DataFrame of products specific to a given merchant."""
    items_df = get_items_df()
    return items_df[items_df['merchant_id'] == merchant_id].copy()


def update_inventory(updates):
    """
    Updates the in-memory inventory DataFrame.

    Args:
        updates (list of dict): A list where each dict contains 'product_id' and 'new_stock'.
    """
    global _inventory_df
    if _inventory_df is None:
        print("Warning: Inventory data not loaded. Cannot update.")
        return False
    try:
        update_map = {item['product_id']: item['new_stock'] for item in updates}
        _inventory_df['current_stock'] = _inventory_df.apply(
            lambda row: update_map.get(row['product_id'], row['current_stock']), axis=1
        )
        _inventory_df['last_updated'] = pd.Timestamp.now(tz='UTC')
        print("Inventory updated in memory.")
        return True
    except Exception as e:
        print(f"Error updating inventory: {e}")
        return False


if __name__ == "__main__":
    # Example usage if you want to test the loader directly
    try:
        load_all_data()
        print("\nMerchant Data:")
        print(get_merchant_df().head())
        print("\nItems Data:")
        print(get_items_df().head())
        print("\nTransaction Data:")
        print(get_transaction_data_df().head())
        print("\nInventory Data:")
        print(get_inventory_df().head())

        # Example filtering of transaction data
        merchant_transactions = get_transaction_data_df(merchant_id='1a3f7')
        print("\nTransactions for Merchant 1a3f7:")
        print(merchant_transactions.head())

    except FileNotFoundError:
        print("\nPlease ensure your CSV files are in the correct location.")
    except Exception as e:
        print(f"\nAn error occurred during the example usage: {e}")


def get_order_items_df():
    """Returns a copy of the transaction items DataFrame."""
    if _transaction_items_df is None:
        load_all_data()
    # Add filtering logic here if needed later, like for get_transaction_data_df
    return _transaction_items_df.copy()