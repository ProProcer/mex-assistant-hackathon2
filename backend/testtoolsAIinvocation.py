import sys
import os
import traceback
import json # <-- Import json

# --- Add Project Root to Python Path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# --- End Path Setup ---

# --- Core Imports ---
from backend.data_access import loader
from backend.insight_engine import query_processor
from backend import config

# --- Configuration ---
TEST_MERCHANT_ID = "1a3f7"

if __name__ == "__main__":
    print("--- Starting AI Tool Invocation Test Script ---")

    # 1. Check for API Key
    if not config.GEMINI_API_KEY:
        print("\n[FATAL] GEMINI_API_KEY not found...") # Abbreviated error
        sys.exit(1)
    else:
        print("[OK] Gemini API Key found.")

    # 2. Load Data
    try:
        loader.load_all_data()
        print("[OK] Mock data loaded successfully.")
    except Exception as e:
        print(f"[FATAL] Error loading mock data: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 3. Define Test Questions
    questions = [
        # Daily Report Questions
        "Show me the daily report.",
        "Generate the report for yesterday.",
        "What's my daily summary?",
        # Anomaly Questions
        "Are there any anomalies?",
        "Check for operational issues.",
        "Any problems yesterday?",
        # Run Code Question
        "What were my total sales between 2025-04-01 and 2025-04-05?",
        # Simple Question
        "Hello there",
    ]

    print("\n--- Running Test Questions ---")
    print("!!! IMPORTANT: Watch the console output below for AI 'Thinking:', 'CALL_FUNCTION:', 'Executing...', and '<-- Tool Execution Result:' lines !!!")
    print("---------------------------------------------------------------------------------------------------------")

    # 4. Loop and Process Questions
    for i, question in enumerate(questions):
        print(f"\n--- Test {i+1}/{len(questions)} ---")
        print(f"Question: '{question}' for Merchant '{TEST_MERCHANT_ID}'")
        print("--- AI Processing Log (from query_processor prints)... ---")
        try:
            # Call the main query processor function
            final_answer = query_processor.process_merchant_question(TEST_MERCHANT_ID, question)

            print("--- ...End AI Processing Log ---")

            # --- MODIFICATION: Simplify Report Output ---
            is_report = False
            try:
                # Try to parse the answer as JSON
                parsed_answer = json.loads(final_answer)
                # Check if it looks like our report structure
                if isinstance(parsed_answer, dict) and "report_date" in parsed_answer and "basic_info" in parsed_answer:
                    is_report = True
                    report_date_str = parsed_answer.get("report_date", "N/A")
                    report_error = parsed_answer.get("error")
                    print(f"Final Answer Returned: [Daily Report Data for {report_date_str}] (Status: {'ERROR' if report_error else 'OK'})")
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, it's not the raw report data
                pass # is_report remains False

            if not is_report:
                # Print non-report answers normally
                print(f"Final Answer Returned: {final_answer}")
            # --- END MODIFICATION ---

        except Exception as e:
            print(f"\n[FAIL] UNEXPECTED ERROR processing question '{question}': {e}")
            traceback.print_exc()
        print("-----------------------------")

    print("\n--- AI Tool Invocation Test Script Finished ---")