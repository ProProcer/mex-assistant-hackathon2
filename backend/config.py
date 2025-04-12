# backend/config.py
import os
from pathlib import Path
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Gemini API ---
# --- Environment Variables ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Project Structure ---
# Determine the project root directory dynamically.
# This assumes config.py is within backend/
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent.parent
MOCK_DATA_DIR = PROJECT_ROOT / "mock_data"

# --- Data File Paths ---
MERCHANT_CSV = MOCK_DATA_DIR / "merchant.csv"
ITEMS_CSV = MOCK_DATA_DIR / "items.csv"
TRANSACTION_DATA_CSV = MOCK_DATA_DIR / "transaction_data.csv"
INVENTORY_CSV = MOCK_DATA_DIR / "inventory.csv"
HOLIDAYS_CSV = MOCK_DATA_DIR / "holidays.csv"
KEYWORDS_CSV = MOCK_DATA_DIR / "keywords.csv"
NOTIFICATIONS_CSV = MOCK_DATA_DIR / "notifications.csv"
# Define the path relative to MOCK_DATA_DIR
TRANSACTION_ITEMS_CSV = MOCK_DATA_DIR / "transaction_items.csv" # <-- CORRECTED LINE

# --- Anomaly Detection Thresholds ---
LOW_STOCK_THRESHOLD = 5
SALES_DROP_THRESHOLD_PERCENT = -20.0
PREP_TIME_INCREASE_THRESHOLD_PERCENT = 10.0
ACCEPTANCE_RATE_THRESHOLD_PERCENT = 90.0

# --- Reporting Configuration ---
STOCK_FORECAST_DAYS = 3

# --- Date and Time Formats ---
MERCHANT_JOIN_DATE_FORMAT = "%Y-%m-%d"  # Assuming format like 2023-11-07
ORDER_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # Assuming format like 2023-11-07T09:49:00Z

# --- Data Analysis Lookback Periods (in days) ---
SALES_TREND_DAYS = 14
ITEM_SALES_TREND_DAYS = 30

# --- Word of Encouragement (for reports) ---
ENCOURAGEMENT_MESSAGE = "You're doing great! Keep analyzing those metrics."




# --- Example Usage (for testing config) ---
if __name__ == "__main__":
    print("--- Configuration ---")
    print(f"GEMINI_API_KEY (exists): {bool(GEMINI_API_KEY)}")
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Mock Data Directory: {MOCK_DATA_DIR}")
    print(f"Merchant CSV Path: {MERCHANT_CSV}")
    print(f"Items CSV Path: {ITEMS_CSV}")
    print(f"Transaction Data CSV Path: {TRANSACTION_DATA_CSV}")
    print(f"Inventory CSV Path: {INVENTORY_CSV}")
    # if 'ORDER_ITEMS_CSV' in locals():
    #     print(f"Order Items CSV Path: {ORDER_ITEMS_CSV}")
    print(f"Low Stock Threshold: {LOW_STOCK_THRESHOLD}")
    print(f"Sales Drop Threshold: {SALES_DROP_THRESHOLD_PERCENT}%")
    print(f"Stock Forecast Days: {STOCK_FORECAST_DAYS}")
    print(f"Merchant Join Date Format: {MERCHANT_JOIN_DATE_FORMAT}")
    print(f"Order Time Format: {ORDER_TIME_FORMAT}")
    print(f"Sales Trend Lookback: {SALES_TREND_DAYS} days")
    print(f"Encouragement Message: {ENCOURAGEMENT_MESSAGE}")