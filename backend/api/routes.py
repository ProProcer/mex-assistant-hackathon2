# api_routes.py (or wherever your route is defined)

from flask import Blueprint, jsonify, request, session # Added session
# --- Standard library imports ---
import traceback
from datetime import datetime
from backend.data_access import loader
# --- Third-party imports ---
import pandas as pd
import logging
import numpy as np

# --- Local application imports ---
from backend.reporting import daily_report_generator
from backend.core import anomaly_detector
from backend.data_access import loader # Import necessary functions/modules
from backend.insight_engine import recommendation_engine
from backend.insight_engine import query_processor
from backend import config # Import config
from mock_data import inventory_manager

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
    Endpoint to record new stock levels by appending entries to the inventory log CSV,
    checks for notifications, and includes triggered alerts in the response.
    """
    merchant_id = MOCK_MERCHANT_ID # TODO: Get from session/auth
    try:
        if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
        data = request.get_json()
        updates = data.get('updates') # Expecting: [{"stock_name": "...", "new_stock": ..., "units": "(optional)"}]

        if not updates or not isinstance(updates, list):
            return jsonify({"error": "Invalid or missing 'updates' list"}), 400

        logging.info(f"Stock update request for {merchant_id}, {len(updates)} items.")

        update_results = {"success": [], "failed": []}
        triggered_product_names = [] # <-- List to collect product names triggering alerts
        all_succeeded = True

        # --- Pre-fetch current units (Keep existing logic) ---
        current_units = {}
        needs_unit_lookup = any(item.get('units') is None or item.get('units') == '' for item in updates)
        if needs_unit_lookup:
            # ... (keep the logic to fetch and populate current_units) ...
            logging.info("Units lookup needed.")
            try:
                latest_inventory = loader.get_inventory_df()
                if latest_inventory is not None and not latest_inventory.empty:
                    merchant_latest = latest_inventory[latest_inventory['merchant_id'] == merchant_id].copy()
                    if not merchant_latest.empty:
                         merchant_latest['date_updated'] = pd.to_datetime(merchant_latest['date_updated'], errors='coerce')
                         merchant_latest.dropna(subset=['date_updated'], inplace=True)
                         if not merchant_latest.empty:
                             merchant_latest = merchant_latest.sort_values(by='date_updated', ascending=False)
                             latest_units_df = merchant_latest.drop_duplicates(subset=['stock_name'], keep='first')
                             # Use fillna('') here to handle potential NaNs read from CSV before creating dict
                             current_units = pd.Series(latest_units_df.units.values, index=latest_units_df.stock_name).fillna('').to_dict()
                             logging.info(f"Fetched units for lookup: {len(current_units)} items")
            except Exception as e:
                 logging.warning(f"Could not pre-fetch units: {e}", exc_info=True)
        else:
            logging.info("No units lookup needed.")


        # --- Process each update item ---
        for item_update in updates:
            stock_name = item_update.get('stock_name')
            new_stock_str = item_update.get('new_stock')
            units_from_payload = item_update.get('units')

            # --- Validation (Keep existing) ---
            if not stock_name or new_stock_str is None:
                update_results["failed"].append({ "item": item_update, "reason": "Missing stock_name or new_stock" })
                all_succeeded = False
                continue

            try:
                 new_stock_int = int(new_stock_str)
                 if new_stock_int < 0: raise ValueError("Stock cannot be negative")

                 # --- Determine Units (Keep existing) ---
                 final_units = ''
                 if units_from_payload: final_units = units_from_payload
                 elif needs_unit_lookup and current_units: final_units = current_units.get(stock_name, '')
                 # ...

                 date_updated_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                 # --- Call inventory_manager to APPEND log entry ---
                 # Ensure using the correct INVENTORY_FILEPATH from config or manager
                 log_filepath = config.INVENTORY_CSV # Use path from config ideally
                 success = inventory_manager.add_stock_log_entry(
                     merchant_id=merchant_id,
                     stock_name=str(stock_name),
                     new_stock_level=new_stock_int,
                     units=str(final_units),
                     date_updated_str=date_updated_str,
                     filepath=log_filepath # Pass the correct path
                 )

                 if success:
                      logging.info(f"Successfully logged entry for {stock_name}")
                      update_results["success"].append({"name": stock_name, "new_level": new_stock_int}) # Include level for check

                      # --- *** CHECK NOTIFICATIONS for THIS successful item *** ---
                      alert_product_name = inventory_manager.check_stock_notifications(
                          merchant_id, stock_name, new_stock_int
                      )
                      if alert_product_name and alert_product_name not in triggered_product_names:
                           triggered_product_names.append(alert_product_name)
                      # ---------------------------------------------------------
                 else:
                      logging.warning(f"Failed to log entry for {stock_name}")
                      update_results["failed"].append({ "item": item_update, "reason": "inventory_manager failed to append log" })
                      all_succeeded = False

            except ValueError as ve:
                 # ... (handle failed item validation) ...
                 update_results["failed"].append({ "item": item_update, "reason": f"Invalid stock value: {ve}" })
                 all_succeeded = False
            except Exception as item_err:
                 # ... (handle failed item unexpected) ...
                 logging.error(f"Error processing update for {stock_name}: {item_err}", exc_info=True)
                 update_results["failed"].append({ "item": item_update, "reason": f"Unexpected error: {item_err}" })
                 all_succeeded = False

        # --- Determine Overall Response ---
        response_data = {
            "details": update_results,
             # ** INCLUDE THE ALERT LIST **
            "low_stock_alerts": triggered_product_names
        }
        status_code = 200 # Default OK

        if all_succeeded:
             logging.info("All stock updates logged successfully. Notifications checked.")
             response_data["status"] = "success"
             response_data["message"] = f"Processed {len(updates)} updates."
        elif not update_results["success"]:
             logging.error("All stock updates failed.")
             response_data["error"] = "Failed to process any stock updates"
             is_validation = any('Invalid' in f.get('reason','') or 'Missing' in f.get('reason','') for f in update_results.get('failed',[]))
             status_code = 400 if is_validation else 500
        else: # Partial success
             logging.warning("Some stock updates failed.")
             response_data["status"] = "partial_success"
             response_data["message"] = f"Processed {len(update_results['success'])}, Failed: {len(update_results['failed'])}."
             status_code = 207 # Multi-Status

        logging.info(f"Sending stock update response. Alerts: {triggered_product_names}")
        return jsonify(response_data), status_code

    except Exception as e:
        logging.critical(f"Critical Error in /merchant/stock_update endpoint: {e}", exc_info=True)
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

@api_bp.route('/merchant/notifications', methods=['GET'])
def get_notification_rules():
    merchant_id = MOCK_MERCHANT_ID # TODO: Get from session/auth
    logging.info(f"GET /api/merchant/notifications request received for merchant {merchant_id}")
    try:
        rules_df = loader.get_notifications_df()
        if rules_df.empty:
            return jsonify([])

        merchant_rules_df = rules_df[rules_df['merchant_id'] == merchant_id].copy()

        # --- *** FIX: Handle NaN before converting to dictionary *** ---
        # Replace pandas NaN with None (which becomes JSON null)
        # Use numpy's NaN for reliable comparison across OS/versions
        merchant_rules_df = merchant_rules_df.replace({np.nan: None})

        # Alternatively, replace NaN specifically in certain columns:
        # if 'units' in merchant_rules_df.columns:
        #     merchant_rules_df['units'] = merchant_rules_df['units'].fillna('') # Replace NaN in units with empty string
        # if 'threshold' in merchant_rules_df.columns:
        #     # Replacing NaN in numeric column with None is usually best for JSON
        #     merchant_rules_df['threshold'] = merchant_rules_df['threshold'].astype(object).where(pd.notnull(merchant_rules_df['threshold']), None)


        rules_list = merchant_rules_df.to_dict('records')
        # -------------------------------------------------------------

        rules_list.sort(key=lambda x: x.get('id', 0))

        logging.info(f"Returning {len(rules_list)} rules for merchant {merchant_id}.")
        # Add debug print if needed
        # logging.debug(f"Cleaned rules list for JSON: {rules_list}")
        return jsonify(rules_list)
    except Exception as e:
        logging.error(f"Error processing GET /merchant/notifications for {merchant_id}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error retrieving notification rules"}), 500


@api_bp.route('/merchant/notifications', methods=['POST'])
def create_notification_rule():
    merchant_id = MOCK_MERCHANT_ID # TODO: Get from session/auth
    logging.info(f"POST /api/merchant/notifications request received for merchant {merchant_id}")

    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    logging.info(f"Received data: {data}")

    # --- Validation (Keep same validation logic) ---
    # ... (validation for productName, threshold, enabled) ...
    required_fields = ['productName', 'threshold', 'enabled']
    if not all(field in data for field in required_fields):
        missing = [f for f in required_fields if f not in data]
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    product_name = data.get('productName')
    threshold = data.get('threshold')
    enabled = data.get('enabled')
    units = data.get('units', '')
    if not isinstance(product_name, str) or not product_name.strip():
        return jsonify({"error": "productName must be non-empty"}), 400
    try:
        threshold_num = float(threshold)
        if threshold_num < 0: raise ValueError()
    except: return jsonify({"error": "threshold must be non-negative number"}), 400
    if not isinstance(enabled, bool):
        return jsonify({"error": "enabled must be boolean"}), 400
    # --- End Validation ---

    try:
        # --- Load existing rules to determine next ID and check duplicates ---
        # Use the accessor function
        rules_df = loader.get_notifications_df()

        # Check for duplicates for THIS merchant
        merchant_rules = rules_df[rules_df['merchant_id'] == merchant_id]
        is_duplicate = merchant_rules['productName'].str.lower() == product_name.strip().lower()
        if is_duplicate.any():
            return jsonify({"error": f"A rule for '{product_name}' already exists."}), 409

        # Determine next ID
        if rules_df.empty or 'id' not in rules_df.columns or rules_df['id'].isnull().all():
             new_rule_id = 1
        else:
             new_rule_id = int(rules_df['id'].max()) + 1 # Ensure int result

        # --- Create new rule data ---
        new_rule = {
            "id": new_rule_id,
            "merchant_id": merchant_id,
            "productName": product_name.strip(),
            "threshold": threshold_num,
            "enabled": enabled,
            "units": units
        }

        # --- Call the loader function to save the rule ---
        if loader.save_notification_rule(new_rule):
            logging.info(f"Rule ID {new_rule_id} saved via loader for merchant {merchant_id}.")
            # Return the rule data (as it was passed to save)
            return jsonify({"message": "Rule created successfully!", "rule": new_rule}), 201
        else:
            logging.error("Loader failed to save notification rule.")
            return jsonify({"error": "Failed to save notification rule."}), 500

    except Exception as e:
        logging.error(f"Error processing POST /merchant/notifications for {merchant_id}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error creating notification rule"}), 500


@api_bp.route('/merchant/notifications/<int:rule_id>', methods=['PUT', 'PATCH'])
def update_notification_rule(rule_id):
    merchant_id = MOCK_MERCHANT_ID # TODO: Use real auth
    logging.info(f"PUT/PATCH /api/merchant/notifications/{rule_id} for merchant {merchant_id}")
    if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()

    # Call the loader function to handle update and saving
    success, result_data = loader.update_notification_rule_in_csv(rule_id, merchant_id, data)

    if success:
        if result_data: # Check if result_data is not None (means update happened or no change needed)
             logging.info(f"Rule {rule_id} update processed successfully via loader.")
             return jsonify({"message": "Rule updated successfully!", "rule": result_data}), 200
        else: # Should ideally not happen if success is True based on loader logic
             logging.warning("Loader reported success but no result data for update.")
             return jsonify({"message": "Update processed, but no data returned."}), 200
    elif result_data is None and not success: # Check if it was a "not found" error
         return jsonify({"error": "Rule not found or does not belong to merchant"}), 404
    else: # Other failure (e.g., save error)
        logging.error(f"Loader failed to update rule {rule_id}.")
        return jsonify({"error": "Failed to update notification rule."}), 500


@api_bp.route('/merchant/notifications/<int:rule_id>', methods=['DELETE'])
def delete_notification_rule(rule_id):
    merchant_id = MOCK_MERCHANT_ID # TODO: Use real auth
    logging.info(f"DELETE /api/merchant/notifications/{rule_id} for merchant {merchant_id}")

    # Call the loader function to handle deletion and saving
    success = loader.delete_notification_rule_from_csv(rule_id, merchant_id)

    if success:
        logging.info(f"Rule {rule_id} deleted successfully via loader.")
        return jsonify({"message": "Rule deleted successfully"}), 200
    else:
        # Loader function logs specifics, check if it was not found vs save error
        # For simplicity here, return 404, but could differentiate
        # We might need the loader delete function to return more info (e.g., 'not_found', 'save_error')
        logging.warning(f"Loader failed to delete rule {rule_id} (may not exist or save failed).")
        return jsonify({"error": "Rule not found or failed to delete."}), 404 # Or 500 if save failed




@api_bp.route('/merchant/stock_delete', methods=['DELETE'])
def delete_stock_route():
    """
    Endpoint to delete all log entries for a specific stock item for the merchant.
    """
    merchant_id = MOCK_MERCHANT_ID # Use the mock ID or get from auth

    # Get stock_name from request body (JSON)
    data = request.get_json()
    stock_name = data.get('stock_name')

    if not stock_name:
        return jsonify({"error": "Missing 'stock_name' in request body"}), 400

    print(f"Received request to delete stock '{stock_name}' for merchant {merchant_id}")

    try:
        success = inventory_manager.delete_stock_log_entry(
            merchant_id=merchant_id,
            stock_name=stock_name,
            filepath=inventory_manager.INVENTORY_FILEPATH # Use path from manager
        )

        if success:
             print(f"Successfully processed deletion request for {stock_name}")
             return jsonify({"status": "success", "message": f"Stock item '{stock_name}' deleted successfully."})
        else:
             # Assume inventory_manager logged the specific error
             print(f"Failed to process deletion request for {stock_name}")
             return jsonify({"error": f"Failed to delete stock item '{stock_name}'. Check server logs."}), 500

    except Exception as e:
        print(f"Critical Error in /merchant/stock_delete endpoint for {stock_name}: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error during stock deletion process"}), 500

