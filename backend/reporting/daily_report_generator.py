import sys
import os
import traceback
import pandas as pd
from datetime import date, timedelta, datetime, timezone
from backend.data_access import loader
from backend.core import metrics_calculator
from backend import config
from backend.reporting import stock_predictor
from typing import Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def _find_latest_transaction_date(merchant_id: str, max_lookback_days: int = 1095) -> Optional[date]:
    """
    Finds the most recent date with transaction data for the merchant
    within the specified lookback period.
    """
    print(f"[Latest Date Finder] Searching for latest transaction date for {merchant_id} (max lookback: {max_lookback_days} days)")
    try:
        # Define the search window
        today = datetime.now(timezone.utc).date()
        search_start_date = today - timedelta(days=max_lookback_days)
        search_end_date = today + timedelta(days=1) # Include today up to the end

        # Load transaction data for the merchant within the lookback window
        # Select only the 'order_time' column for efficiency
        transactions_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=search_start_date, end_date=search_end_date)

        if transactions_df is None or transactions_df.empty:
            print(f"[Latest Date Finder] No transactions found for {merchant_id} in the last {max_lookback_days} days.")
            return None

        # Ensure 'order_time' is datetime and timezone-aware (UTC)
        if not pd.api.types.is_datetime64_any_dtype(transactions_df['order_time']):
             transactions_df['order_time'] = pd.to_datetime(transactions_df['order_time'], errors='coerce', utc=True)
             transactions_df.dropna(subset=['order_time'], inplace=True)

        if transactions_df.empty: # Check again after potential drops
             print(f"[Latest Date Finder] No valid transaction dates found after conversion/dropna.")
             return None

        if transactions_df['order_time'].dt.tz is None:
            transactions_df['order_time'] = transactions_df['order_time'].dt.tz_localize('UTC')
        elif transactions_df['order_time'].dt.tz != timezone.utc:
             transactions_df['order_time'] = transactions_df['order_time'].dt.tz_convert('UTC')


        # Find the maximum date part
        latest_timestamp = transactions_df['order_time'].max()

        if pd.isna(latest_timestamp):
            print(f"[Latest Date Finder] Max timestamp calculation resulted in NaT.")
            return None

        latest_date_found = latest_timestamp.date()
        print(f"[Latest Date Finder] Latest transaction date found: {latest_date_found.strftime('%Y-%m-%d')}")
        return latest_date_found

    except Exception as e:
        print(f"[Latest Date Finder] Error finding latest transaction date: {e}")
        traceback.print_exc()
        return None


