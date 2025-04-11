import pandas as pd
import traceback
from datetime import date, timedelta
from . import metrics_calculator
from data_access import loader
from backend import config

def detect_anomalies(merchant_id):
    detected_anomalies = []
    today = date.today()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    start_of_yesterday = pd.Timestamp(yesterday, tz='UTC')
    start_of_today = pd.Timestamp(today, tz='UTC')
    start_of_day_before = pd.Timestamp(day_before_yesterday, tz='UTC')

    try:
        # Use the correct filtering function
        orders_yesterday_df = metrics_calculator.get_filtered_transaction_data(merchant_id, start_of_yesterday, start_of_today)
        orders_day_before_df = metrics_calculator.get_filtered_transaction_data(merchant_id, start_of_day_before, start_of_yesterday)
    except Exception as e:
        print(f"Error getting data for anomaly detection: {e}")
        return []

    # --- Calculate Metrics ---
    sales_yesterday = metrics_calculator.calculate_sales(orders_yesterday_df)
    sales_day_before = metrics_calculator.calculate_sales(orders_day_before_df)
    prep_time_yesterday = metrics_calculator.calculate_avg_prep_time(orders_yesterday_df)
    acceptance_rate_yesterday = metrics_calculator.calculate_acceptance_rate(orders_yesterday_df)
    # TODO: Calculate baselines for prep time, etc.

    # --- Check for Anomalies ---

    # 1. Sales Drop (DoD)
    if sales_day_before > 0:
        sales_change_percent = ((sales_yesterday - sales_day_before) / sales_day_before) * 100
        if sales_change_percent < config.SALES_DROP_THRESHOLD_PERCENT:
            # --- Segmentation for Sales Drop ---
            segmentation_info = get_sales_drop_segmentation(
                orders_yesterday_df['order_id'].unique(), # Pass unique order IDs
                orders_day_before_df['order_id'].unique()
            )
            detected_anomalies.append({
                "type": "sales_drop_dod", "metric": "Sales",
                "current_value": sales_yesterday, "baseline_value": sales_day_before,
                "change_percent": round(sales_change_percent, 1), "period": "Day-over-Day",
                "segmentation_info": segmentation_info # Add segmentation results
            })

    # 2. Prep Time Increase (Placeholder - needs baseline)
    # ...

    # 3. Low Acceptance Rate
    if acceptance_rate_yesterday < config.ACCEPTANCE_RATE_THRESHOLD_PERCENT:
         # TODO: Add time-based segmentation if possible
         detected_anomalies.append({
             "type": "low_acceptance_rate", "metric": "Acceptance Rate",
             "current_value": round(acceptance_rate_yesterday, 1),
             "threshold": config.ACCEPTANCE_RATE_THRESHOLD_PERCENT, "period": "Yesterday",
             "segmentation_info": "Check specific times if pattern persists." # Placeholder
         })

    # 4. Low Stock (Adjusted)
    inventory_df = loader.get_inventory_df()
    products_df = loader.get_products_df() # Use items_df alias if preferred
    merchant_products = products_df[products_df['merchant_id'] == merchant_id]
    current_inventory = pd.merge(inventory_df, merchant_products, on='product_id', how='inner')
    low_stock_items = current_inventory[current_inventory['current_stock'] < config.LOW_STOCK_THRESHOLD]

    if not low_stock_items.empty:
        # TODO: Prioritize based on sales rank (needs sales data per item)
        for _, item in low_stock_items.head(3).iterrows(): # Limit alerts
             detected_anomalies.append({
                 "type": "low_stock", "metric": "Inventory",
                 "product_id": item['item_id'], # Use correct column name
                 "product_name": item['product_name'],
                 "current_value": item['current_stock'],
                 "threshold": config.LOW_STOCK_THRESHOLD
             })

    return detected_anomalies

def get_sales_drop_segmentation(order_ids_current, order_ids_baseline):
    """ Analyzes item/category contribution to sales drop. """
    try:
        items_current = metrics_calculator.get_order_items_details(order_ids_current)
        items_baseline = metrics_calculator.get_order_items_details(order_ids_baseline)

        if items_current.empty or items_baseline.empty:
            return "Not enough data for segmentation."

        # Calculate total sales per category/item for both periods
        sales_current_cat = items_current.groupby('category')['price'].sum()
        sales_baseline_cat = items_baseline.groupby('category')['price'].sum()
        # Use .reindex().fillna() for robust alignment before subtraction
        sales_change_cat = (sales_current_cat.reindex(sales_baseline_cat.index.union(sales_current_cat.index), fill_value=0) -
                            sales_baseline_cat.reindex(sales_baseline_cat.index.union(sales_current_cat.index), fill_value=0))
        sales_change_cat = sales_change_cat.sort_values() # Sort after calculation

        sales_current_item = items_current.groupby(['category','product_name'])['price'].sum()
        sales_baseline_item = items_baseline.groupby(['category','product_name'])['price'].sum()
        # Use .reindex().fillna() for robust alignment before subtraction
        sales_change_item = (sales_current_item.reindex(sales_baseline_item.index.union(sales_current_item.index), fill_value=0) -
                             sales_baseline_item.reindex(sales_baseline_item.index.union(sales_current_item.index), fill_value=0))
        sales_change_item = sales_change_item.sort_values() # Sort after calculation


        # Find biggest drops safely
        biggest_cat_drop = "N/A"
        # Check if the Series is not empty AND if its minimum value is actually negative
        if not sales_change_cat.empty and (sales_change_cat.min() < 0):
             biggest_cat_drop = sales_change_cat.idxmin()

        biggest_item_drop_tuple = None # Use None initially
        # Check if the Series is not empty AND if its minimum value is actually negative
        if not sales_change_item.empty and (sales_change_item.min() < 0):
             biggest_item_drop_tuple = sales_change_item.idxmin() # idxmin returns the index (tuple here)


        # Construct reason string
        if biggest_cat_drop != "N/A":
             reason = f"Sales drop seems most significant in the '{biggest_cat_drop}' category. "
             # Check if we also found a specific item drop
             if biggest_item_drop_tuple is not None and isinstance(biggest_item_drop_tuple, tuple) and len(biggest_item_drop_tuple) > 1:
                  reason += f"Specifically, item '{biggest_item_drop_tuple[1]}' saw a notable decrease."
             elif biggest_item_drop_tuple is not None: # Handle if index isn't tuple as expected
                  reason += f"A specific item ({biggest_item_drop_tuple}) saw a notable decrease."
        elif biggest_item_drop_tuple is not None and isinstance(biggest_item_drop_tuple, tuple) and len(biggest_item_drop_tuple) > 1:
             # Case where category drop wasn't clear but item drop was
             reason = f"Sales drop seems driven primarily by item '{biggest_item_drop_tuple[1]}' in category '{biggest_item_drop_tuple[0]}'."
        else:
             reason = "Could not pinpoint a specific category or item driving the sales drop." # Fallback

        return reason.strip()

    except Exception as e:
        print(f"Error in segmentation: {e}")
        traceback.print_exc() # Print traceback for segmentation errors
        return "Could not determine main drivers due to an error."