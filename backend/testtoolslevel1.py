import sys
import os
from datetime import date, timedelta
import json # To pretty-print the results
import pandas as pd # For checking data types maybe

# --- !!! FIX: Add Project Root to Python Path !!! ---
# Calculate the path to the project root directory (one level up from 'backend')
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Insert it at the beginning of the Python path list
sys.path.insert(0, project_root)
# --- End Fix ---

# --- Core Imports (Now should work) ---
# It's often clearer to use the full path from the project root now
from backend.data_access import loader
from backend.reporting import daily_report_generator
from backend.core import anomaly_detector

# --- Configuration ---
# Choose a merchant ID known to exist in your mock_data/merchant.csv
TEST_MERCHANT_ID = "1a3f7"
# Or use the one hardcoded in routes.py if specifically testing that route's behavior later
# TEST_MERCHANT_ID = "1a3f7" # Use the one from routes.py

if __name__ == "__main__":
    print("--- Starting Direct Function Test Script ---")

    # 1. !!! Load Data First !!! (Very Important)
    try:
        # Now that project_root is in sys.path, loader should find config
        loader.load_all_data()
        print("[OK] Mock data loaded successfully.")
    except Exception as e:
        print(f"[FATAL] Error loading mock data: {e}")
        import traceback
        traceback.print_exc() # Print detailed error
        sys.exit(1) # Stop if data loading fails

    # ... (rest of your test script remains the same) ...

    # 2. Test `generate_daily_report`
    print(f"\n--- Testing: daily_report_generator.generate_daily_report for {TEST_MERCHANT_ID} ---")
    try:
        report_date = date.today() - timedelta(days=1) # Test for yesterday
        print(f"Requesting report for date: {report_date.strftime('%Y-%m-%d')}")
        report_data = daily_report_generator.generate_daily_report(TEST_MERCHANT_ID, report_date)

        print("[RESULT] Report generated. Structure:")
        print(json.dumps(report_data, indent=2, default=str))

        # Basic Checks:
        if report_data.get("error"):
            print(f"[WARN] Report generation returned an error message: {report_data['error']}")
        if not isinstance(report_data, dict):
             print("[FAIL] Expected report_data to be a dictionary.")
        if "sales_today" not in report_data:
             print("[FAIL] 'sales_today' key missing from report.")

    except Exception as e:
        print(f"[FAIL] ERROR during daily report generation test: {e}")
        import traceback
        traceback.print_exc()

    # 3. Test `detect_anomalies`
    print(f"\n--- Testing: anomaly_detector.detect_anomalies for {TEST_MERCHANT_ID} ---")
    try:
        anomalies = anomaly_detector.detect_anomalies(TEST_MERCHANT_ID)

        print(f"[RESULT] Anomaly detection complete. Found {len(anomalies)} potential anomalies.")
        print(json.dumps(anomalies, indent=2, default=str))

        # Basic Checks:
        if not isinstance(anomalies, list):
            print("[FAIL] Expected anomalies to be a list.")
        if anomalies:
             if not isinstance(anomalies[0], dict):
                  print("[FAIL] Expected items in the anomalies list to be dictionaries.")
             if 'type' not in anomalies[0]:
                  print("[FAIL] Anomaly dictionary missing 'type' key.")

    except Exception as e:
        print(f"[FAIL] ERROR during anomaly detection test: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Direct Function Test Script Finished ---")