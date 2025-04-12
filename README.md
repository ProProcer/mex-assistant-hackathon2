# MEX Assistant Hackathon Project

## Description

MEX Assistant is a web-based application designed for GrabFood merchants in Southeast Asia. It provides data-driven insights, operational analytics, and an AI-powered chat assistant to help merchants make informed business decisions and streamline their operations. The application features a Flask backend for data processing and API endpoints, and a vanilla JavaScript frontend for user interaction.

## Features

* *Merchant Dashboard:* Displays key information and provides access to different functionalities.
* *Daily Reports:* Generates daily summaries including sales, order counts, trends, and stock forecasts (though the actual data calculation is noted as in-progress in the template within query_processor.py).
* *Anomaly Detection:* Identifies potential operational issues like sales drops or low stock levels.
* *Inventory Management:* Allows viewing current stock levels and updating/adding new stock items.
* *Low Stock Notifications:* Enables setting up rules to get notified when stock for specific items falls below a threshold.
* *AI Assistant Chat:* A chatbot interface (powered by Google Gemini) allowing merchants to ask questions about their business data and receive insights.
* *Data Visualization:* Uses Chart.js to display trends like sales over time and Pareto analysis.

## Data Schema

The application utilizes several CSV files for data storage, typically located in the mock_data/ directory as defined in backend/config.py[cite: 1]. The primary schemas, accessible via the loader object in the backend (backend/data_access/loader.py [cite: 1]), are:

* **Inventory (loader.get_inventory_df())**
    * merchant_id (object): Merchant identifier.
    * stock_name (object): Name of the stock item (e.g., 'Cheese').
    * stock_quantity (int64): Recorded quantity of the item.
    * units (object): Unit of measurement (e.g., 'kg').
    * date_updated (datetime64[ns, UTC]): Timestamp of the stock level log entry.
    * Note: This represents a log of stock changes. The current quantity for an item is the entry with the latest date_updated.

* **Items / Products (loader.get_items_df() or loader.get_products_df())**
    * item_id (int64): Unique identifier for the item.
    * cuisine_tag (object): Tag associated with the item's cuisine (e.g., 'Side', 'American').
    * item_name (object): Display name of the item (e.g., 'Fried Spring Rolls').
    * item_price (float64): Price of the item (assumed USD).
    * merchant_id (object): Merchant identifier.

* **Merchants (loader.get_merchant_df() or loader.get_merchants_df())**
    * merchant_id (object): Unique merchant identifier.
    * merchant_name (object): Name of the merchant's store.
    * join_date (datetime64[ns, UTC]): Date the merchant joined.
    * city_id (int64): Identifier for the city.
    * merchant_type (object): Type of merchant (e.g., 'Home-Based Kitchen', 'Restaurant').
    * city_name (object): Name of the city (e.g., 'Bandar Seri Begawan', 'Manila').

* **Notifications (loader.get_notifications_df())**
    * id (integer): Unique identifier for the notification rule (e.g., 1).
    * merchant_id (object): Merchant identifier (e.g., '1d4f2').
    * productName (object): Name of the product the rule applies to (e.g., 'Coffee Beans').
    * threshold (integer/float): The quantity level below which to notify (e.g., 1).
    * enabled (boolean): Whether the notification rule is active (e.g., TRUE).
    * units (object): Unit of measurement (e.g., 'kg').

* **Order Items (loader.get_order_items_df())**
    * order_id (object): Identifier linking items to a specific order in the transaction data.
    * item_id (int64): Identifier for the item ordered.
    * merchant_id (object): Merchant identifier.
    * item_price (float64): Price of the item at the time of the order.

* **Transaction Data (loader.get_transaction_data_df())**
    * order_id (object): Unique identifier for the order.
    * order_time (datetime64[ns, UTC]): Timestamp when the order was placed.
    * driver_arrival_time (datetime64[ns, UTC]): Timestamp driver arrived at merchant.
    * driver_pickup_time (datetime64[ns, UTC]): Timestamp driver picked up the order.
    * delivery_time (datetime64[ns, UTC]): Timestamp order was delivered.
    * order_value (float64): Total value of the order (sum of all item prices in that order, assumed USD).
    * eater_id (int64): Identifier for the customer.
    * merchant_id (object): Merchant identifier.
    * prep_duration_minutes (float64): Calculated preparation time.
    * delivery_duration_minutes (float64): Calculated delivery time.
    * total_duration_minutes (float64): Calculated total time from order to delivery.
    * acceptance_status (object): Status like 'Accepted', 'Missed'. (Assumed 'Accepted' if column is missing).

## Setup and Operation (for Hackathon)

1.  *Clone:* Clone this repository to your local machine.
2.  *Environment:*
    * Navigate to the project root (mex-assistant-hackathon2/).
    * Create a Python virtual environment: python -m venv .venv
    * Activate the environment:
        * Windows: .venv\Scripts\activate
        * macOS/Linux: source .venv/bin/activate
3.  *Dependencies:* Install required packages: pip install -r backend/requirements.txt [cite: 1]
4.  *API Key:*
    * Create a .env file in the project root directory (mex-assistant-hackathon2/).
    * Add your Google Gemini API key to the .env file:
        
        GEMINI_API_KEY=YOUR_API_KEY_HERE
        
    * The application uses python-dotenv to load this key (backend/config.py[cite: 1], backend/insight_engine/gemini_service.py [cite: 1]).
5.  *Data Files:*
    * Ensure the necessary CSV data files (merchant.csv, items.csv, transaction_data.csv, inventory.csv, transaction_items.csv, notifications.csv etc.) are present in the mock_data/ directory. The paths are configured in backend/config.py[cite: 1].
    * You can download the required data files from this Google Drive link: [Hackathon Data](https://drive.google.com/drive/folders/1k2sXTX0gsV-fgIrVzgk8KNUIgWtvELiZ?usp=sharing)
6.  *Run Backend:*
    * Navigate to the backend/ directory if you aren't already there.
    * Run the Flask application: python app.py [cite: 1]
7.  *Access Frontend:*
    * Open your web browser and go to http://127.0.0.1:5000/ (or the address provided by Flask).
    * The application interface should load, allowing interaction with the different features.

## API Contract

For details on the available backend API endpoints, please refer to the docs/api_contract.md file[cite: 1].
