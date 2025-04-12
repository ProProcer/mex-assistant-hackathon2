import sys
import os
import traceback
import pandas as pd
from datetime import date, timedelta, datetime, timezone
from typing import Optional, Dict, Any, List # Added List

# Assuming these modules exist and function as described/updated
from backend.data_access import loader
from backend.core import metrics_calculator
from backend import config
from backend.reporting import stock_predictor # Assuming this exists


# Add project root to Python path - adjust if your structure differs
# This allows running the script directly while importing backend modules
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError:
     # Handle case where __file__ is not defined (e.g., interactive session)
     print("Warning: Could not automatically add project root to sys.path.")


def _find_latest_transaction_date(merchant_id: str) -> Optional[date]:
    """
    Finds the latest transaction date for a given merchant based on order_time.

    Args:
        merchant_id: The ID of the merchant to query.

    Returns:
        The date (datetime.date object) of the latest transaction, or None if
        no transactions are found or required columns are missing/invalid.

    Raises:
        KeyError: If 'merchant_id' or 'order_time' columns are missing.
        # May raise other exceptions depending on the loader implementation.
    """
    print(f"Finding latest transaction date for merchant '{merchant_id}'...")
    try:
        # 1. Get the transaction data DataFrame
        df = loader.get_transaction_data_df()
        if df is None or df.empty:
            print(f"Warning: No transaction data loaded.")
            return None

        # 2. Validate required columns
        required_cols = ['merchant_id', 'order_time']
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            raise KeyError(f"Transaction DataFrame missing required column(s): {missing_cols}")

        # 3. Ensure 'order_time' is datetime (loader should ideally handle this)
        # Add conversion if loader doesn't guarantee UTC datetime
        if not pd.api.types.is_datetime64_any_dtype(df['order_time']):
            print("Warning: 'order_time' column is not datetime. Attempting conversion...")
            df['order_time'] = pd.to_datetime(df['order_time'], utc=True, errors='coerce')
            # Drop rows where conversion failed, as they can't be used for max()
            df = df.dropna(subset=['order_time'])
        # Ensure timezone is UTC if it's datetime but potentially naive or other tz
        elif df['order_time'].dt.tz is None:
             print("Warning: 'order_time' is naive datetime. Assuming UTC.")
             df['order_time'] = df['order_time'].dt.tz_localize('UTC')
        elif str(df['order_time'].dt.tz) != 'UTC':
             print(f"Warning: 'order_time' has timezone {df['order_time'].dt.tz}. Converting to UTC.")
             df['order_time'] = df['order_time'].dt.tz_convert('UTC')


        # 4. Filter for the specific merchant
        merchant_transactions = df[df['merchant_id'] == merchant_id]

        # 5. Check if any transactions were found
        if merchant_transactions.empty:
            print(f"No transactions found for merchant '{merchant_id}'.")
            return None

        # 6. Find the maximum 'order_time'
        latest_timestamp = merchant_transactions['order_time'].max()
        # Check if max() returned NaT (can happen if all times were NaT after coerce)
        if pd.isna(latest_timestamp):
             print(f"Could not determine latest transaction time for merchant '{merchant_id}' (likely data issue).")
             return None

        # 7. Extract and return the date part (already UTC)
        latest_date = latest_timestamp.date()
        print(f"Latest transaction date found: {latest_date.strftime('%Y-%m-%d')}")
        return latest_date

    except KeyError as e:
        print(f"Error finding latest transaction date: {e}")
        traceback.print_exc() # Log full traceback for debugging
        raise # Re-raise critical errors like missing columns
    except Exception as e:
        print(f"An unexpected error occurred in _find_latest_transaction_date: {e}")
        traceback.print_exc()
        # Decide whether to return None or raise depending on severity
        return None


