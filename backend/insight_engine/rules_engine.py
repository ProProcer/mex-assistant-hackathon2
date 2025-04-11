# backend/insight_engine/rules_engine.py

def check_rules(anomaly_details):
    """
    Checks predefined rules based on anomaly details.
    Returns a reason string if a rule matches, otherwise None.
    """
    anomaly_type = anomaly_details.get("type") # Get the type of anomaly

    # --- Rule Definitions ---

    if anomaly_type == "low_stock":
        # Rule 1: Basic Low Stock Alert
        product_name = anomaly_details.get("product_name", "Unknown Product")
        current_stock = anomaly_details.get("current_value", 0)
        reason = f"Stock level is low for {product_name} ({current_stock} units remaining)."
        # Note: Add checks for 'top seller' here later if that data becomes available
        return reason

    # Example for another rule type (can add later)
    # elif anomaly_type == "low_acceptance_rate":
    #     current_rate = anomaly_details.get("current_value", 0)
    #     threshold = anomaly_details.get("threshold", 90)
    #     if current_rate < threshold - 10: # Example: Significantly low
    #         return f"Acceptance rate ({current_rate}%) is significantly below the target ({threshold}%)."
    #     else:
    #         return f"Acceptance rate ({current_rate}%) is below the target ({threshold}%)."


    # --- No Rule Matched ---
    return None # Indicate that no predefined rule was triggered