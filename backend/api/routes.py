# api_routes.py (or wherever your route is defined)

from flask import Blueprint, jsonify, request, session # Added session
# --- Standard library imports ---
import traceback
from datetime import datetime

# --- Third-party imports ---
import pandas as pd

# --- Local application imports ---
from backend.reporting import daily_report_generator
from backend.core import anomaly_detector
from backend.data_access import loader # Import necessary functions/modules
from backend.insight_engine import recommendation_engine
from backend.insight_engine import query_processor
from backend import config # Import config

# --- Import Inventory Manager (Adjust path as needed) ---
# Assuming mock_data is adjacent or configured in PYTHONPATH
from mock_data import inventory_manager


api_bp = Blueprint('api', __name__)

# --- Placeholder Merchant ID ---
# In a real app, this would come from authentication (e.g., session)
MOCK_MERCHANT_ID = "1d4f2" # Example: Replace with a valid ID from your data

# --- NEW: Endpoint to get merchant-specific inventory ---
@api_bp.route('/merchant/inventory', methods=['GET'])
def get_merchant_inventory():
    """
    Endpoint to get current inventory details (stock name, quantity, units)
    for the current merchant based on the latest log entry per stock item.
    """
    merchant_id = MOCK_MERCHANT_ID # Use the mock ID for now
    try:
        print(f"Fetching inventory log for merchant: {merchant_id}")

        # 1. Get the raw inventory log data
        raw_inventory_df = loader.get_inventory_df()
        # Optional: Add print statement to debug if needed
        # print(raw_inventory_df)
        if raw_inventory_df is None or raw_inventory_df.empty:
            print(f"No raw inventory data found in loader.")
            return jsonify([])

        # --- Basic Validation ---
        required_cols = ['merchant_id', 'stock_name', 'stock_quantity', 'units', 'date_updated']
        if not all(col in raw_inventory_df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in raw_inventory_df.columns]
            print(f"Error: Inventory data is missing required columns: {missing}")
            return jsonify({"error": f"Internal server error: Inventory data is incomplete (missing: {', '.join(missing)})"}), 500

        # 2. Filter for the specific merchant
        merchant_inventory_log = raw_inventory_df[raw_inventory_df['merchant_id'] == merchant_id].copy()

        if merchant_inventory_log.empty:
            print(f"No inventory log data found for merchant {merchant_id}.")
            return jsonify([])

        # 3. Find the *current* stock for each item
        try:
            # Convert 'date_updated' to datetime objects *after* filtering for efficiency
            # errors='coerce' will turn unparseable dates into NaT (Not a Time)
            merchant_inventory_log['date_updated'] = pd.to_datetime(merchant_inventory_log['date_updated'], errors='coerce')
            original_count = len(merchant_inventory_log)
            merchant_inventory_log.dropna(subset=['date_updated'], inplace=True) # Remove rows with invalid dates
            if len(merchant_inventory_log) < original_count:
                 print(f"Warning: Dropped {original_count - len(merchant_inventory_log)} rows due to invalid date format for merchant {merchant_id}.")

        except Exception as e: # Catch potential errors during conversion/dropna
            print(f"Error processing 'date_updated' column: {e}")
            traceback.print_exc()
            return jsonify({"error": "Internal server error: Could not process date information in inventory"}), 500

        if merchant_inventory_log.empty:
            print(f"No valid inventory entries remain for merchant {merchant_id} after date processing.")
            return jsonify([])

        # Sort by stock_name and then date (latest first)
        merchant_inventory_log = merchant_inventory_log.sort_values(
            by=['stock_name', 'date_updated'],
            ascending=[True, False] # Sort name A-Z, date Newest-Oldest
        )


        # Drop duplicates based on 'stock_name', keeping the first entry (which is the latest due to sorting)
        current_inventory_df = merchant_inventory_log.drop_duplicates(
            subset=['stock_name'],
            keep='first'
        ).copy() # Use copy() to avoid SettingWithCopyWarning later


        # 4. Select and format the required output columns
        # Rename 'stock_quantity' to 'current_stock' for the output JSON
        current_inventory_df = current_inventory_df.rename(columns={'stock_quantity': 'current_stock'})

        # Select only the columns needed by the frontend
        result_df = current_inventory_df[['stock_name', 'current_stock', 'units']].copy()

        # Ensure correct data types for JSON serialization
        # Fill potential NaN in numeric column before converting type
        result_df['current_stock'] = result_df['current_stock'].fillna(0).astype(int) # Or float if needed
        result_df['units'] = result_df['units'].fillna('').astype(str)
        result_df['stock_name'] = result_df['stock_name'].fillna('Unknown').astype(str)


        result = result_df.to_dict('records')
        print(f"Returning {len(result)} current inventory items for merchant {merchant_id}.")
        return jsonify(result)

    except FileNotFoundError as e:
         print(f"Error finding data file during inventory fetch: {e}")
         return jsonify({"error": f"Required data file not found: {e.filename}"}), 500
    except KeyError as e:
         # This might happen if required columns are missing despite the initial check
         print(f"Error accessing column during inventory processing: {e}")
         traceback.print_exc()
         return jsonify({"error": f"Internal server error: Missing expected data column '{e}'"}), 500
    except Exception as e:
        print(f"An unexpected error occurred in /merchant/inventory for {merchant_id}: {e}")
        traceback.print_exc() # Log full traceback
        return jsonify({"error": "Internal server error fetching inventory"}), 500


