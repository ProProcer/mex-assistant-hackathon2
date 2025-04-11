from flask import Blueprint, jsonify, request
from reporting import daily_report_generator
from core import anomaly_detector
from data_access import loader # Import necessary functions/modules
from insight_engine import recommendation_engine
from insight_engine import query_processor

api_bp = Blueprint('api', __name__)

# --- Placeholder Merchant ID ---
# In a real app, this would come from authentication
MOCK_MERCHANT_ID = "1a3f7" # Change this to test different merchants

@api_bp.route('/merchant/basic_info', methods=['GET'])
def get_basic_info():
    """ Endpoint to get basic merchant info. """
    try:
        # TODO: Implement logic to get basic info for MOCK_MERCHANT_ID
        # Example: Fetch from merchants_df
        merchant_df = loader.get_merchants_df()
        info = merchant_df[merchant_df['merchant_id'] == MOCK_MERCHANT_ID].to_dict('records')
        if not info:
            return jsonify({"error": "Merchant not found"}), 404
        # Add more details as needed
        return jsonify(info[0])
    except Exception as e:
        print(f"Error in /basic_info: {e}")
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route('/merchant/daily_report', methods=['GET'])
def get_daily_report():
    """ Endpoint to generate and retrieve the daily report. """
    try:
        # TODO: Implement logic to generate the daily report for MOCK_MERCHANT_ID
        # You might need to define the 'date' for the report (e.g., yesterday)
        from datetime import date, timedelta
        report_date = date.today() - timedelta(days=1) # Example: Yesterday
        report_data = daily_report_generator.generate_daily_report(MOCK_MERCHANT_ID, report_date)
        return jsonify(report_data)
    except Exception as e:
        print(f"Error in /daily_report: {e}")
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route('/merchant/check_anomalies', methods=['POST']) # POST might be better if triggering analysis
def check_anomalies_route():
    """ Endpoint to check for anomalies and return insights. """
    try:
        # TODO: Implement anomaly detection logic for MOCK_MERCHANT_ID
        anomalies = anomaly_detector.detect_anomalies(MOCK_MERCHANT_ID) # Pass necessary data/dates

        insights = []
        if anomalies:
            # TODO: For each significant anomaly, get reason and recommendation
            for anomaly in anomalies: # Prioritize which ones to process
                 insight = recommendation_engine.get_reason_and_recommendation(anomaly, MOCK_MERCHANT_ID)
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
        return jsonify({"error": "Internal server error"}), 500


@api_bp.route('/merchant/stock_update', methods=['POST'])
def update_stock_route():
    """ Endpoint to manually update stock levels (simulation). """
    try:
        data = request.get_json()
        updates = data.get('updates') # Expected: [{"product_id": "...", "new_stock": ...}]

        if not updates:
            return jsonify({"error": "No updates provided"}), 400

        # TODO: Implement logic to update the inventory data source (e.g., modify inventory_df)
        # Note: This simple in-memory update won't persist if the server restarts.
        # For the hackathon, maybe just log it or update the in-memory df.
        success = loader.update_inventory_memory(updates) # Need to implement this in loader.py

        if success:
             print(f"Stock updated in memory: {updates}")
             return jsonify({"status": "success"})
        else:
             return jsonify({"error": "Failed to update stock"}), 500

    except Exception as e:
        print(f"Error in /stock_update: {e}")
        return jsonify({"error": "Internal server error"}), 500
    

@api_bp.route('/merchant/ask', methods=['POST'])
def handle_ask():
    """ Endpoint to handle free-form questions from the merchant. """
    merchant_id = session.get('merchant_id', config.CURRENT_DEMO_MERCHANT_ID) # Get current merchant ID
    if not merchant_id:
         return jsonify({"error": "Merchant context not found"}), 400

    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        # ===> PROCESSING HAPPENS HERE <===
        # Delegate the processing to a dedicated function/module
        answer = query_processor.process_merchant_question(merchant_id, question)

        return jsonify({"answer": answer})

    except Exception as e:
        print(f"Error processing question '{question}' for {merchant_id}: {e}")
        # Provide a generic error message
        return jsonify({"answer": "Sorry, I encountered an error trying to answer that question."}), 500