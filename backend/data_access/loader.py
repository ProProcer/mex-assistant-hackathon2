import pandas as pd
from backend import config
from datetime import datetime, date
import traceback


# Global variables to store loaded DataFrames
_merchant_df = None
_items_df = None
_transaction_data_df = None
_inventory_df = None
_transaction_items_df = None  # <-- Add this


def load_all_data():
    """Loads all data from CSV files into pandas DataFrames."""
    global _merchant_df, _items_df, _transaction_data_df, _inventory_df, _transaction_items_df

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