def generate_daily_report(merchant_id, report_date):
    """Generates the complete daily report object, using the latest available data if needed."""
    print(f"Starting daily_report generation request for {merchant_id} targeting {report_date.strftime('%Y-%m-%d')}")

    LOOKBACK_DAYS_FOR_LATEST = 1095

    print(f"Starting daily_report generation request for {merchant_id} (initial target: {report_date.strftime('%Y-%m-%d')})")

    # --- Determine Effective Report Date ---
    effective_report_date = _find_latest_transaction_date(merchant_id, LOOKBACK_DAYS_FOR_LATEST)


    if effective_report_date is None:
        # No data found within the lookback period
        error_msg = f"No recent transaction data found for {merchant_id} in the last {LOOKBACK_DAYS_FOR_LATEST} days to generate a report."
        print(f"[Report Error] {error_msg}")
        return {
            "report_date": report_date.strftime('%Y-%m-%d'), # Report the initially requested date
            "error": error_msg,
            "basic_info": None,
            "sales_on_report_date": 0,
            "orders_on_report_date": 0,
            "sales_trend_data": {},
            "item_quantity_trend_data": {'labels': [], 'datasets': []},
            "stock_forecast": [],
            "low_stock_alerts": [],
            "top_products_pareto_today": {'labels': [], 'data': [], 'cumulative': []},
            "word_of_encouragement": None
        }

    # --- Proceed with Report Generation using effective_report_date ---
    report_data = {
        # IMPORTANT: Use the EFFECTIVE date here so the AI knows which date the data belongs to
        "report_date": effective_report_date.strftime('%Y-%m-%d'),
        "error": None
    }
    print(f"Generating report using data for effective date: {effective_report_date.strftime('%Y-%m-%d')}")

   # Define date ranges based on the *effective* date
    report_day_start = pd.Timestamp(effective_report_date, tz='UTC')
    report_day_end = report_day_start + timedelta(days=1)
    # Trend data should look back from the start of the effective report day
    trend_start_date = report_day_start - timedelta(days=config.SALES_TREND_DAYS)

    report_data = {"report_date": report_date.strftime('%Y-%m-%d'), "error": None}

    try:
         # --- Basic Info & Maturity (Unchanged) ---
        merchant_df = loader.get_merchants_df()
        if merchant_df.empty or merchant_id not in merchant_df['merchant_id'].values:
            report_data["error"] = f"Merchant with ID '{merchant_id}' not found."
            print(report_data["error"])
            report_data["basic_info"] = None
            return report_data
        
        merchant_info = merchant_df[merchant_df['merchant_id'] == merchant_id].iloc[0]

        join_date_str = merchant_info.get("join_date", None)
        business_maturity_years = "N/A"
        if join_date_str and pd.notna(join_date_str):
            try:
                join_dt = pd.to_datetime(join_date_str, format=config.MERCHANT_JOIN_DATE_FORMAT, errors='coerce')
                if pd.notna(join_dt):
                    join_dt_aware = join_dt.tz_localize('UTC') if join_dt.tzinfo is None else join_dt.tz_convert('UTC')
                    maturity_delta = datetime.now(timezone.utc) - join_dt_aware
                    business_maturity_years = round(maturity_delta.days / 365.25, 1)
            except Exception as maturity_err:
                print(f"Could not calculate maturity: {maturity_err}")
                business_maturity_years = "Error"

        report_data["basic_info"] = {
            "merchant_name": merchant_info.get("merchant_name", "N/A"),
            "merchant_type": merchant_info.get("merchant_type", "N/A"), # From merchant.csv
            "cuisine_type": merchant_info.get("cuisine_type", "N/A"), # From merchant.csv
            "location": merchant_info.get("city_name", "N/A"), # Use city_name as Location
            "business_maturity_years": business_maturity_years # Calculated
            # Add 'scale' based on research if possible/needed
        }
        print("Basic info processed.")

        # --- Metrics for the Effective Report Day (Unchanged logic, uses effective date ranges) ---
        orders_report_day_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=report_day_start, end_date=report_day_end)
        report_data["sales_on_report_date"] = metrics_calculator.calculate_sales(orders_report_day_df)
        report_data["orders_on_report_date"] = metrics_calculator.calculate_num_orders(orders_report_day_df)
        print(f"Metrics for effective report date ({effective_report_date.strftime('%Y-%m-%d')}) processed.")

       # --- Trend Data (Looking Back from effective_report_date) (Unchanged logic) ---
        all_orders_trend_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=trend_start_date, end_date=report_day_start)
        report_data["sales_trend_data"] = metrics_calculator.get_sales_over_time(all_orders_trend_df, trend_start_date, report_day_start)
        print("Sales over time processed.")

        report_data["item_quantity_trend_data"] = metrics_calculator.get_items_sold_over_time(
            merchant_id, trend_start_date, report_day_start
        )
        print("Item quantity over time processed.")

        # --- Stock Forecast ---
        report_data["stock_forecast"] = stock_predictor.predict_stock_runout(merchant_id)
        report_data["low_stock_alerts"] = stock_predictor.check_low_stock_alerts(merchant_id)
        print("Stock forecast processed.")

        # --- Pareto Analysis (For the Report Day) ---
        report_data["top_products_pareto_today"] = metrics_calculator.calculate_pareto_data(
            merchant_id, report_day_start, report_day_end
        )
        print(f"Pareto data for effective date ({effective_report_date.strftime('%Y-%m-%d')}) processed.")

        report_data["word_of_encouragement"] = config.ENCOURAGEMENT_MESSAGE
        print("Encouragement message added.")
        print(f"Finished daily_report generation for {merchant_id} using effective date {effective_report_date.strftime('%Y-%m-%d')}")

    except Exception as e:
        # --- Error Handling (Unchanged logic, reports error for the effective date) ---
        print(f"Error during report generation details for date {effective_report_date.strftime('%Y-%m-%d')}: {e}")
        traceback.print_exc()
        report_data["error"] = f"Failed to generate full report details for {effective_report_date.strftime('%Y-%m-%d')}: {e}"

    return report_data # Return the complete dictionary