# --- MODIFIED: Endpoint to update stock levels (using inventory_manager) ---
@api_bp.route('/merchant/stock_update', methods=['POST'])
def update_stock_route():
    """
    Endpoint to record new stock levels by appending entries to the inventory log CSV.
    Handles both bulk updates and adding single new items.
    """
    merchant_id = MOCK_MERCHANT_ID # Use the mock ID
    try:
        data = request.get_json()
        # Expected: [{"stock_name": "...", "new_stock": ..., "units": "(optional)"}]
        updates = data.get('updates')

        if not updates or not isinstance(updates, list):
            return jsonify({"error": "Invalid or missing 'updates' list in request body"}), 400

        print(f"Received stock update request for merchant {merchant_id} with {len(updates)} items.")

        update_results = {"success": [], "failed": []}
        all_succeeded = True

        # --- Pre-fetch current units for efficiency (only if needed) ---
        current_units = {}
        # Determine if any item in the payload is missing units information
        needs_unit_lookup = any(item.get('units') is None or item.get('units') == '' for item in updates)

        if needs_unit_lookup:
            print("Units lookup needed for at least one item.")
            try:
                latest_inventory = loader.get_inventory_df() # Read the current log
                if latest_inventory is not None and not latest_inventory.empty:
                    merchant_latest = latest_inventory[latest_inventory['merchant_id'] == merchant_id].copy()
                    if not merchant_latest.empty:
                         # Ensure date conversion before sorting/dropping duplicates
                         merchant_latest['date_updated'] = pd.to_datetime(merchant_latest['date_updated'], errors='coerce')
                         merchant_latest.dropna(subset=['date_updated'], inplace=True)
                         if not merchant_latest.empty: # Check again after dropna
                             merchant_latest = merchant_latest.sort_values(by='date_updated', ascending=False)
                             # Get latest unit for each stock name
                             latest_units_df = merchant_latest.drop_duplicates(subset=['stock_name'], keep='first')
                             current_units = pd.Series(latest_units_df.units.values, index=latest_units_df.stock_name).to_dict()
                             print(f"Fetched current units for lookup: {current_units}")

            except Exception as e:
                 print(f"Warning: Could not pre-fetch current units for lookup. Will use defaults if needed. Error: {e}")
                 # Proceed without pre-fetched units, will use default '' if lookup fails or is not needed
        else:
            print("No units lookup needed; all items provided units or lookup is not required.")


        # --- Process each update item ---
        for item_update in updates:
            stock_name = item_update.get('stock_name')
            new_stock_str = item_update.get('new_stock')
            # <<< --- MODIFICATION START --- >>>
            # Get units specifically from this item's payload
            units_from_payload = item_update.get('units') # Might be None or empty string
            # <<< --- MODIFICATION END --- >>>

            # --- Validation ---
            if not stock_name or new_stock_str is None:
                print(f"Skipping invalid update item (missing stock_name or new_stock): {item_update}")
                update_results["failed"].append({ "item": item_update, "reason": "Missing stock_name or new_stock" })
                all_succeeded = False
                continue

            try:
                 # Convert new_stock to integer, handle potential errors
                 new_stock_int = int(new_stock_str)
                 if new_stock_int < 0:
                      raise ValueError("Stock cannot be negative")

                 # <<< --- MODIFICATION START --- >>>
                 # --- Determine Units ---
                 # PRIORITY: Use units from payload if provided and not empty.
                 # Otherwise, lookup from existing data (if lookup was performed).
                 # Finally, default to empty string.
                 final_units = ''
                 if units_from_payload: # Check if it's not None and not empty string
                     final_units = units_from_payload
                     print(f"Using units from payload for '{stock_name}': '{final_units}'")
                 else:
                     # Only attempt lookup if lookup was needed and successful
                     if needs_unit_lookup and current_units:
                         final_units = current_units.get(stock_name, '') # Fallback to default '' if name not in lookup dict
                     else:
                         final_units = '' # Default to empty string if no lookup or lookup failed
                     print(f"Using looked-up/default units for '{stock_name}': '{final_units}'")
                 # <<< --- MODIFICATION END --- >>>


                 # --- Get Date (using consistent format) ---
                 date_updated_str = datetime.now().strftime('%Y-%m-%d') # Use YYYY-MM-DD format for consistency


                 # --- Call inventory_manager to APPEND the new log entry ---
                 success = inventory_manager.add_stock_log_entry(
                     merchant_id=merchant_id,
                     stock_name=str(stock_name), # Ensure stock_name is string
                     new_stock_level=new_stock_int,
                     units=str(final_units), # <<< MODIFICATION: Use the determined final_units >>>
                     date_updated_str=date_updated_str,
                     filepath=inventory_manager.INVENTORY_FILEPATH # Use path from manager
                 )

                 if success:
                      print(f"Successfully logged new stock entry for {stock_name}")
                      update_results["success"].append(stock_name)
                 else:
                      # The manager function prints errors, but log failure here too
                      print(f"Failed to log new stock entry for {stock_name}")
                      update_results["failed"].append({ "item": item_update, "reason": "inventory_manager failed to append log entry (check manager logs)" })
                      all_succeeded = False

            except ValueError as ve:
                 # Handle invalid integer conversion or negative stock
                 print(f"Skipping update for '{stock_name}': Invalid stock value '{new_stock_str}'. Error: {ve}")
                 update_results["failed"].append({ "item": item_update, "reason": f"Invalid stock value: {ve}" })
                 all_succeeded = False
            except Exception as item_err:
                 # Catch unexpected errors during a single item update
                 print(f"Error processing update for {stock_name}: {item_err}")
                 traceback.print_exc()
                 update_results["failed"].append({ "item": item_update, "reason": f"Unexpected error: {item_err}" })
                 all_succeeded = False


        # --- Determine Overall Response ---
        if all_succeeded:
             print("All stock updates logged successfully.")
             return jsonify({"status": "success", "message": f"Successfully processed {len(update_results['success'])} updates.", "details": update_results})
        elif not update_results["success"]: # No items succeeded
             print("All stock updates failed.")
             # Check if failure was due to validation or backend issue
             is_validation_failure = any('Invalid stock value' in f.get('reason','') or 'Missing' in f.get('reason','') for f in update_results.get('failed',[]))
             status_code = 400 if is_validation_failure else 500
             return jsonify({"error": "Failed to process any stock updates", "details": update_results}), status_code
        else: # Partial success
             print("Some stock updates failed.")
             return jsonify({"status": "partial_success", "message": f"Processed {len(update_results['success'])} updates, {len(update_results['failed'])} failed.", "details": update_results}), 207


    except Exception as e:
        print(f"Critical Error in /merchant/stock_update endpoint: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error during stock update process"}), 500


