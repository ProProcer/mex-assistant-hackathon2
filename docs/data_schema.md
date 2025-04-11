# Data Schemas (CSV)

## merchants.csv
- `merchant_id` (string, PK): Unique ID (e.g., M1001)
- `merchant_name` (string): Store Name
- `merchant_type` (string): e.g., Hawker Stall, Restaurant, Cafe
- `cuisine_type` (string): e.g., Malay, Western, Chinese
- `location_zone` (string): e.g., Central, East
- `size` (string): e.g., Small, Medium, Large
- `business_maturity_years` (integer): Years in business
- `average_rating` (float): Overall store rating

## products.csv
- `product_id` (string, PK): Unique ID (e.g., M1001-P001)
- `merchant_id` (string, FK): Links to merchants.csv
- `product_name` (string): Item Name
- `category` (string): e.g., Main Course, Beverage
- `price` (float): Price of the item
- `is_new` (boolean): If the item was recently added
- `dietary_tags` (string): Comma-separated tags (e.g., "Halal,Vegetarian")

## orders.csv (Exploded - One row per item in an order)
- `order_id` (string): ID for the order transaction
- `merchant_id` (string, FK): Links to merchants.csv
- `timestamp` (string, ISO 8601 format - YYYY-MM-DDTHH:MM:SSZ): Time order placed
- `product_id` (string, FK): Links to products.csv
- `quantity` (integer): Quantity of this specific product in the order (usually 1 if exploded)
- `item_price` (float): Price of one unit of this product at the time of order
- `total_amount` (float): Amount for this line item (item_price * quantity)
- `order_type` (string): e.g., Delivery, Self Pick-up
- `prep_time_minutes` (integer): Time in minutes, null if not accepted
- `acceptance_status` (string): e.g., Accepted, Missed
- `issue_reported` (string): e.g., None, Missing Item

## inventory.csv
- `product_id` (string, PK/FK): Links to products.csv
- `current_stock` (integer): Estimated current units
- `last_updated` (string, ISO 8601 format): Timestamp of last update/check

## ratings.csv (Optional)
- `rating_id` (string, PK)
- `order_id` (string, FK): Links to orders.csv
- `merchant_id` (string, FK)
- `rating_value` (integer): e.g., 1-5
- `comment` (string): Customer feedback text
- `timestamp` (string, ISO 8601 format)