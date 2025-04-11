import sys
import os
import traceback
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
from datetime import date, timedelta, datetime, timezone
from backend.data_access import loader
from backend.core import metrics_calculator
from backend import config
from backend.reporting import stock_predictor

def generate_daily_report(merchant_id, report_date):
    """Generates the complete daily report object."""
    # Use report_date for "today's" metrics, use lookback for trends
    report_day_start = pd.Timestamp(report_date, tz='UTC')
    report_day_end = report_day_start + timedelta(days=1)
    trend_start_date = report_day_start - timedelta(days=config.SALES_TREND_DAYS) # Trends look back from report date

    report_data = {"report_date": report_date.strftime('%Y-%m-%d'), "error": None}

    try:
        print(f"Starting daily_report generation for {merchant_id} on {report_date}")

        # --- Basic Info & Maturity ---
        merchant_df = loader.get_merchants_df()
        if merchant_df.empty or merchant_id not in merchant_df['merchant_id'].values:
            report_data["error"] = f"Merchant with ID '{merchant_id}' not found."
            print(report_data["error"])
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

        # --- Metrics for the Report Day ---
        orders_report_day_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=report_day_start, end_date=report_day_end)
        report_data["sales_on_report_date"] = metrics_calculator.calculate_sales(orders_report_day_df)
        report_data["orders_on_report_date"] = metrics_calculator.calculate_num_orders(orders_report_day_df)
        print("Metrics for report date processed.")

        # --- Trend Data (Looking Back) ---
        all_orders_trend_df = loader.get_transaction_data_df(merchant_id=merchant_id, start_date=trend_start_date, end_date=report_day_start) # End date is start of report day
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
        print("Pareto data processed.")

        report_data["word_of_encouragement"] = config.ENCOURAGEMENT_MESSAGE
        print("Encouragement message added.")
        print(f"Finished daily_report generation for {merchant_id}")


    except Exception as e:
        print(f"Error generating daily report for {merchant_id}: {e}")
        traceback.print_exc()
        report_data["error"] = f"Failed to generate full report: {e}"

    return report_data # Return the complete dictionary