# --- Other existing routes (get_basic_info, get_daily_report, etc.) ---
@api_bp.route('/merchant/basic_info', methods=['GET'])
def get_basic_info():
    """ Endpoint to get basic merchant info. """
    merchant_id = MOCK_MERCHANT_ID # Use mock ID
    try:
        merchant_df = loader.get_merchants_df()
        info = merchant_df[merchant_df['merchant_id'] == merchant_id].to_dict('records')
        if not info:
            return jsonify({"error": f"Merchant {merchant_id} not found"}), 404
        return jsonify(info[0])
    except Exception as e:
        print(f"Error in /basic_info: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route('/merchant/daily_report', methods=['GET'])
def get_daily_report():
    """ Endpoint to generate and retrieve the daily report. """
    merchant_id = MOCK_MERCHANT_ID # Use mock ID
    try:
        from datetime import date, timedelta
        report_date = date.today() - timedelta(days=1) # Example: Yesterday
        report_data = daily_report_generator.generate_daily_report(merchant_id, report_date)
        return jsonify(report_data)
    except Exception as e:
        print(f"Error in /daily_report: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route('/merchant/check_anomalies', methods=['POST']) # POST might be better if triggering analysis
def check_anomalies_route():
    """ Endpoint to check for anomalies and return insights. """
    merchant_id = MOCK_MERCHANT_ID # Use mock ID
    try:
        anomalies = anomaly_detector.detect_anomalies(merchant_id) # Pass necessary data/dates

        insights = []
        if anomalies:
            for anomaly in anomalies: # Prioritize which ones to process
                 # Assuming recommendation engine exists and works
                 try:
                     insight = recommendation_engine.get_reason_and_recommendation(anomaly, merchant_id)
                 except Exception as rec_err:
                     print(f"Error getting recommendation for anomaly: {rec_err}")
                     insight = {"reason": "N/A", "recommendation": "N/A (Error in analysis)"}

                 if insight:
                      insights.append({
                          "type": anomaly.get('type', 'unknown'),
                          "message": f"Alert: Anomaly detected for {anomaly.get('metric', '')}!", # Make message more specific
                          "reason": insight.get('reason'),
                          "recommendation": insight.get('recommendation')
                      })

        return jsonify({"alerts": insights}) # Return insights/alerts
    except Exception as e:
        print(f"Error in /check_anomalies: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

@api_bp.route('/merchant/ask', methods=['POST'])
def handle_ask():
    """ Endpoint to handle free-form questions from the merchant. """
    merchant_id = MOCK_MERCHANT_ID # Use mock ID

    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        answer = query_processor.process_merchant_question(merchant_id, question)
        return jsonify({"answer": answer})

    except Exception as e:
        print(f"Error processing question '{question}' for {merchant_id}: {e}")
        traceback.print_exc()
        return jsonify({"answer": "Sorry, I encountered an error trying to answer that question."}), 500