import pandas as pd
from backend.data_access import loader
from datetime import timedelta
import traceback

# backend/core/metrics_calculator.py
def calculate_sales(orders_df):
    accepted_orders = orders_df[orders_df['acceptance_status'] == 'Accepted']
    # Assuming your total amount column is named 'total_amount'
    if 'total_amount' in accepted_orders.columns:
        return accepted_orders['total_amount'].sum()
    else:
        print("WARNING: 'total_amount' column not found in orders data.")
        return 0.0

def get_sales_over_time(orders_df, start_date, end_date, timeframe='D'):
    """
    Calculates total sales over a specified time period.

    Args:
        orders_df (pd.DataFrame): DataFrame containing order data with 'order_time' and 'total_amount'.
        start_date (datetime): Start date of the period.
        end_date (datetime): End date of the period (exclusive).
        timeframe (str, optional): Pandas Grouper frequency string (e.g., 'D' for day, 'W' for week). Defaults to 'D'.

    Returns:
        dict: A dictionary where keys are order_time (as strings) and values are the total sales for that period.
    """
    filtered_orders = orders_df[
        (orders_df['order_time'] >= start_date) &
        (orders_df['order_time'] < end_date) &
        (orders_df['acceptance_status'] == 'Accepted')
    ].copy()

    if filtered_orders.empty:
        return {}

    sales_over_time = filtered_orders.groupby(pd.Grouper(key='order_time', freq=timeframe))['total_amount'].sum()
    # --- FIX: Convert order_time keys to strings ---
    sales_dict_str_keys = {ts.strftime('%Y-%m-%d'): value
                           for ts, value in sales_over_time.items()}
    # Return the dict with string keys
    return sales_dict_str_keys
    # --- End Fix ---

def calculate_num_orders(orders_df_filtered):
    """ Calculates number of unique accepted orders from filtered transaction data. """
    if orders_df_filtered.empty: return 0
    accepted_orders = orders_df_filtered[orders_df_filtered['acceptance_status'] == 'Accepted']
    return accepted_orders['order_id'].nunique() # Count unique order IDs

def calculate_acceptance_rate(orders_df_filtered):
    """ Calculates order acceptance rate using 'acceptance_status'. """
    if orders_df_filtered.empty: return 100.0
    # Count unique order IDs for total and accepted
    total_orders = orders_df_filtered['order_id'].nunique()
    accepted_count = orders_df_filtered[orders_df_filtered['acceptance_status'] == 'Accepted']['order_id'].nunique()
    if total_orders == 0: return 100.0
    return (accepted_count / total_orders) * 100.0

def calculate_avg_prep_time(orders_df_filtered):
            """ Calculates average prep time from the 'prep_time_minutes' column for accepted orders. """
            if orders_df_filtered.empty:
                return 0.0 # Return 0 if no orders provided

            # Filter for accepted orders that have a valid prep time
            accepted = orders_df_filtered[
                (orders_df_filtered['acceptance_status'] == 'Accepted') &
                orders_df_filtered['prep_time_minutes'].notna() & # Check if prep time exists and is not NaN
                pd.to_numeric(orders_df_filtered['prep_time_minutes'], errors='coerce').notna() # Ensure it's numeric
            ].copy()

            if accepted.empty:
                return 0.0 # Return 0 if no accepted orders with valid prep time

            # Convert to numeric just in case, coercing errors to NaN
            prep_times = pd.to_numeric(accepted['prep_time_minutes'], errors='coerce')

            # Filter out any potential non-numeric values that might have slipped through
            prep_times = prep_times.dropna()

            if prep_times.empty:
                return 0.0

            # Optional: Filter outliers (e.g., prep times > 120 mins or < 0)
            prep_times = prep_times[(prep_times >= 0) & (prep_times < 120)] # Example filter

            if prep_times.empty:
                return 0.0

            # Calculate the mean of the *existing* prep times
            return prep_times.mean()

