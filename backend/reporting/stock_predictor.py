import pandas as pd
import traceback
from datetime import datetime, timedelta, timezone
from backend.data_access import loader
from backend import config

def predict_stock_runout(merchant_id, lookback_days=7):
    """ Predicts which items might run out of stock soon based on quantity sold. """
    forecast = []
    try:
        inventory_df = loader.get_inventory_df()
        products_df = loader.get_products_df()
        orders_df = loader.get_transaction_data_df()
        order_items_df = loader.get_order_items_df() # Correctly loaded

        # --- DEBUG ---
        print("[DEBUG stock_predictor] Loaded order_items_df columns:", order_items_df.columns.tolist())
        if 'product_id' not in order_items_df.columns:
             print("[ERROR stock_predictor] 'product_id' is MISSING from order_items_df AFTER loading!")
             return forecast # Cannot proceed
        # --- END DEBUG ---


        # Get current stock for the merchant
        merchant_products = products_df[products_df['merchant_id'] == merchant_id]
        # Verify columns before merge
        if 'product_id' not in inventory_df.columns: raise KeyError("inventory_df missing 'product_id'")
        if 'product_id' not in merchant_products.columns: raise KeyError("merchant_products missing 'product_id'")

        current_stock = pd.merge(inventory_df, merchant_products[['product_id','product_name']], on='product_id', how='inner')
        if current_stock.empty: return forecast

        # --- Calculate recent average daily sales QUANTITY ---
        end_date = pd.Timestamp(datetime.now(timezone(timedelta(hours=8))).date(), tz='UTC')
        start_date = end_date - timedelta(days=lookback_days)

        # Filter relevant accepted orders within the time range
        recent_orders_filtered = orders_df[
            (orders_df['merchant_id'] == merchant_id) &
            (orders_df['timestamp'] >= start_date) &
            (orders_df['timestamp'] < end_date) &
            (orders_df['acceptance_status'] == 'Accepted')
        ]

        # Handle case where there are NO accepted orders in the period
        if recent_orders_filtered.empty:
             print(f"[DEBUG stock_predictor] No accepted orders found for {merchant_id} in lookback period.")
             low_no_sales = current_stock[current_stock['current_stock'] < config.LOW_STOCK_THRESHOLD * 2]
             for _, item in low_no_sales.iterrows():
                  forecast.append({
                      "product_name": item['product_name'],
                      "current_stock": int(item['current_stock']),
                      "days_left_forecast": "N/A (No recent sales)"
                  })
             return forecast

        # --- CORRECTED LOGIC: Use order_items_df ---
        # Get the IDs of the accepted orders in the recent period
        recent_order_ids = recent_orders_filtered['order_id'].unique()

        # Filter order_items_df to get items ONLY from those recent, accepted orders
        recent_items = order_items_df[order_items_df['order_id'].isin(recent_order_ids)].copy()

        # Handle case where recent orders had NO items (unlikely but possible)
        if recent_items.empty:
            print(f"[DEBUG stock_predictor] No items found for recent accepted orders for {merchant_id}.")
            # Apply same "no sales" logic as above
            low_no_sales = current_stock[current_stock['current_stock'] < config.LOW_STOCK_THRESHOLD * 2]
            for _, item in low_no_sales.iterrows():
                  forecast.append({
                      "product_name": item['product_name'],
                      "current_stock": int(item['current_stock']),
                      "days_left_forecast": "N/A (No recent sales)"
                  })
            return forecast

        # Now, group the filtered recent_items DataFrame
        # Ensure columns exist before grouping
        if 'product_id' not in recent_items.columns: raise KeyError("recent_items missing 'product_id'")
        if 'quantity' not in recent_items.columns: raise KeyError("recent_items missing 'quantity'")

        item_sales_qty = recent_items.groupby('product_id')['quantity'].sum().reset_index()
        # --- END CORRECTED LOGIC ---

        item_sales_qty['avg_daily_sales'] = item_sales_qty['quantity'] / lookback_days

        # --- Merge average sales with current stock ---
        # Verify column before merge
        if 'product_id' not in item_sales_qty.columns: raise KeyError("item_sales_qty missing 'product_id'")
        stock_analysis = pd.merge(current_stock, item_sales_qty[['product_id', 'avg_daily_sales']], on='product_id', how='left')
        stock_analysis['avg_daily_sales'] = stock_analysis['avg_daily_sales'].fillna(0)

        # --- Calculate days left ---
        stock_analysis['days_left'] = stock_analysis.apply(
            lambda row: round(row['current_stock'] / row['avg_daily_sales']) if row['avg_daily_sales'] > 0 else 999,
            axis=1
        )

        # --- Filter for items running out soon ---
        running_out_soon = stock_analysis[stock_analysis['days_left'] <= config.STOCK_FORECAST_DAYS].sort_values('days_left')

        # Format output
        for _, item in running_out_soon.iterrows():
            forecast.append({
                "product_name": item['product_name'],
                "current_stock": int(item['current_stock']),
                "days_left_forecast": int(item['days_left'])
            })

    except KeyError as e:
         print(f"KeyError during stock prediction: {e}. Check CSV column names and joins.")
         # traceback.print_exc() # Uncomment for more detail if needed
    except Exception as e:
        print(f"Error predicting stock runout: {e}")
        # traceback.print_exc() # Uncomment for more detail if needed

    return forecast

def check_low_stock_alerts(merchant_id, low_stock_threshold=None):
    """ Checks for items with current stock below the threshold. """
    if low_stock_threshold is None:
        low_stock_threshold = config.LOW_STOCK_THRESHOLD

    inventory_df = loader.get_inventory_df()
    products_df = loader.get_products_df_by_merchant(merchant_id) # Ensure this filters by merchant
    if inventory_df.empty or products_df.empty:
        return []

    low_stock_items = pd.merge(inventory_df[inventory_df['current_stock'] <= low_stock_threshold],
                                products_df[['product_id', 'product_name']],
                                on='product_id', how='inner')

    alerts = []
    stock_forecast = predict_stock_runout(merchant_id)
    forecast_map = {item['product_name']: item['days_left_forecast'] for item in stock_forecast}

    for _, item in low_stock_items.iterrows():
        forecast_days = forecast_map.get(item['product_name'], "N/A")
        alerts.append({
            "product_name": item['product_name'],
            "current_stock": int(item['current_stock']),
            "days_left_forecast": forecast_days
        })
    return alerts

if __name__ == "__main__":
    merchant_id_to_check = '1a3f7'
    forecast = predict_stock_runout(merchant_id_to_check)
    print(f"\n--- Stock Forecast for Merchant {merchant_id_to_check} ---")
    for item in forecast:
        print(item)

    low_stock = check_low_stock_alerts(merchant_id_to_check)
    print(f"\n--- Low Stock Alerts for Merchant {merchant_id_to_check} (Threshold: {config.LOW_STOCK_THRESHOLD if hasattr(config, 'LOW_STOCK_THRESHOLD') else 'Not Defined'}) ---")
    for item in low_stock:
        print(item)