# backend/core/metrics_calculator.py

import pandas as pd
import numpy as np
import traceback
from datetime import datetime, timedelta, date, timezone
from typing import List, Dict, Any, Tuple, Optional

# Assuming loader is accessible from this context
from backend.data_access import loader
# Assuming config might have relevant settings, though not strictly needed for these functions
# from backend import config

# --- Helper Function ---

def _filter_transactions_by_date(df: pd.DataFrame, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Filters a DataFrame with an 'order_time' column between start_date (inclusive) and end_date (exclusive)."""
    if df is None or df.empty or 'order_time' not in df.columns:
        return pd.DataFrame() # Return empty if no data or no time column

    # Ensure order_time is datetime and UTC (loader should ideally handle this)
    if not pd.api.types.is_datetime64_any_dtype(df['order_time']):
        try:
            df['order_time'] = pd.to_datetime(df['order_time'], utc=True, errors='coerce')
            df = df.dropna(subset=['order_time']) # Drop failed conversions
        except Exception:
             print("Error converting 'order_time' to datetime. Filtering might be inaccurate.")
             return pd.DataFrame() # Cannot filter reliably
    elif df['order_time'].dt.tz is None:
         df['order_time'] = df['order_time'].dt.tz_localize('UTC') # Assume UTC if naive
    elif str(df['order_time'].dt.tz) != 'UTC':
         df['order_time'] = df['order_time'].dt.tz_convert('UTC') # Convert to UTC

    # Perform filtering
    return df[(df['order_time'] >= start_date) & (df['order_time'] < end_date)]

# --- Metric Functions ---

def calculate_sales(merchant_id: str, start_date: datetime, end_date: datetime) -> float:
    """
    Calculates the total sales value for accepted orders within a date range.

    Args:
        merchant_id: The ID of the merchant.
        start_date: The start datetime of the period (inclusive, UTC).
        end_date: The end datetime of the period (exclusive, UTC).

    Returns:
        The total sales value as a float, or 0.0 if no data or errors occur.
    """
    print(f"[Metrics Calculator] Calculating sales for {merchant_id} from {start_date} to {end_date}")
    try:
        df = loader.get_transaction_data_df()
        if df is None or df.empty:
            print("[Metrics Calculator] No transaction data loaded for sales calculation.")
            return 0.0

        # Check required columns
        required_cols = ['merchant_id', 'order_time', 'order_value']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            print(f"[Metrics Calculator] Warning: Transaction data missing required columns for sales: {missing}. Returning 0.0")
            return 0.0

        # Filter by merchant and date
        merchant_df = df[df['merchant_id'] == merchant_id].copy() # Use copy to avoid SettingWithCopyWarning
        period_df = _filter_transactions_by_date(merchant_df, start_date, end_date)

        if period_df.empty:
            print(f"[Metrics Calculator] No transactions found for {merchant_id} in the specified period.")
            return 0.0

        # Handle potentially missing 'acceptance_status'
        accepted_df = pd.DataFrame()
        if 'acceptance_status' in period_df.columns:
            accepted_df = period_df[period_df['acceptance_status'] == 'Accepted']
        else:
            print("[Metrics Calculator] Warning: 'acceptance_status' column missing. Assuming all orders in period are 'Accepted' for sales calculation.")
            accepted_df = period_df # Assume all are accepted

        if accepted_df.empty:
            print(f"[Metrics Calculator] No accepted orders found for {merchant_id} in the period.")
            return 0.0

        # Calculate sum of order_value, ensuring it's numeric
        accepted_df['order_value'] = pd.to_numeric(accepted_df['order_value'], errors='coerce')
        total_sales = accepted_df['order_value'].sum()

        # Replace NaN with 0.0 if coercion failed or sum is empty
        total_sales = 0.0 if pd.isna(total_sales) else float(total_sales)

        print(f"[Metrics Calculator] Calculated sales for {merchant_id}: {total_sales:.2f}")
        return round(total_sales, 2)

    except Exception as e:
        print(f"Error calculating sales for {merchant_id}: {e}")
        traceback.print_exc()
        return 0.0 # Return 0.0 on error


def calculate_num_orders(merchant_id: str, start_date: datetime, end_date: datetime) -> int:
    """
    Calculates the total number of orders (regardless of status) within a date range.

    Args:
        merchant_id: The ID of the merchant.
        start_date: The start datetime of the period (inclusive, UTC).
        end_date: The end datetime of the period (exclusive, UTC).

    Returns:
        The total number of orders as an integer, or 0 if no data or errors occur.
    """
    print(f"[Metrics Calculator] Calculating num_orders for {merchant_id} from {start_date} to {end_date}")
    try:
        df = loader.get_transaction_data_df()
        if df is None or df.empty:
            print("[Metrics Calculator] No transaction data loaded for order count.")
            return 0

        # Check required columns
        required_cols = ['merchant_id', 'order_time']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            print(f"[Metrics Calculator] Warning: Transaction data missing required columns for order count: {missing}. Returning 0.")
            return 0

        # Filter by merchant and date
        merchant_df = df[df['merchant_id'] == merchant_id]
        period_df = _filter_transactions_by_date(merchant_df, start_date, end_date)

        num_orders = len(period_df)
        print(f"[Metrics Calculator] Calculated num_orders for {merchant_id}: {num_orders}")
        return num_orders

    except Exception as e:
        print(f"Error calculating num_orders for {merchant_id}: {e}")
        traceback.print_exc()
        return 0 # Return 0 on error


def get_sales_over_time(merchant_id: str, start_date: datetime, end_date: datetime) -> Dict[str, List]:
    """
    Calculates daily sales totals for accepted orders over a period.

    Args:
        merchant_id: The ID of the merchant.
        start_date: The start datetime of the period (inclusive, UTC).
        end_date: The end datetime of the period (exclusive, UTC).

    Returns:
        A dictionary suitable for chart libraries:
        {'labels': [date_strings], 'datasets': [{'label': 'Sales', 'data': [daily_totals]}]}
        Returns empty structure or structure with error message on failure.
    """
    print(f"[Metrics Calculator] Calculating sales_over_time for {merchant_id} from {start_date} to {end_date}")
    default_return = {'labels': [], 'datasets': []}
    try:
        df = loader.get_transaction_data_df()
        if df is None or df.empty:
             print("[Metrics Calculator] No transaction data loaded for sales trend.")
             return default_return

        # Check required columns
        required_cols = ['merchant_id', 'order_time', 'order_value']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            print(f"[Metrics Calculator] Warning: Transaction data missing required columns for sales trend: {missing}.")
            return {'error': f"Missing columns: {missing}"}


        # Filter by merchant and date range
        merchant_df = df[df['merchant_id'] == merchant_id].copy()
        period_df = _filter_transactions_by_date(merchant_df, start_date, end_date)

        if period_df.empty:
            print(f"[Metrics Calculator] No transactions found for {merchant_id} in the trend period.")
            return default_return

        # Handle potentially missing 'acceptance_status'
        accepted_df = pd.DataFrame()
        if 'acceptance_status' in period_df.columns:
            accepted_df = period_df[period_df['acceptance_status'] == 'Accepted'].copy()
        else:
            print("[Metrics Calculator] Warning: 'acceptance_status' column missing. Assuming all orders in period are 'Accepted' for sales trend.")
            accepted_df = period_df.copy() # Assume all are accepted

        if accepted_df.empty:
            print(f"[Metrics Calculator] No accepted orders found for {merchant_id} in the trend period.")
            return default_return

        # Ensure order_value is numeric
        accepted_df['order_value'] = pd.to_numeric(accepted_df['order_value'], errors='coerce').fillna(0.0)
        # Extract date part for grouping
        accepted_df['order_date'] = accepted_df['order_time'].dt.date

        # Group by date and sum sales
        daily_sales = accepted_df.groupby('order_date')['order_value'].sum()

        # Create a full date range to ensure all days are present
        all_dates = pd.date_range(start=start_date.date(), end=end_date.date() - timedelta(days=1), freq='D')
        # Reindex to include all dates, filling missing ones with 0
        daily_sales = daily_sales.reindex(all_dates.date, fill_value=0.0)

        # Format for chart
        labels = [d.strftime('%Y-%m-%d') for d in daily_sales.index]
        data = [round(s, 2) for s in daily_sales.values]

        print(f"[Metrics Calculator] Calculated sales_over_time for {merchant_id}.")
        return {
            'labels': labels,
            'datasets': [{'label': 'Sales', 'data': data}]
        }

    except Exception as e:
        print(f"Error calculating sales_over_time for {merchant_id}: {e}")
        traceback.print_exc()
        return {'error': f"Failed to calculate sales trend: {e}"}


def get_items_sold_over_time(merchant_id: str, start_date: datetime, end_date: datetime) -> Dict[str, List]:
    """
    Calculates daily quantity sold per item over a period for accepted orders.

    Args:
        merchant_id: The ID of the merchant.
        start_date: The start datetime of the period (inclusive, UTC).
        end_date: The end datetime of the period (exclusive, UTC).

    Returns:
        A dictionary suitable for chart libraries:
        {'labels': [date_strings],
         'datasets': [{'label': item_name, 'data': [daily_quantities]}, ...]}
        Returns empty structure or structure with error message on failure.
    """
    print(f"[Metrics Calculator] Calculating items_sold_over_time for {merchant_id} from {start_date} to {end_date}")
    default_return = {'labels': [], 'datasets': []}
    try:
        # 1. Load necessary data
        transactions_df = loader.get_transaction_data_df()
        order_items_df = loader.get_order_items_df()
        products_df = loader.get_products_df()

        # Basic validation of loaded dataframes
        if transactions_df is None or transactions_df.empty:
             print("[Metrics Calculator] No transaction data loaded for item trend.")
             return default_return
        if order_items_df is None or order_items_df.empty:
             print("[Metrics Calculator] No order items data loaded for item trend.")
             return default_return
        if products_df is None or products_df.empty:
             print("[Metrics Calculator] No products data loaded for item trend.")
             # Can proceed but item names will be unknown
             products_df = pd.DataFrame(columns=['item_id', 'item_name']) # Create empty to avoid error

        # 2. Check required columns
        trans_req_cols = ['merchant_id', 'order_time', 'order_id']
        items_req_cols = ['order_id', 'item_id', 'quantity'] # CRITICAL: 'quantity'
        prod_req_cols = ['item_id', 'item_name']

        if not all(col in transactions_df.columns for col in trans_req_cols):
            missing = [col for col in trans_req_cols if col not in transactions_df.columns]
            print(f"[Metrics Calculator] Warning: Transaction data missing required columns for item trend: {missing}.")
            return {'error': f"Missing transaction columns: {missing}"}
        if not all(col in order_items_df.columns for col in items_req_cols):
            missing = [col for col in items_req_cols if col not in order_items_df.columns]
            print(f"[Metrics Calculator] CRITICAL ERROR: Order items data missing required columns for item trend: {missing}. Cannot calculate quantities.")
            return {'error': f"Missing order item columns: {missing}. 'quantity' is essential."} # Specific error
        if not all(col in products_df.columns for col in prod_req_cols):
            missing = [col for col in prod_req_cols if col not in products_df.columns]
            print(f"[Metrics Calculator] Warning: Products data missing required columns for item trend: {missing}. Item names may be missing.")
            # Add missing columns with default values if possible (e.g., item_name)
            if 'item_name' not in products_df.columns and 'item_id' in products_df.columns:
                 products_df['item_name'] = 'Unknown Item (ID: ' + products_df['item_id'].astype(str) + ')'


        # 3. Filter transactions
        merchant_trans_df = transactions_df[transactions_df['merchant_id'] == merchant_id].copy()
        period_trans_df = _filter_transactions_by_date(merchant_trans_df, start_date, end_date)

        if period_trans_df.empty:
            print(f"[Metrics Calculator] No transactions found for {merchant_id} in the item trend period.")
            return default_return

        # Handle potentially missing 'acceptance_status'
        accepted_orders_df = pd.DataFrame()
        if 'acceptance_status' in period_trans_df.columns:
            accepted_orders_df = period_trans_df[period_trans_df['acceptance_status'] == 'Accepted']
        else:
            print("[Metrics Calculator] Warning: 'acceptance_status' column missing. Assuming all orders in period are 'Accepted' for item trend.")
            accepted_orders_df = period_trans_df # Assume all are accepted

        if accepted_orders_df.empty:
             print(f"[Metrics Calculator] No accepted orders found for {merchant_id} in the item trend period.")
             return default_return

        accepted_order_ids = accepted_orders_df['order_id'].unique()

        # 4. Filter order items and merge
        relevant_items_df = order_items_df[order_items_df['order_id'].isin(accepted_order_ids)].copy()
        if relevant_items_df.empty:
             print(f"[Metrics Calculator] No items found for the accepted orders in the period.")
             return default_return

        # Ensure quantity is numeric
        relevant_items_df['quantity'] = pd.to_numeric(relevant_items_df['quantity'], errors='coerce').fillna(0).astype(int)

        # Merge with product names (use left merge to keep all items even if product name is missing)
        items_with_names = pd.merge(relevant_items_df, products_df[['item_id', 'item_name']], on='item_id', how='left')
        items_with_names['item_name'] = items_with_names['item_name'].fillna('Unknown Item') # Handle missing names

        # Merge with transactions to get order_time (needed for grouping by date)
        items_with_dates = pd.merge(items_with_names, accepted_orders_df[['order_id', 'order_time']], on='order_id', how='left')
        # Ensure order_time is valid after merge
        items_with_dates = items_with_dates.dropna(subset=['order_time'])
        if items_with_dates.empty:
             print("[Metrics Calculator] Could not link items back to order dates.")
             return default_return

        items_with_dates['order_date'] = items_with_dates['order_time'].dt.date

        # 5. Group and pivot
        daily_item_sales = items_with_dates.groupby(['order_date', 'item_name'])['quantity'].sum().reset_index()

        # Pivot table: dates as index, items as columns, quantities as values
        pivot_table = daily_item_sales.pivot(index='order_date', columns='item_name', values='quantity')

        # 6. Create full date range and reindex
        all_dates = pd.date_range(start=start_date.date(), end=end_date.date() - timedelta(days=1), freq='D')
        pivot_table = pivot_table.reindex(all_dates.date, fill_value=0) # Fill missing dates/items with 0

        # 7. Format for chart output
        labels = [d.strftime('%Y-%m-%d') for d in pivot_table.index]
        datasets = []
        for item_name in pivot_table.columns:
            datasets.append({
                'label': item_name,
                'data': [int(q) for q in pivot_table[item_name].values] # Ensure integers
            })

        print(f"[Metrics Calculator] Calculated items_sold_over_time for {merchant_id}.")
        return {'labels': labels, 'datasets': datasets}

    except Exception as e:
        print(f"Error calculating items_sold_over_time for {merchant_id}: {e}")
        traceback.print_exc()
        return {'error': f"Failed to calculate item trend: {e}"}


def calculate_pareto_data(merchant_id: str, start_date: datetime, end_date: datetime) -> Dict[str, List]:
    """
    Calculates Pareto data (80/20 rule) based on item revenue for accepted orders
    within a specific period (usually a single day).

    Args:
        merchant_id: The ID of the merchant.
        start_date: The start datetime of the period (inclusive, UTC).
        end_date: The end datetime of the period (exclusive, UTC).

    Returns:
        A dictionary containing lists for Pareto chart:
        {'labels': [item_names], 'data': [item_revenues], 'cumulative': [cumulative_percentages]}
        Returns empty structure or structure with error message on failure.
    """
    print(f"[Metrics Calculator] Calculating Pareto data for {merchant_id} from {start_date} to {end_date}")
    default_return = {'labels': [], 'data': [], 'cumulative': []}
    try:
        # 1. Load necessary data
        transactions_df = loader.get_transaction_data_df()
        order_items_df = loader.get_order_items_df()
        products_df = loader.get_products_df()

        # Basic validation of loaded dataframes
        if transactions_df is None or transactions_df.empty: return default_return
        if order_items_df is None or order_items_df.empty: return default_return
        if products_df is None or products_df.empty:
             print("[Metrics Calculator] Warning: Products data missing for Pareto. Item names will be unknown.")
             products_df = pd.DataFrame(columns=['item_id', 'item_name'])

        # 2. Check required columns
        trans_req_cols = ['merchant_id', 'order_time', 'order_id']
        items_req_cols = ['order_id', 'item_id', 'quantity', 'item_price'] # CRITICAL: quantity & item_price
        prod_req_cols = ['item_id', 'item_name']

        if not all(col in transactions_df.columns for col in trans_req_cols):
            missing = [col for col in trans_req_cols if col not in transactions_df.columns]
            return {'error': f"Missing transaction columns: {missing}"}
        if not all(col in order_items_df.columns for col in items_req_cols):
            missing = [col for col in items_req_cols if col not in order_items_df.columns]
            print(f"[Metrics Calculator] CRITICAL ERROR: Order items data missing required columns for Pareto: {missing}. Cannot calculate revenue.")
            return {'error': f"Missing order item columns: {missing}. 'quantity' & 'item_price' are essential."}
        if not all(col in products_df.columns for col in prod_req_cols):
            missing = [col for col in prod_req_cols if col not in products_df.columns]
            print(f"[Metrics Calculator] Warning: Products data missing columns: {missing}. Item names may be missing.")
            if 'item_name' not in products_df.columns and 'item_id' in products_df.columns:
                 products_df['item_name'] = 'Unknown Item (ID: ' + products_df['item_id'].astype(str) + ')'

        # 3. Filter transactions
        merchant_trans_df = transactions_df[transactions_df['merchant_id'] == merchant_id].copy()
        period_trans_df = _filter_transactions_by_date(merchant_trans_df, start_date, end_date)
        if period_trans_df.empty: return default_return

        # Handle potentially missing 'acceptance_status'
        accepted_orders_df = pd.DataFrame()
        if 'acceptance_status' in period_trans_df.columns:
            accepted_orders_df = period_trans_df[period_trans_df['acceptance_status'] == 'Accepted']
        else:
            print("[Metrics Calculator] Warning: 'acceptance_status' column missing. Assuming all orders in period are 'Accepted' for Pareto.")
            accepted_orders_df = period_trans_df
        if accepted_orders_df.empty: return default_return

        accepted_order_ids = accepted_orders_df['order_id'].unique()

        # 4. Filter order items and calculate line revenue
        relevant_items_df = order_items_df[order_items_df['order_id'].isin(accepted_order_ids)].copy()
        if relevant_items_df.empty: return default_return

        # Calculate revenue per item line, handling non-numeric types
        relevant_items_df['quantity'] = pd.to_numeric(relevant_items_df['quantity'], errors='coerce').fillna(0)
        relevant_items_df['item_price'] = pd.to_numeric(relevant_items_df['item_price'], errors='coerce').fillna(0)
        relevant_items_df['line_revenue'] = relevant_items_df['quantity'] * relevant_items_df['item_price']

        # 5. Merge with product names
        items_with_names = pd.merge(relevant_items_df, products_df[['item_id', 'item_name']], on='item_id', how='left')
        items_with_names['item_name'] = items_with_names['item_name'].fillna('Unknown Item')

        # 6. Group by item name and sum revenue
        item_revenue = items_with_names.groupby('item_name')['line_revenue'].sum()

        # Filter out items with zero or negative revenue if any
        item_revenue = item_revenue[item_revenue > 0]

        if item_revenue.empty:
            print(f"[Metrics Calculator] No positive revenue items found for Pareto analysis in the period.")
            return default_return

        # 7. Sort by revenue (descending)
        item_revenue_sorted = item_revenue.sort_values(ascending=False)

        # 8. Calculate cumulative percentage
        total_revenue = item_revenue_sorted.sum()
        cumulative_revenue = item_revenue_sorted.cumsum()
        cumulative_percentage = (cumulative_revenue / total_revenue) * 100

        # 9. Format output
        labels = item_revenue_sorted.index.tolist()
        data = [round(rev, 2) for rev in item_revenue_sorted.values]
        cumulative = [round(pct, 1) for pct in cumulative_percentage.values]

        print(f"[Metrics Calculator] Calculated Pareto data for {merchant_id}.")
        return {'labels': labels, 'data': data, 'cumulative': cumulative}

    except Exception as e:
        print(f"Error calculating Pareto data for {merchant_id}: {e}")
        traceback.print_exc()
        return {'error': f"Failed to calculate Pareto data: {e}"}

# --- Optional: Add calculate_acceptance_rate and calculate_avg_prep_time if needed ---
# (Based on the anomaly detector code, these might also be useful)

def calculate_acceptance_rate(merchant_id: str, start_date: datetime, end_date: datetime) -> Optional[float]:
    """Calculates the order acceptance rate."""
    # ... (Implementation similar to anomaly detector, loading transactions,
    #      checking for 'acceptance_status', calculating rate) ...
    print(f"[Metrics Calculator] Calculating acceptance_rate for {merchant_id} (Not fully implemented in this snippet)")
    # Placeholder implementation:
    try:
        df = loader.get_transaction_data_df()
        if df is None or df.empty or 'merchant_id' not in df.columns or 'order_time' not in df.columns:
            return None
        merchant_df = df[df['merchant_id'] == merchant_id]
        period_df = _filter_transactions_by_date(merchant_df, start_date, end_date)
        if period_df.empty: return None # Or 100.0 if preferred for no orders? Or 0? None seems safest.
        if 'acceptance_status' not in period_df.columns:
             print("[Metrics Calculator] Warning: 'acceptance_status' missing for acceptance rate calculation.")
             return None # Cannot calculate without status

        total_orders = len(period_df)
        accepted_orders = len(period_df[period_df['acceptance_status'] == 'Accepted'])
        return (accepted_orders / total_orders) * 100 if total_orders > 0 else None # Avoid division by zero
    except Exception:
        traceback.print_exc()
        return None


def calculate_avg_prep_time(merchant_id: str, start_date: datetime, end_date: datetime) -> Optional[float]:
    """Calculates the average preparation time in minutes for accepted orders."""
     # ... (Implementation similar to anomaly detector, loading transactions,
    #      checking for 'prep_duration_minutes', filtering accepted, calculating mean) ...
    print(f"[Metrics Calculator] Calculating avg_prep_time for {merchant_id} (Not fully implemented in this snippet)")
     # Placeholder implementation:
    try:
        df = loader.get_transaction_data_df()
        if df is None or df.empty or 'merchant_id' not in df.columns or 'order_time' not in df.columns:
             return None
        merchant_df = df[df['merchant_id'] == merchant_id]
        period_df = _filter_transactions_by_date(merchant_df, start_date, end_date)
        if period_df.empty: return None

        accepted_df = pd.DataFrame()
        if 'acceptance_status' in period_df.columns:
             accepted_df = period_df[period_df['acceptance_status'] == 'Accepted']
        else: # Assume accepted if status missing? Risky for prep time. Better to return None.
             print("[Metrics Calculator] Warning: 'acceptance_status' missing. Cannot reliably filter for avg prep time.")
             return None
        if accepted_df.empty: return None

        if 'prep_duration_minutes' not in accepted_df.columns:
             print("[Metrics Calculator] Warning: 'prep_duration_minutes' missing. Cannot calculate avg prep time.")
             return None

        prep_times = pd.to_numeric(accepted_df['prep_duration_minutes'], errors='coerce')
        avg_prep_time = prep_times.mean() # mean() ignores NaNs by default

        return float(avg_prep_time) if pd.notna(avg_prep_time) else None

    except Exception:
         traceback.print_exc()
         return None