def calculate_pareto_data(merchant_id, start_date, end_date):
    """
    Calculates Pareto data (80/20 rule) for top-selling products by revenue
    for a given merchant and time period.
    """
    try:
        # Get accepted orders for the period
        orders_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=start_date, end_date=end_date)
        accepted_orders = orders_df[orders_df['acceptance_status'] == 'Accepted']

        if accepted_orders.empty: return {"labels": [], "data": [], "cumulative": []}
        accepted_order_ids = accepted_orders['order_id'].unique()

        # Get items for these orders
        order_items_df = loader.get_order_items_df()
        # Ensure required columns exist
        if not {'order_id', 'product_id', 'quantity', 'item_price'}.issubset(order_items_df.columns):
            raise KeyError("order_items_df missing required columns for pareto")
        accepted_items = order_items_df[order_items_df['order_id'].isin(accepted_order_ids)].copy()

        if accepted_items.empty: return {"labels": [], "data": [], "cumulative": []}

        # Calculate revenue per item line
        accepted_items['revenue'] = accepted_items['quantity'] * accepted_items['item_price']

        # Get product names
        products_df = loader.get_products_df()
        if not {'product_id', 'product_name'}.issubset(products_df.columns):
             raise KeyError("products_df missing required columns for pareto")
        items_with_details = pd.merge(
            accepted_items[['product_id', 'revenue']],
            products_df[['product_id', 'product_name']],
            on='product_id', how='left'
        )
        items_with_details['product_name'] = items_with_details['product_name'].fillna('Unknown Product')

        # Calculate total revenue per product, sort descending
        item_revenue_total = items_with_details.groupby('product_name')['revenue'].sum().sort_values(ascending=False)

        if item_revenue_total.empty: return {"labels": [], "data": [], "cumulative": []}

        # Calculate cumulative percentage
        total_revenue = item_revenue_total.sum()
        if total_revenue == 0:
             return {"labels": item_revenue_total.index.tolist(), "data": item_revenue_total.values.tolist(), "cumulative": [0.0] * len(item_revenue_total)}

        cumulative_percentage = (item_revenue_total.cumsum() / total_revenue) * 100

        # Format output
        return {
            "labels": item_revenue_total.index.tolist(),
            "data": item_revenue_total.values.tolist(), # Individual revenue per product
            "cumulative": cumulative_percentage.values.tolist() # Cumulative %
        }

    except Exception as e:
        print(f"Error calculating pareto data for {merchant_id}: {e}")
        traceback.print_exc()
        return {"labels": [], "data": [], "cumulative": [], "error": str(e)}

# --- Helper to get data for a period (Adjusted) ---
def get_filtered_transaction_data(merchant_id, start_date, end_date):
    """ Filters transaction_data for a merchant and date range. """
    orders_df = loader.get_transaction_data_df()
    # Ensure dates are timezone-aware if orders_df['order_time'] is
    start_dt_aware = pd.to_datetime(start_date).tz_localize('UTC') if pd.to_datetime(start_date).tzinfo is None else pd.to_datetime(start_date)
    end_dt_aware = pd.to_datetime(end_date).tz_localize('UTC') if pd.to_datetime(end_date).tzinfo is None else pd.to_datetime(end_date)

    mask = (
        (orders_df['merchant_id'] == merchant_id) &
        (orders_df['order_time'] >= start_dt_aware) &
        (orders_df['order_time'] < end_dt_aware)
    )
    return orders_df.loc[mask]

