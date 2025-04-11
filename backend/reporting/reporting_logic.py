import pandas as pd
from datetime import datetime, timedelta

def load_orders_data():
    try:
        return pd.read_csv('orders.csv', parse_dates=['timestamp'])
    except FileNotFoundError:
        print("Error: orders.csv not found.")
        return pd.DataFrame()

def load_products_data():
    try:
        return pd.read_csv('products.csv')
    except FileNotFoundError:
        print("Error: products.csv not found.")
        return pd.DataFrame()

def load_inventory_data():
    try:
        return pd.read_csv('inventory.csv')
    except FileNotFoundError:
        print("Error: inventory.csv not found.")
        return pd.DataFrame()

def calculate_sales(orders_df):
    """Calculates total sales for accepted orders."""
    accepted_orders = orders_df[orders_df['acceptance_status'] == 'Accepted']
    return accepted_orders['total_amount'].sum()

def calculate_num_orders(orders_df):
    """Calculates the number of unique accepted orders."""
    accepted_orders = orders_df[orders_df['acceptance_status'] == 'Accepted']
    return accepted_orders['order_id'].nunique()

def get_sales_over_time(orders_df, start_date, end_date, timeframe='D'):
    """Calculates sales over a specified time period."""
    filtered_orders = orders_df[(orders_df['timestamp'] >= start_date) & (orders_df['timestamp'] < end_date) & (orders_df['acceptance_status'] == 'Accepted')]
    sales_over_time = filtered_orders.groupby(pd.Grouper(key='timestamp', freq=timeframe))['total_amount'].sum()
    return sales_over_time.to_dict()

def get_item_sales_over_time(orders_df, start_date, end_date, products_df, timeframe='D'):
    """Calculates sales of each item over a specified time period."""
    filtered_orders = orders_df[(orders_df['timestamp'] >= start_date) & (orders_df['timestamp'] < end_date) & (orders_df['acceptance_status'] == 'Accepted')]
    merged_df = pd.merge(filtered_orders, products_df, on='product_id')
    item_sales = merged_df.groupby(['product_name', pd.Grouper(key='timestamp', freq=timeframe)])['total_amount'].sum().unstack(fill_value=0)
    datasets = []
    labels = [ts.strftime('%Y-%m-%d') for ts in item_sales.columns]
    for product in item_sales.index:
        datasets.append({'label': product, 'data': item_sales.loc[product].tolist()})
    return {'labels': labels, 'datasets': datasets}

def get_top_product_by_quantity(orders_df):
    """Identifies the top-selling product based on quantity."""
    top_product = orders_df[orders_df['acceptance_status'] == 'Accepted'].groupby('product_id')['quantity'].sum().sort_values(ascending=False).index[0]
    products_df = load_products_data()
    product_name = products_df[products_df['product_id'] == top_product]['product_name'].iloc[0] if not products_df.empty and not pd.isna(top_product) else "N/A"
    return product_name

def project_stock(inventory_df, orders_df, sales_history_days=7):
    """Projects stock levels based on average daily sales."""
    stock_projection = {}
    today = datetime.now(datetime.timezone(timedelta(hours=8))).date()
    start_date = today - timedelta(days=sales_history_days)
    recent_orders = orders_df[(orders_df['timestamp'].dt.date >= start_date) & (orders_df['timestamp'].dt.date <= today) & (orders_df['acceptance_status'] == 'Accepted')]
    daily_sales = recent_orders.groupby('product_id')['quantity'].sum() / sales_history_days
    inventory_map = inventory_df.set_index('product_id')['current_stock'].to_dict()

    for product_id, current_stock in inventory_map.items():
        avg_daily_sale = daily_sales.get(product_id, 0)
        if avg_daily_sale > 0:
            days_remaining = current_stock / avg_daily_sale
            stock_projection[product_id] = f"{days_remaining:.2f}"
        else:
            stock_projection[product_id] = "N/A"
    return stock_projection

def check_low_stock_alerts(inventory_df, projected_stock, low_stock_threshold=10):
    """Checks for low stock items."""
    low_stock_alerts = []
    inventory_map = inventory_df.set_index('product_id')['current_stock'].to_dict()
    products_df = load_products_data()
    product_name_map = products_df.set_index('product_id')['product_name'].to_dict()

    for product_id, current_stock in inventory_map.items():
        if current_stock <= low_stock_threshold:
            product_name = product_name_map.get(product_id, "Unknown")
            projected_remaining = projected_stock.get(product_id, "N/A")
            low_stock_alerts.append({
                'product_id': product_id,
                'product_name': product_name,
                'current_stock': current_stock,
                'projected_remaining': projected_remaining
            })
    return low_stock_alerts

if __name__ == "__main__":
    orders_df = load_orders_data()
    products_df = load_products_data()
    inventory_df = load_inventory_data()

    if not orders_df.empty and not products_df.empty and not inventory_df.empty:
        today = datetime.now(datetime.timezone(timedelta(hours=8))).date()
        yesterday = today - timedelta(days=1)

        daily_report = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_sales': calculate_sales(orders_df[orders_df['timestamp'].dt.date == yesterday]),
            'total_orders': calculate_num_orders(orders_df[orders_df['timestamp'].dt.date == yesterday]),
            'sales_trend': get_sales_over_time(orders_df, yesterday - timedelta(days=6), today),
            'item_sales_trend': get_item_sales_over_time(orders_df, yesterday - timedelta(days=6), today, products_df),
            'pareto_data': calculate_pareto_data(orders_df[orders_df['timestamp'].dt.date == yesterday], products_df),
            'top_product_quantity': get_top_product_by_quantity(orders_df[orders_df['timestamp'].dt.date == yesterday]),
            'stock_projection': project_stock(inventory_df, orders_df),
            'low_stock_alerts': check_low_stock_alerts(inventory_df, project_stock(inventory_df, orders_df))
        }
        print("\n--- Daily Report ---")
        for key, value in daily_report.items():
            print(f"{key}: {value}")