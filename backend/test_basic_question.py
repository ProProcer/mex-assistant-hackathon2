import pytest
import os
import sys
import pandas as pd

# --- Add backend directory to Python path ---
# This allows importing modules from the backend package
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir) # Should be the root 'backend' folder
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
# --- End Path Setup ---

# Now import modules from your backend structure
from data_access import loader
from insight_engine import gemini_service
from backend import config # To access config values if needed

# --- Test Setup Fixture ---
@pytest.fixture(scope="module", autouse=True)
def setup_data():
    """
    Fixture to load data once before tests in this module run.
    'autouse=True' makes it automatically apply to all tests here.
    'scope="module"' ensures it runs only once for this file.
    """
    print("\nSetting up data for basic question tests...")
    try:
        loader.load_all_data()
        # Verify data loaded
        assert loader.get_merchants_df() is not None
        assert loader.get_products_df() is not None
        print("Mock data loaded successfully.")
    except Exception as e:
        pytest.fail(f"Failed to load mock data: {e}")

# --- Test Functions ---

# Use parametrize to easily test different merchants
@pytest.mark.parametrize("merchant_id", ["1a3f7", "8d5f9"]) # Add more valid IDs from your mock data
def test_ask_cuisine_type(merchant_id):
    """Tests asking about the merchant's cuisine type."""
    question = "What type of cuisine do I sell?"

    # --- Get Context ---
    merchants_df = loader.get_merchants_df()
    try:
        merchant_info = merchants_df[merchants_df['merchant_id'] == merchant_id].iloc[0]
        expected_cuisine = merchant_info.get('cuisine_type', 'Unknown') # Get expected value from data
        merchant_name = merchant_info.get('merchant_name', 'this merchant')
        context = f"The merchant '{merchant_name}' (ID: {merchant_id}) is asking a question. Their data indicates they primarily sell {expected_cuisine} cuisine."
    except IndexError:
        pytest.fail(f"Merchant ID {merchant_id} not found in mock data.")
    except Exception as e:
        pytest.fail(f"Error getting merchant context for {merchant_id}: {e}")

    # --- Build Prompt ---
    prompt = f"""
You are an AI assistant for a GrabFood merchant.
Context: {context}

Question from merchant: "{question}"

Based *only* on the provided context, answer the merchant's question directly and concisely in one sentence.
"""

    # --- Call AI Service ---
    response = gemini_service.generate_text(prompt)
    print(f"\n[Test: Cuisine - {merchant_id}] Prompt:\n{prompt}\n[Test: Cuisine - {merchant_id}] Response:\n{response}") # Print for debugging

    # --- Assertions ---
    assert isinstance(response, str)
    assert "AI service is unavailable" not in response # Check if Gemini call succeeded
    assert expected_cuisine.lower() in response.lower() # Check if the actual cuisine type is mentioned

@pytest.mark.parametrize("merchant_id", ["1a3f7", "8d5f9"])
def test_ask_merchant_name(merchant_id):
    """Tests asking about the merchant's own name."""
    question = "What is my shop name?"

    # --- Get Context ---
    merchants_df = loader.get_merchants_df()
    try:
        merchant_info = merchants_df[merchants_df['merchant_id'] == merchant_id].iloc[0]
        expected_name = merchant_info.get('merchant_name', 'Unknown Store Name')
        context = f"Merchant with ID {merchant_id} is asking a question. Their registered name is '{expected_name}'."
    except IndexError:
        pytest.fail(f"Merchant ID {merchant_id} not found.")

    # --- Build Prompt ---
    prompt = f"""
You are an AI assistant for a GrabFood merchant.
Context: {context}

Question from merchant: "{question}"

Based *only* on the provided context, answer the merchant's question directly and concisely.
"""
    # --- Call AI Service ---
    response = gemini_service.generate_text(prompt)
    print(f"\n[Test: Name - {merchant_id}] Prompt:\n{prompt}\n[Test: Name - {merchant_id}] Response:\n{response}")

    # --- Assertions ---
    assert isinstance(response, str)
    assert "AI service is unavailable" not in response
    # Check if the core part of the name is present (case-insensitive)
    # Split expected name in case it has generic words like "Test Merchant"
    name_parts = expected_name.split()
    assert any(part.lower() in response.lower() for part in name_parts if len(part) > 3) # Check for significant parts

# Example test requiring data join/calculation (more complex)
@pytest.mark.parametrize("merchant_id", ["8d5f9"])
def test_ask_number_of_items(merchant_id):
    """Tests asking how many items are on the menu."""
    question = "How many different items do I have on my menu?"

    # --- Get Context (Requires calculation) ---
    products_df = loader.get_products_df()
    try:
        merchant_items = products_df[products_df['merchant_id'] == merchant_id]
        expected_item_count = len(merchant_items)
        context = f"Merchant {merchant_id} is asking a question. According to product data, they have {expected_item_count} distinct items listed."
    except Exception as e:
        pytest.fail(f"Error calculating item count for {merchant_id}: {e}")

    # --- Build Prompt ---
    prompt = f"""
You are an AI assistant for a GrabFood merchant.
Context: {context}

Question from merchant: "{question}"

Based *only* on the provided context, answer the merchant's question directly and state the number.
"""
    # --- Call AI Service ---
    response = gemini_service.generate_text(prompt)
    print(f"\n[Test: Item Count - {merchant_id}] Prompt:\n{prompt}\n[Test: Item Count - {merchant_id}] Response:\n{response}")

    # --- Assertions ---
    assert isinstance(response, str)
    assert "AI service is unavailable" not in response
    assert str(expected_item_count) in response # Check if the number is mentioned

# Add more tests here for:
# - Average rating (requires merchant data)
# - Specific product price (requires joining/lookup)
# - Opening hours (requires adding this data to merchant.csv/generate_data.py)
# - Yesterday's sales (requires metric calculation first) - might be better tested via the report/anomaly API tests