# --- Need a function to get order items for analysis ---
def get_order_items_details(order_ids): # order_ids is likely a NumPy array here
    """ Gets item details for a list/array of order IDs, merging with product info. """
    # --- CORRECTED CHECK ---
    # Check if the numpy array has size 0 (is empty)
    if order_ids.size == 0: # <-- Use .size for NumPy arrays
    # --- END CORRECTION ---
    # if not order_ids: # <-- Old check causing ValueError
        return pd.DataFrame() # Return empty dataframe

    # --- Ensure pandas is imported ---
    # import pandas as pd (should be at top of file)

    order_items_df = loader.get_order_items_df()
    products_df = loader.get_products_df()

    # Filter items for the relevant orders
    # .isin() works correctly with NumPy arrays
    items_filtered = order_items_df[order_items_df['order_id'].isin(order_ids)]

    # Merge with product details (name, category, price)
    # Make sure product_id column name is correct in products_df
    items_details = pd.merge(
        items_filtered,
        products_df[['product_id', 'product_name', 'category', 'price']], # Ensure item_id is actually product_id if using products.csv
        on='product_id', # Ensure this matches column name in items_filtered AND products_df
        how='left'
    )
    return items_details

#NEW sebenernya ini udah ada di reporting_logic.py sih cuman belom didefine di sini
# Add this function definition within core/metrics_calculator.py
# Make sure pandas (pd) and loader are imported in metrics_calculator.py

def get_item_sales_over_time(merchant_id, start_date, end_date, timeframe='D'):
    """  # <-- Docstring immediately after function definition
    Calculates total sales revenue for each item over a specified time period
    for a given merchant.

    Args:
        merchant_id (str): The ID of the merchant.
        start_date (datetime): Start date/time of the period.
        end_date (datetime): End date/time of the period (exclusive).
        timeframe (str, optional): Pandas Grouper frequency string (e.g., 'D'). Defaults to 'D'.

    Returns:
        dict: Data structured for Chart.js {'labels': [...], 'datasets': [...]}.
              Returns empty dict if no data.
    """
    # Start the main try block for the function logic
    try:
        # --- CORRECT PLACEMENT FOR DEBUG LINE ---
        # Print the type and value JUST BEFORE the call that seems to cause the error downstream
        print(f"[DEBUG metrics_calculator] Attempting loader.get_transaction_data_df with merchant_id type: {type(merchant_id)}, value: {repr(merchant_id)}")
        # --- END DEBUG LINE ---

        # 1. Get accepted orders within the timeframe for the merchant
        # This is the line where the error seems to originate when it calls the loader
        orders_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=start_date, end_date=end_date)

        # --- Optional: Add another debug print AFTER the loader call to see if it succeeded ---
        # print(f"[DEBUG metrics_calculator] loader.get_transaction_data_df returned orders_df with shape: {orders_df.shape if isinstance(orders_df, pd.DataFrame) else 'Not a DataFrame'}")
        # ---

        accepted_orders = orders_df[orders_df['acceptance_status'] == 'Accepted'].copy()

        if accepted_orders.empty:
            return {'labels': [], 'datasets': []} # No accepted orders in period

        # ... (rest of steps 1-7 remain the same) ...

        accepted_order_ids = accepted_orders['order_id'].unique()

        # 2. Get the items associated with these accepted orders
        all_order_items_df = loader.get_order_items_df()
        order_items_filtered = all_order_items_df[all_order_items_df['order_id'].isin(accepted_order_ids)].copy()

        if order_items_filtered.empty:
             return {'labels': [], 'datasets': []}

        # 3. Calculate revenue per item line (quantity * price)
        order_items_filtered['item_revenue'] = order_items_filtered['quantity'] * order_items_filtered['item_price']

        # 4. Add the order order_time back to the item data
        items_with_order_time = pd.merge(
            order_items_filtered[['order_id', 'product_id', 'item_revenue']],
            accepted_orders[['order_id', 'order_time']],
            on='order_id',
            how='left'
        )

        # 5. Get product names
        products_df = loader.get_products_df()
        items_with_details = pd.merge(
            items_with_order_time,
            products_df[['product_id', 'product_name']],
            on='product_id',
            how='left'
        )
        items_with_details['product_name'] = items_with_details['product_name'].fillna('Unknown Product')

        # 6. Group by product name and time, summing the item revenue
        items_with_details['order_time'] = pd.to_datetime(items_with_details['order_time'])
        item_sales = items_with_details.groupby(
            ['product_name', pd.Grouper(key='order_time', freq=timeframe)]
        )['item_revenue'].sum().unstack(fill_value=0)

        if item_sales.empty:
             return {'labels': [], 'datasets': []}

        # 7. Format for Chart.js
        datasets = []
        labels = [ts.strftime('%Y-%m-%d') for ts in item_sales.columns]
        colors = [f'hsl({(i * 360 / (len(item_sales.index) + 1)) % 360}, 70%, 50%)' for i in range(len(item_sales.index))]

        for i, product in enumerate(item_sales.index):
            datasets.append({
                'label': product,
                'data': item_sales.loc[product].tolist(),
                'borderColor': colors[i],
                'fill': False
                })

        return {'labels': labels, 'datasets': datasets}

    # Keep the except block as it was, the debug print here was correct
    except Exception as e:
        print(f"[DEBUG metrics_calculator] Exception caught. merchant_id type: {type(merchant_id)}, value: {repr(merchant_id)}")
        print(f"Error calculating item sales over time for {merchant_id}: {e}") # Keep original error print
        traceback.print_exc()
        return {'labels': [], 'datasets': [], 'error': str(e)}

