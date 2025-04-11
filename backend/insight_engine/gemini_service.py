import google.generativeai as genai
from backend import config
import os

# Configure the Gemini client
try:
    if config.GEMINI_API_KEY:
        genai.configure(api_key=config.GEMINI_API_KEY)
        # Optional: Set safety settings if needed
        safety_settings = [
             {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
             {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
             {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
             {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        model = genai.GenerativeModel(
             model_name="gemini-2.0-flash", # Or another suitable model
             safety_settings=safety_settings
        )
        print("Gemini client configured.")
    else:
        model = None
        print("Warning: GEMINI_API_KEY not found in config. AI features will be disabled.")

except Exception as e:
    print(f"Error configuring Gemini client: {e}")
    model = None

def generate_text(prompt):
    """ Sends a prompt to the Gemini API and returns the text response. """
    if not model:
        print("Gemini model not available.")
        # Return a default message or raise an error
        return "AI service is unavailable."

    try:
        # Set generation config if needed (temperature, max output tokens, etc.)
        # generation_config = genai.types.GenerationConfig(max_output_tokens=200, temperature=0.7)
        response = model.generate_content(prompt) # Add generation_config=generation_config if used

        # Basic check for response content
        if response.parts:
            # Handle potential multi-part responses if necessary, usually text is in the first part
            return response.text
        else:
            # Handle cases where the response might be blocked or empty
            print(f"Gemini response empty or blocked. Finish reason: {response.prompt_feedback}")
            return "AI could not generate a response for this request."

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return f"Error generating text: {e}" # Return error message