def generate_daily_report(merchant_id: str, requested_report_date: datetime) -> Dict[str, Any]:
    """
    Generates the complete daily report object for a merchant, using data
    from the most recent day with transactions if available.

    Args:
        merchant_id: The ID of the merchant.
        requested_report_date: The target date for the report (timezone-naive assumed,
                               will be handled as UTC internally).

    Returns:
        A dictionary containing the daily report data or an error message.
    """
    # Ensure requested date is treated as UTC internally, even if naive was passed
    if requested_report_date.tzinfo is None:
        requested_report_date_utc = requested_report_date.replace(tzinfo=timezone.utc)
    else:
        requested_report_date_utc = requested_report_date.astimezone(timezone.utc)

    print(f"Starting daily report generation request for merchant '{merchant_id}' (Requested date: {requested_report_date_utc.strftime('%Y-%m-%d')})")

    # --- Determine Effective Report Date ---
    effective_report_date: Optional[date] = None
    try:
        effective_report_date = _find_latest_transaction_date(merchant_id)
    except Exception as e:
        # Catch errors from _find_latest_transaction_date (like KeyError)
         error_msg = f"Failed to determine latest transaction date for merchant '{merchant_id}': {e}"
         print(f"[Report Error] {error_msg}")
         # Return a shell indicating this initial failure
         return {
             "report_date": requested_report_date_utc.strftime('%Y-%m-%d'),
             "effective_report_date": None,
             "error": error_msg,
             "basic_info": None, "sales_on_report_date": 0.0, "orders_on_report_date": 0,
             "sales_trend_data": {'labels': [], 'datasets': []},
             "item_quantity_trend_data": {'labels': [], 'datasets': []},
             "stock_forecast": [], "low_stock_alerts": [],
             "top_products_pareto_today": {'labels': [], 'data': [], 'cumulative': []},
             "word_of_encouragement": None
         }


    # --- Initialize Report Structure ---
    # Use the *requested* date for the initial report key if no data found,
    # but the main report content will use the effective date.
    report_shell = {
        "report_date": requested_report_date_utc.strftime('%Y-%m-%d'), # Reflects user request
        "effective_report_date": None, # Will be filled if data found
        "error": None,
        "basic_info": None,
        "sales_on_report_date": 0.0, # Default to 0
        "orders_on_report_date": 0, # Default to 0
        "sales_trend_data": {'labels': [], 'datasets': []}, # Default empty structure
        "item_quantity_trend_data": {'labels': [], 'datasets': []}, # Default empty structure
        "stock_forecast": [], # Default empty list
        "low_stock_alerts": [], # Default empty list
        "top_products_pareto_today": {'labels': [], 'data': [], 'cumulative': []}, # Default empty structure
        "word_of_encouragement": config.ENCOURAGEMENT_MESSAGE if hasattr(config, 'ENCOURAGEMENT_MESSAGE') else "Keep up the great work!"
    }

    if effective_report_date is None:
        error_msg = f"No transaction data found for merchant '{merchant_id}' to generate a report based on activity."
        print(f"[Report Status] {error_msg}")
        report_shell["error"] = error_msg # Add non-fatal error/status
        # Decide if you want to return here or continue trying to get basic info etc.
        # Let's return the shell with the error for clarity.
        return report_shell

    # --- Proceed with Report Generation using effective_report_date ---
    print(f"Found data. Generating report using effective date: {effective_report_date.strftime('%Y-%m-%d')}")
    report_data = report_shell.copy() # Start with the shell
    # Overwrite report_date and set effective_report_date to the date data was found for
    report_data["report_date"] = effective_report_date.strftime('%Y-%m-%d')
    report_data["effective_report_date"] = effective_report_date.strftime('%Y-%m-%d')

    # Define date ranges based on the *effective* date (make them timezone-aware UTC datetimes)
    report_day_start = datetime.combine(effective_report_date, datetime.min.time(), tzinfo=timezone.utc)
    report_day_end = report_day_start + timedelta(days=1) # Exclusive end (start of next day)
    # Trend data looks back from the start of the effective report day
    trend_days = getattr(config, 'SALES_TREND_DAYS', 7) # Default to 7 if not in config
    trend_start_date = report_day_start - timedelta(days=trend_days)

    try:
        # --- Basic Merchant Info ---
        print("Fetching merchant basic info...")
        merchant_df = loader.get_merchants_df()
        if merchant_df is None or merchant_df.empty:
             # Non-fatal: Report can continue without basic info
             print("Warning: Merchants data is empty or failed to load. Skipping basic info.")
             report_data["basic_info"] = {"error": "Could not load merchant data."}
        else:
            if 'merchant_id' not in merchant_df.columns:
                 print("Warning: 'merchant_id' column missing in merchants data. Skipping basic info.")
                 report_data["basic_info"] = {"error": "Merchant data format incorrect (missing merchant_id)."}
            else:
                merchant_info_series = merchant_df[merchant_df['merchant_id'] == merchant_id]

                if merchant_info_series.empty:
                    print(f"Warning: Merchant with ID '{merchant_id}' not found in merchants data. Skipping basic info.")
                    report_data["basic_info"] = {"error": f"Merchant ID '{merchant_id}' not found."}
                else:
                    merchant_info = merchant_info_series.iloc[0].to_dict()

                    # Calculate Business Maturity Safely
                    business_maturity_years: Any = "N/A" # Use Any type hint for flexibility
                    join_date_val = merchant_info.get("join_date")
                    if pd.notna(join_date_val): # Check for valid date/timestamp (not None or NaT)
                        try:
                            # Ensure Timestamp and UTC awareness
                            join_dt_aware = pd.Timestamp(join_date_val)
                            if join_dt_aware.tzinfo is None:
                                join_dt_aware = join_dt_aware.tz_localize('UTC')
                            else:
                                join_dt_aware = join_dt_aware.tz_convert('UTC')

                            maturity_delta = datetime.now(timezone.utc) - join_dt_aware
                            if maturity_delta.days >= 0:
                                business_maturity_years = round(maturity_delta.days / 365.25, 1)
                            else:
                                business_maturity_years = 0.0 # Joined in the future? Set to 0.
                        except Exception as maturity_err:
                            print(f"Warning: Could not calculate maturity for join date '{join_date_val}': {maturity_err}")
                            business_maturity_years = "Calculation Error"

                    report_data["basic_info"] = {
                        # Use .get() for robustness against missing columns in source data
                        "merchant_name": merchant_info.get("merchant_name", "N/A"),
                        "merchant_type": merchant_info.get("merchant_type", "N/A"),
                        "cuisine_type": merchant_info.get("cuisine_tag", merchant_info.get("cuisine_type", "N/A")), # Check both possible names
                        "location": merchant_info.get("city_name", "N/A"),
                        "business_maturity_years": business_maturity_years
                    }
                    print("Basic info processed.")

        # --- Metrics for the Effective Report Day ---
        # These rely on metrics_calculator functions which should handle internal errors/empty data
        print(f"Calculating metrics for effective date: {effective_report_date.strftime('%Y-%m-%d')}...")
        try:
            report_data["sales_on_report_date"] = metrics_calculator.calculate_sales(
                merchant_id, report_day_start, report_day_end
            )
            report_data["orders_on_report_date"] = metrics_calculator.calculate_num_orders(
                merchant_id, report_day_start, report_day_end
            )
            print(f"Metrics for effective report date processed (Sales: {report_data['sales_on_report_date']}, Orders: {report_data['orders_on_report_date']}).")
        except Exception as metric_err:
             print(f"ERROR calculating daily metrics: {metric_err}")
             traceback.print_exc()
             report_data["sales_on_report_date"] = "Error" # Indicate error in report
             report_data["orders_on_report_date"] = "Error"
             # Optionally add specific error message to report_data['error']


        # --- Trend Data (Looking Back from effective_report_date) ---
        print(f"Calculating trend data from {trend_start_date.strftime('%Y-%m-%d')} to {report_day_start.strftime('%Y-%m-%d')}...")
        try:
            report_data["sales_trend_data"] = metrics_calculator.get_sales_over_time(
                merchant_id, trend_start_date, report_day_start
            )
            print("Sales over time trend processed.")
        except Exception as trend_err:
             print(f"ERROR calculating sales trend: {trend_err}")
             traceback.print_exc()
             report_data["sales_trend_data"] = {'error': f"Failed to calculate sales trend: {trend_err}"}

        try:
            report_data["item_quantity_trend_data"] = metrics_calculator.get_items_sold_over_time(
                merchant_id, trend_start_date, report_day_start
            )
            print("Item quantity over time trend processed.")
        except Exception as item_trend_err:
             print(f"ERROR calculating item quantity trend: {item_trend_err}")
             traceback.print_exc()
             report_data["item_quantity_trend_data"] = {'error': f"Failed to calculate item trend: {item_trend_err}"}


        # --- Stock Forecast & Alerts ---
        print("Processing stock information...")
        try:
            # Check if stock_predictor module and functions exist before calling
            if hasattr(stock_predictor, 'predict_stock_runout'):
                report_data["stock_forecast"] = stock_predictor.predict_stock_runout(merchant_id)
            else:
                 print("Warning: stock_predictor.predict_stock_runout function not found.")
                 report_data["stock_forecast"] = [{"error": "Stock prediction feature unavailable."}]

            if hasattr(stock_predictor, 'check_low_stock_alerts'):
                report_data["low_stock_alerts"] = stock_predictor.check_low_stock_alerts(merchant_id)
            else:
                 print("Warning: stock_predictor.check_low_stock_alerts function not found.")
                 report_data["low_stock_alerts"] = [{"error": "Low stock check feature unavailable."}]

            print("Stock forecast and alerts processed.")
        except Exception as stock_err:
             print(f"ERROR during stock processing: {stock_err}")
             traceback.print_exc()
             # Add specific error messages to the report fields
             report_data["stock_forecast"] = [{"error": f"Stock prediction failed: {stock_err}"}]
             report_data["low_stock_alerts"] = [{"error": f"Low stock check failed: {stock_err}"}]


        # --- Pareto Analysis (For the Effective Report Day) ---
        print(f"Calculating Pareto data for effective date: {effective_report_date.strftime('%Y-%m-%d')}...")
        try:
            report_data["top_products_pareto_today"] = metrics_calculator.calculate_pareto_data(
                merchant_id, report_day_start, report_day_end
            )
            print(f"Pareto data processed.")
        except Exception as pareto_err:
            print(f"ERROR calculating Pareto data: {pareto_err}")
            traceback.print_exc()
            report_data["top_products_pareto_today"] = {'error': f"Failed to calculate Pareto data: {pareto_err}"}


        # --- Final Touches ---
        # Encouragement message already set in shell initialization
        print("Encouragement message added.")
        print(f"Finished daily report generation successfully for merchant '{merchant_id}' using effective date {effective_report_date.strftime('%Y-%m-%d')}")

    except Exception as e:
        # --- Catch-all for unexpected errors during main processing ---
        error_detail = f"Unexpected error during report generation for merchant '{merchant_id}' (effective date {effective_report_date.strftime('%Y-%m-%d')}): {e}"
        print(f"[Report Error] {error_detail}")
        traceback.print_exc()
        # Add error to the report data, preserving any data already generated
        report_data["error"] = report_data.get("error") + f"; {error_detail}" if report_data.get("error") else error_detail # Append if error already exists

    return report_data
