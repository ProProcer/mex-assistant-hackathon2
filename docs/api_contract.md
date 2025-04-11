# API Contract

**Base URL:** `/api`

---

**GET /merchant/basic_info**
- **Description:** Retrieves basic profile information for the logged-in/selected merchant.
- **Response (200 OK):**
  ```json
  {
    "merchant_id": "M1001",
    "merchant_name": "Sedap Corner",
    "merchant_type": "Hawker Stall",
    "cuisine_type": "Malay",
    "location_zone": "Central",
    "size": "Small",
    "business_maturity_years": 2,
    "average_rating": 4.5
  }
  ```
- **Response (404 Not Found):**
  ```json
  { "error": "Merchant not found" }
  ```

---

**GET /merchant/daily_report**
- **Description:** Gets the calculated report for the previous day.
- **Response (200 OK):**
  ```json
  {
    "report_date": "2025-03-10",
    "basic_info": { "...": "..." }, // Subset of basic info if needed
    "sales_today": 155.75,
    "orders_today": 22,
    "sales_trend_data": { // Data for Chart.js
      "labels": ["2025-03-04", "...", "2025-03-10"],
      "data": [120.5, "...", 155.75]
    },
    "item_sales_trend_data": { // Data for Chart.js (Optional)
      "labels": ["2025-03-04", "...", "2025-03-10"],
      "datasets": [
         {"label": "Nasi Lemak", "data": [15, "...", 20], "borderColor": "red"},
         {"label": "Teh Tarik", "data": [30, "...", 25], "borderColor": "blue"}
      ]
    },
    "stock_forecast": [
      {"product_name": "Nasi Lemak", "current_stock": 4, "days_left_forecast": 1},
      {"product_name": "Mee Goreng", "current_stock": 10, "days_left_forecast": 3}
    ],
    "top_products_pareto": { // Data for Chart.js
      "labels": ["Nasi Lemak", "Mee Goreng", "Teh Tarik", "..."],
      "data": [45.5, 70.1, 85.3, "..."] // Cumulative percentages
    },
    "word_of_encouragement": "Sales look steady! Keep focusing on quality."
  }
  ```
- **Response (500 Internal Server Error):**
  ```json
  { "error": "Failed to generate full report." }
  ```

---

**POST /merchant/check_anomalies**
- **Description:** Triggers an analysis for recent anomalies.
- **Response (200 OK):**
  ```json
  {
    "alerts": [
      {
        "type": "sales_drop_dod",
        "message": "Alert: Sales dropped significantly yesterday!",
        "reason": "This seems mainly driven by lower sales in the 'Main Course' category.",
        "recommendation": "Consider reviewing prices or running a small promotion for your main courses."
      },
      {
        "type": "low_stock",
        "message": "Alert: Stock for 'Nasi Lemak' is running low!",
        "reason": "This is one of your bestsellers and stock is down to 4 units.",
        "recommendation": "Reorder ingredients for Nasi Lemak soon to avoid missing sales."
      }
      // Or an empty list: "alerts": []
    ]
  }
  ```

---

**POST /merchant/stock_update**
- **Description:** Simulates a manual stock update by the merchant.
- **Request Body:**
  ```json
  {
    "updates": [
      {"product_id": "M1001-P001", "new_stock": 50},
      {"product_id": "M1001-P002", "new_stock": 100}
    ]
  }
  ```
- **Response (200 OK):**
  ```json
  { "status": "success" }
  ```
- **Response (400 Bad Request):**
  ```json
  { "error": "No updates provided" }
  ```
- **Response (500 Internal Server Error):**
  ```json
  { "error": "Failed to update stock" }
  ```