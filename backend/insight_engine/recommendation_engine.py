from . import gemini_service
from data_access import loader # May need merchant info for context

def get_reason_and_recommendation(anomaly_details, merchant_id):
    """
    Uses Gemini to generate a likely reason and actionable recommendation
    based on the detected anomaly details.
    """
    if not anomaly_details:
        return None

    # --- Get Merchant Context (Optional but helpful for personalization) ---
    try:
        merchant_df = loader.get_merchants_df()
        merchant_info = merchant_df[merchant_df['merchant_id'] == merchant_id].iloc[0]
        merchant_context = f"The merchant '{merchant_info['merchant_name']}' is a {merchant_info['size']} {merchant_info['merchant_type']} selling {merchant_info['cuisine_type']} cuisine."
    except Exception:
        merchant_context = "The merchant runs a food business on Grab." # Fallback

    # --- Build the Prompt ---
    # This needs careful crafting!
    prompt = f"""
You are an AI assistant helping a GrabFood merchant understand their business data.
{merchant_context}

An anomaly was detected:
Anomaly Type: {anomaly_details.get('type', 'N/A')}
Metric: {anomaly_details.get('metric', 'N/A')}
Details: {str(anomaly_details)} # Provide relevant details like value, change, product name etc.
Segmentation Info (if available): {anomaly_details.get('segmentation_info', 'Not available')}

Based *only* on this information:
1. Briefly explain the likely **reason** for this anomaly in simple terms a busy merchant can understand (1 sentence).
2. Suggest **one specific, actionable recommendation** the merchant could take in response (1 sentence). Make it practical.

Format your response exactly like this:
Reason: [Your explanation]
Recommendation: [Your suggestion]
"""

    # --- Call Gemini ---
    raw_response = gemini_service.generate_text(prompt)

    # --- Parse the Response ---
    reason = "AI could not determine a reason."
    recommendation = "No specific recommendation available. Please review your operations." # Default

    try:
        lines = raw_response.split('\n')
        for line in lines:
            if line.lower().startswith("reason:"):
                reason = line.split(":", 1)[1].strip()
            elif line.lower().startswith("recommendation:"):
                recommendation = line.split(":", 1)[1].strip()
    except Exception as e:
        print(f"Error parsing Gemini response: {e}\nRaw response:\n{raw_response}")
        # Use defaults defined above

    # Basic check to ensure AI didn't just repeat the input or fail
    if "AI service is unavailable" in reason or "AI could not generate" in reason:
         return {"reason": reason, "recommendation": recommendation} # Pass along the error state


    # TODO: Add more sophisticated parsing or validation if needed

    return {"reason": reason, "recommendation": recommendation}