# --- End of function definition ---

def get_items_sold_over_time(merchant_id, start_date, end_date, timeframe='D'):
    """
    Calculates total quantity sold for each item over a specified time period
    for a given merchant. Structured for Chart.js.
    """
    try:
        orders_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=start_date, end_date=end_date)
        accepted_orders = orders_df[orders_df['acceptance_status'] == 'Accepted'].copy()

        if accepted_orders.empty: return {'labels': [], 'datasets': []}
        accepted_order_ids = accepted_orders['order_id'].unique()

        all_order_items_df = loader.get_order_items_df()
        # Ensure required columns exist in order_items_df
        if not {'order_id', 'product_id', 'quantity'}.issubset(all_order_items_df.columns):
            raise KeyError("order_items_df missing required columns (order_id, product_id, quantity)")
        order_items_filtered = all_order_items_df[all_order_items_df['order_id'].isin(accepted_order_ids)].copy()

        if order_items_filtered.empty: return {'labels': [], 'datasets': []}

        # Merge with order_time
        items_with_order_time = pd.merge(
            order_items_filtered[['order_id', 'product_id', 'quantity']], # Get quantity
            accepted_orders[['order_id', 'order_time']],
            on='order_id', how='left'
        )

        # Merge with product names
        products_df = loader.get_products_df()
        if not {'product_id', 'product_name'}.issubset(products_df.columns):
             raise KeyError("products_df missing required columns (product_id, product_name)")
        items_with_details = pd.merge(
            items_with_order_time,
            products_df[['product_id', 'product_name']],
            on='product_id', how='left'
        )
        items_with_details['product_name'] = items_with_details['product_name'].fillna('Unknown Product')

        # Grouping
        items_with_details['order_time'] = pd.to_datetime(items_with_details['order_time'])
        item_quantity_sum = items_with_details.groupby(
            ['product_name', pd.Grouper(key='order_time', freq=timeframe)]
        )['quantity'].sum().unstack(fill_value=0) # Sum quantity

        if item_quantity_sum.empty: return {'labels': [], 'datasets': []}

        # Formatting for Chart.js
        datasets = []
        labels = [ts.strftime('%Y-%m-%d') for ts in item_quantity_sum.columns]
        colors = [f'hsl({(i * 360 / (len(item_quantity_sum.index) + 1)) % 360}, 70%, 50%)' for i in range(len(item_quantity_sum.index))]

        for i, product in enumerate(item_quantity_sum.index):
            datasets.append({
                'label': product,
                'data': item_quantity_sum.loc[product].tolist(), # Use quantity data
                'borderColor': colors[i],
                'fill': False
                })

        return {'labels': labels, 'datasets': datasets}

    except Exception as e:
        print(f"Error calculating item quantity sold over time for {merchant_id}: {e}")
        traceback.print_exc()
        return {'labels': [], 'datasets': [], 'error': str(e)}
