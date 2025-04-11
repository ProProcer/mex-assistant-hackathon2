# backend/insight_engine/query_processor.py
import io
import re # Using regex for more robust parsing
import json
import pandas as pd
import numpy as np
import contextlib
import traceback
from datetime import date, timedelta, datetime
import os
import sys
import codecs # Add this import at the top
from backend.reporting.daily_report_generator import generate_daily_report # Adjust path if needed
from backend.core.anomaly_detector import detect_anomalies # Adjust path if needed
# Assuming these modules/objects are correctly imported and available
from . import gemini_service # Your Gemini service
from data_access import loader # Your data loader instance
from core import metrics_calculator # Your metrics calculator
# from reporting import daily_report_generator # Uncomment if needed

MAX_TURNS = 10

# --- Helper to create the get_user_id function ---
# This closure ensures the function created inside run_code knows the correct ID
def _create_get_user_id_func(user_id):
    def get_user_id():
        """Returns the merchant_id for the current context."""
        return user_id
    return get_user_id

# --- Core Processing Logic ---

def process_merchant_question(merchant_id, question):
    """
    Processes a question using a multi-turn prompt strategy with Gemini,
    allowing the LLM to use tools including 'run_code'.
    """
    print(f"Processing question for Merchant ID {merchant_id}: '{question}'")

      # --- Ensure merchant_id is a string ---
    if not isinstance(merchant_id, str):
        print(f"Warning: merchant_id was not a string ({type(merchant_id)}). Converting.")
        merchant_id = str(merchant_id)
    # ---

    current_date_str = date.today().strftime('%Y-%m-%d')
    conversation_history = [{"role": "user", "content": question}]
    current_thinking = "No thinking yet."
    provided_data = "Initial state. No data provided yet."

    # --- Pre-fetch static prompts ---
    briefing = get_briefing_prompt()
    core_principles = get_core_principle_prompt()
    merchant_context = get_merchant_context_prompt(merchant_id)
    data_schemas = get_available_data_schemas_prompt()
    tool_descriptions = get_available_tools_prompt()

    # --- Tool Bypass Instruction (for prompts) ---
    report_exception_instruction = (
        "**Special Case:** If you call `get_daily_report`, the system will "
        "return its raw output directly. Do *not* try to summarize or analyze "
        "the report data yourself in a subsequent 'ANSWER:' step; the raw data "
        "is the final output for that specific tool call."
    )

    for turn in range(MAX_TURNS):
        print(f"\n--- Turn {turn + 1}/{MAX_TURNS} ---")

        # --- Construct the appropriate prompt ---
        if turn == 0:
            # Add instruction about daily report exception here
            prompt = build_initial_prompt(
                briefing=briefing,
                core_principles=core_principles,
                merchant_context=merchant_context,
                current_date=current_date_str,
                data_schemas=data_schemas,
                tool_descriptions=tool_descriptions,
                user_question=question,
                report_exception_instruction= report_exception_instruction 
            )
        else:
             # Add instruction about daily report exception here too
            prompt = build_intermediate_prompt(
                briefing=briefing,
                core_principles=core_principles,
                merchant_context=merchant_context,
                current_date=current_date_str,
                data_schemas=data_schemas,
                tool_descriptions=tool_descriptions,
                original_question=question,
                previous_thinking=current_thinking,
                provided_data=provided_data,
                report_exception_instruction=report_exception_instruction 
            )

        print(">>> Sending Prompt to LLM (first/last 200 chars):")
        print(prompt[:200] + "..." + prompt[-200:])

        # --- Call LLM ---
        try:
             raw_response = gemini_service.generate_text(prompt)
             print("<<< Received Raw Response from LLM:")
             print(raw_response)
        except Exception as e:
             print(f"Error calling LLM service: {e}")
             return f"Sorry, I encountered an error trying to reach my processing service. Please try again later. Error: {e}"


        # --- Parse LLM Response ---
        call_function_match = re.search(r"CALL_FUNCTION:(.*?)(?:ANSWER:|$)", raw_response, re.DOTALL | re.IGNORECASE)
        answer_match = re.search(r"ANSWER:(.*)", raw_response, re.DOTALL | re.IGNORECASE)
        thinking_end_pos = len(raw_response)
        if call_function_match: thinking_end_pos = min(thinking_end_pos, call_function_match.start())
        if answer_match: thinking_end_pos = min(thinking_end_pos, answer_match.start())
        thinking_part = raw_response[:thinking_end_pos].strip()
        if thinking_part.lower().startswith("thinking:"): current_thinking = thinking_part[len("thinking:"):].strip()
        else: current_thinking = thinking_part
        if not current_thinking: current_thinking = "(No thinking steps provided before action/answer)"
        call_function_str = call_function_match.group(1).strip() if call_function_match else None
        final_answer = answer_match.group(1).strip() if answer_match else None
        conversation_history.append({"role": "assistant", "thinking": current_thinking})
        print(f"Parsed Thinking: {current_thinking}")

        # --- Process Action or Answer ---
        if final_answer is not None:
            print(f"--> Final Answer Found: {final_answer}")
            conversation_history.append({"role": "assistant", "final_answer": final_answer})
            return final_answer

        # ================== START OF MODIFIED LOGIC ==================
        elif call_function_str is not None:
            print(f"--> Function Call Requested: {call_function_str}")

            # --- Step 1: Parse the function name (Robustly) ---
            func_match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", call_function_str)
            func_name = func_match.group(1) if func_match else None
            print(f"Parsed Function Name: {func_name}")
            # --- End Step 1 ---

            # --- Step 2: Execute the tool call ---
            # Pass merchant_id here explicitly
            tool_result_string = execute_tool_call(merchant_id, call_function_str)
            print(f"<-- Tool Execution Result (String):\n{tool_result_string[:500]}...") # Log truncated result
            # --- End Step 2 ---

            # --- Step 3: Special handling for get_daily_report ---
            if func_name == "get_daily_report":
                print(f"--> Special Handling: Function '{func_name}' called. Returning result directly.")
                # Log the call and the raw result before returning
                conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": tool_result_string})
                conversation_history.append({"role": "assistant", "final_answer": tool_result_string}) # Log final answer
                return tool_result_string # EXIT the loop immediately, return raw string result
            # --- End Step 3 ---

            # --- Step 4: Handle other tools (continue the loop) ---
            elif func_name is not None: # For any other successfully parsed tool
                print(f"--> Continuing loop for AI to reason on '{func_name}' result.")
                provided_data = tool_result_string # Update provided_data for the next turn
                conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": provided_data})
                # The loop continues automatically...
            # --- End Step 4 ---

            else: # Handle cases where function name couldn't be parsed
                 print(f"Warning: Could not parse function name from call string '{call_function_str}'.")
                 # Log the raw call attempt and the (likely error) result
                 conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": tool_result_string})
                 # Return the error message from execute_tool_call or a generic one
                 return tool_result_string if "Error" in tool_result_string else "Sorry, I encountered an issue processing that tool request."
        # ================== END OF MODIFIED LOGIC ==================

        else:
            # LLM didn't provide CALL_FUNCTION or ANSWER
            print("Warning: LLM did not provide a clear CALL_FUNCTION or ANSWER keyword.")
            conversation_history.append({"role": "system", "status": "Ambiguous response from LLM"})
            return f"I'm still processing that. Here's my current thinking:\n{current_thinking}\n(Could not determine the next step...)"

    # --- Max turns reached ---
    print("Maximum turns reached without a final answer.")
    conversation_history.append({"role": "system", "status": "Max turns reached"})
    return f"I seem to be stuck in a loop trying to figure that out. My last thought process was:\n{current_thinking}\nCould you perhaps simplify your question or ask about a specific metric?"


# --- Prompt Building Helpers ---

# Updated to accept pre-fetched components and use f-strings correctly
def build_initial_prompt(briefing, core_principles, merchant_context, current_date, data_schemas, tool_descriptions, user_question, report_exception_instruction):
    # Added a dedicated section for run_code rules
    return f"""
{briefing}

**Your Core Principles:**
{core_principles}

**Merchant Context:**
{merchant_context}

**Current Date:** {current_date}

**Available Data Schemas (via `loader` object in `run_code`):**
{data_schemas}

**Available Tools:**
{tool_descriptions}

**Instructions:**
1.  Analyze the merchant's question ({user_question}), keeping your core principles in mind.
2.  Outline your step-by-step thinking process under the `Thinking:` heading.
3.  Determine the **single, first** tool call required.
4.  Use `CALL_FUNCTION: tool_name(parameters)` to request this.
5.  **`run_code` Tool Specific Rules (VERY IMPORTANT):** Follow validity, simplicity, breakdown, schema, import, `get_user_id()`, and output rules.
6.  **{report_exception_instruction}** # Include the special case instruction
7.  Do NOT provide an answer yet unless no data is needed. Focus *only* on the first required tool call.
8.  Ensure your response format is strictly `Thinking: ...` followed by `CALL_FUNCTION: ...` or `ANSWER: ...`.

**Merchant's Question:**
{user_question}

**Your Response:**
Thinking:
"""

# Updated to accept the report_exception_instruction
def build_intermediate_prompt(briefing, core_principles, merchant_context, current_date, data_schemas, tool_descriptions, original_question, previous_thinking, provided_data, report_exception_instruction):
    # Added stricter rules for run_code and error handling
    return f"""
{briefing}

Continue reasoning to answer the merchant's question: "{original_question}"

**Your Core Principles:**
{core_principles}

**Merchant Context:**
{merchant_context}

**Current Date:** {current_date}

**Available Data Schemas (via `loader` object in `run_code`):**
{data_schemas}

**Available Tools:**
{tool_descriptions}

**Original Question:** {original_question}

**Conversation History (Summary):**
*   **Previous Thinking:**
{previous_thinking}
*   **Data/Result Provided (Result of your last tool call):**
{provided_data}

**Instructions:**
1.  **REVIEW** the `Provided Data` and `Previous Thinking`. Is the information needed already present?
2.  Continue your reasoning under `Thinking:`.
3.  **Determine the *single next* logical step:**
    *   **Need More Info?** State `CALL_FUNCTION: tool_name(parameters)`. Follow `run_code` rules if applicable.
    *   **Ready to Answer?** State `ANSWER:` followed by the final, clear response.
    *   **Handle Errors:** If `Provided Data` shows an error, analyze it, explain the correction in `Thinking:`, and issue a corrected `CALL_FUNCTION: run_code(...)`. Give up after 1-2 tries if the same error persists.
4.  **{report_exception_instruction}** # Include the special case instruction
5.  Ensure response format is strictly `Thinking: ...` followed by *either* `CALL_FUNCTION: ...` *or* `ANSWER: ...`.

**Your Response:**
Thinking:
"""
# --- Static Prompt Content Helpers ---

def get_briefing_prompt():
    # No changes needed here
    return """
You are MEX Assistant, an AI partner designed specifically for GrabFood merchants in Southeast Asia.
Your primary goal is to provide proactive, actionable insights and personalized guidance to help
merchants make better business decisions and streamline operations. Remember to give natural flow in the cat and use colloquial if possible
"""

def get_merchant_context_prompt(merchant_id):
    # Slightly improved error handling and clarity
    # Assume loader is accessible
    cities = np.array(["Singapore", "Kuala Lumpur", "Jakarta", 
                        "Manila", "Naypyidaw", "Vientiane", "Phnom Penh", "Bandar Seri Begawan"])

    try:
        merchant_df = loader.get_merchants_df() # Use actual loader function name
        items_df = loader.get_products_df() # Use actual loader function name

        merchant_info = merchant_df[merchant_df['merchant_id'] == merchant_id] # Use correct column name
        if merchant_info.empty:
            print(f"Warning: Merchant ID {merchant_id} not found in merchants data.")
            return f"Merchant ID: {merchant_id}. (Details not found)."

        merchant_info = merchant_info.iloc[0] # Get the first row as a Series

        # --- City Name Logic ---
        city_id = merchant_info.get('city_id')
        city_name = merchant_info.get('city_name') # Check if it already exists

        if pd.isna(city_name) or city_name == "Unknown City": # If missing or default unknown
             if pd.notna(city_id):
                 try:
                     city_id_int = int(city_id)
                     city_name = cities.get(city_id_int, "Unknown City") # Use your city map/data
                 except (ValueError, TypeError):
                     city_name = "Unknown City (Invalid ID)"
             else:
                 city_name = "Unknown City"
        # --- End City Name Logic ---

        items = items_df[items_df['merchant_id'] == merchant_id] # Use correct column name
        menu_items = []
        if not items.empty:
            max_items_in_prompt = 5 # Reduced for brevity
            # Use correct item/product column names from items.csv/products.csv
            for _, item in items.head(max_items_in_prompt).iterrows():
                 item_name = item.get('product_name', item.get('item_name', 'N/A')) # Check both common names
                 item_id = item.get('product_id', item.get('item_id', 'N/A')) # Check both common names
                 price = item.get('price', item.get('item_price', 'N/A')) # Check both common names
                 item_desc = f"{item_name} (ID: {item_id}, Price: {price})"
                 menu_items.append(item_desc)
            if len(items) > max_items_in_prompt:
                 menu_items.append(f"... and {len(items) - max_items_in_prompt} more items.")
        else:
            menu_items.append("No menu items found.")

        menu_summary = "; ".join(menu_items)

        # Get other attributes, using .get() for safety
        merchant_name = merchant_info.get('merchant_name', 'N/A')
        merchant_type = merchant_info.get('merchant_type', 'N/A')
        cuisine_type = merchant_info.get('cuisine_type', 'N/A')

        prompt = (f"Merchant ID: {merchant_id}. Name: {merchant_name}. "
                  f"Type: {merchant_type}. Cuisine: {cuisine_type}. Location: {city_name}. "
                  f"Menu Sample: {menu_summary}")
        return prompt

    except Exception as e:
        print(f"Error fetching merchant context for {merchant_id}: {e}\n{traceback.format_exc()}")
        return f"Merchant ID: {merchant_id}. (Error retrieving details: {e})"

def get_core_principle_prompt():
    # No changes needed here
    return """
*   **Be Proactive:** Identify potential issues or opportunities even if not explicitly asked.
*   **Be Actionable:** Provide clear, concrete recommendations, not just data points.
*   **Be Personalized:** Consider the merchant's context (location, menu sample provided).
*   **Be Clear & Simple:** Communicate insights in easy-to-understand language, avoiding jargon. Assume varying levels of digital literacy. Be concise.
*   **Be Accurate:** Base your analysis strictly on the provided data schemas and the results from requested tools. Do not invent data or hallucinate functionality.
*   **Be Strategic:** Think step-by-step about how to best answer the merchant's query using the available resources. Only call one tool at a time.
"""

def get_available_data_schemas_prompt(loader_module=loader, max_examples=2):
    # Added 'loader.' prefix to function names for clarity in the prompt
    # Added more robust error handling and dynamic checking
    if loader_module is None:
        return "Error: No data loader module provided."

    df_function_names = []
    # Introspect the loader module for functions matching the pattern
    for func_name in dir(loader_module):
        # Match functions like get_X_df, get_X_data_df etc.
        if re.match(r"get_.*df$", func_name):
            attribute = getattr(loader_module, func_name)
            if callable(attribute) and not func_name.startswith('_'): # Avoid private methods
                df_function_names.append(func_name)

    if not df_function_names:
        return "No public data loading functions (like 'get_*_df') found in the loader module."

    prompt_parts = ["Schema available via `loader` object within the `run_code` tool:\n"]
    for func_name in sorted(df_function_names):
        prompt_parts.append(f"--- Function: loader.{func_name}() ---")
        try:
            func_object = getattr(loader_module, func_name)

            # --- Attempt to call the function to get the DataFrame ---
            # Add basic argument handling if some functions require them (e.g., merchant_id)
            # This part is tricky without knowing exact signatures. We'll assume no args for schema gen.
            # If functions *require* args, this schema generation will fail for them.
            try:
                 df = func_object() # Assume it can be called without args for schema
            except TypeError as te:
                 # Basic check if it failed due to missing arguments
                 if "required positional argument" in str(te) or "missing" in str(te).lower():
                     prompt_parts.append(f"  Note: This function likely requires arguments (e.g., merchant_id) and cannot be introspected without them.")
                     continue # Skip to next function
                 else:
                     raise # Re-raise other TypeErrors
            except Exception as call_e:
                 prompt_parts.append(f"  Error calling loader.{func_name}() for schema: {type(call_e).__name__}")
                 continue # Skip to next function


            if not isinstance(df, pd.DataFrame):
                prompt_parts.append("  Error: Did not return a pandas DataFrame.")
                continue

            if df.empty:
                 prompt_parts.append(f"  Columns: {', '.join(df.columns)} (Returned Empty DataFrame or no data loaded yet)")
                 continue

            prompt_parts.append("  Columns and Example Values (from loaded sample):")
            # Use a smaller sample to avoid overwhelming the prompt
            sample_df = df.head(max_examples * 2)

            for col in df.columns:
                # Get unique, non-null examples from the sample
                unique_examples = sample_df[col].dropna().unique()[:max_examples]

                example_strs = []
                if len(unique_examples) > 0:
                     example_strs = [repr(ex) for ex in unique_examples]
                elif not sample_df[col].isnull().all(): # If no unique non-null, check if there are any values at all
                    example_strs = [repr(ex) for ex in sample_df[col].unique()[:max_examples]] # Show potential nulls/duplicates if that's all there is
                    if not example_strs: example_strs.append("(No values in sample)")
                elif sample_df[col].empty:
                     example_strs.append("(Column is empty)")
                else: # All nulls in sample
                     example_strs.append("(All nulls in sample)")

                # Show dtype as well
                col_dtype = str(df[col].dtype)
                prompt_parts.append(f"    - {col} (dtype: {col_dtype}): (Examples: {', '.join(example_strs)})")

        except Exception as e:
            prompt_parts.append(f"  Error getting schema/examples for loader.{func_name}(): {type(e).__name__}: {e}")
            print(f"Schema Gen Error for {func_name}: {e}") # Log error for debugging
            # traceback.print_exc() # Uncomment for full traceback if needed
        finally:
            prompt_parts.append("-" * (len(func_name) + 20)) # Separator line

    return ("\n".join(prompt_parts) 
            + "\nNote that in loader.get_transaction_data_df(), each order can includes several products, so the order_value is the sum price of all of the products in that order"
            + "\nNote that the currency is in USD")


# BARU
def get_available_tools_prompt():
    """
    Generates a description of the available tools for the AI agent.
    Ensures get_daily_report and check_for_anomalies are defined.
    """
    run_code_tool_definition = {
        "name": "run_code",
        "description": (
            "Executes Python code. Use for calculations, data analysis (`loader.get_X_df()`), "
            "complex logic. Has pandas (`pd`), `loader`, `numpy` (`np`), and `get_user_id()`."
            "Code MUST be valid Python. Returns stdout/stderr."
            "**Important `run_code` Environment Rules:**"
            "* You **cannot** use `import` statements (e.g., `import pandas as pd`) because the execution environment is restricted and does not allow importing external libraries directly."
            "* However, certain libraries and objects are **already available** for you to use directly without importing. Use these pre-loaded objects for data access and manipulation."
            "* Focus on using the methods and attributes of the available objects, especially the `loader` object for accessing data DataFrames and the built-in `pd` (pandas) and `np` (numpy) functionalities provided through those DataFrames."
            "**Important**: Use simple, single-step code. Break down tasks. Use provided schemas."
        ),
        "parameters": {
            "type": "object", "properties": {
                "code_string": {
                    "type": "string",
                    "description": (
                        "Valid Python code string. Example: "
                        "'merchant_id = get_user_id(); df = loader.get_products_df(); "
                        "print(df[df[\"merchant_id\"] == merchant_id].head())'"
                    )
                }
            }, "required": ["code_string"]
        }
    }

    get_daily_report_tool_definition = {
    "name": "get_daily_report",
    "description": (
    "Fetches the standard daily operational report (sales, orders, trends, stock) for a specific date. "
            "**IMPORTANT:** Use this tool ONLY when the user explicitly asks for their 'daily report' or 'daily summary'. "
            "Do NOT use this tool just to get data (like sales figures or stock levels) for answering other questions. "
            "When this tool is called, its raw data output will be returned directly as the final answer to the user, and no further thinking or processing steps will occur."
    ),
         "parameters": {
             "type": "object", "properties": {
                 "report_date": {
                     "type": "string",
                     "description": (
                         "The date for the report in YYYY-MM-DD format. "
                         "Defaults to 'yesterday' if not specified. Example: '2023-12-30'" 
                     )
                 }
             }, "required": [] 
         }
     }

    check_for_anomalies_tool_definition = {
        "name": "check_for_anomalies",
        "description": (
            "Checks for recent operational anomalies (yesterday vs day before) for the merchant. "
            "Looks for significant sales drops, low acceptance rates, low stock. "
            "Returns a list of detected anomalies."
        ),
        "parameters": { # Takes no explicit parameters from the LLM
            "type": "object", "properties": {}, "required": []
        }
    }

    available_tools = [
        run_code_tool_definition,
        get_daily_report_tool_definition, # Ensure it's here
        check_for_anomalies_tool_definition # Ensure it's here
    ]

    # --- Format for Prompt ---
    prompt_parts = ["You have access to the following tools:\n"]
    for tool in available_tools:
         prompt_parts.append(f"--- Tool: {tool['name']} ---")
         prompt_parts.append(f"Description: {tool['description']}")
         prompt_parts.append("Arguments:")
         props = tool['parameters']['properties']
         required = tool['parameters'].get('required', [])
         if not props:
              prompt_parts.append("  (No arguments required)")
         else:
              for param_name, param_details in props.items():
                  req_status = "(required)" if param_name in required else "(optional)"
                  prompt_parts.append(f"  - {param_name} ({param_details['type']}) {req_status}: {param_details['description']}")
         prompt_parts.append("-" * (len(tool['name']) + 10))
    return "\n".join(prompt_parts)

# --- Tool Execution Logic ---

def execute_tool_call(merchant_id, call_function_str):
    """
    Parses the function call string and executes the corresponding backend function/tool.
    Passes merchant_id for context where needed. Returns result or error as a string.
    """
    print(f"Attempting to parse and execute: {call_function_str}")
    match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)\s*$", call_function_str,re.DOTALL)

    if not match:
        error_msg = f"Invalid tool call format: '{call_function_str}'. Expected 'function_name(parameters)'."
        print(f"Error: {error_msg}")
        # Return error in the expected format (string, potentially JSON string if preferred downstream)
        # return json.dumps({"error": error_msg}) # If JSON is expected
        return f"--- Execution Failed ---\n--- Error Type ---\nFormatError\n--- Error Message ---\n{error_msg}" # Return plain string like run_code errors

    func_name = match.group(1)
    params_str = match.group(2).strip()

    print(f"Parsed Function Name: {func_name}")
    print(f"Parsed Parameters String: '{params_str}'")

    try:
        if func_name == "run_code":
            # Regex refined for robustness (handles potential internal quotes if LLM messes up)
            # Tries to find code_string='...' or code_string="..."
            code_match = re.search(r"""code_string\s*=\s*(?P<quote>['"])(.*?)(?P=quote)\s*$""", params_str, re.DOTALL)
            if not code_match:
                # Fallback: If quoting is weird, try to grab everything after '='
                code_match_fallback = re.search(r"code_string\s*=\s*(.*)", params_str, re.DOTALL)
                if code_match_fallback:
                     code_to_run_raw = code_match_fallback.group(1).strip()
                     # Attempt to remove leading/trailing quotes if they exist
                     if code_to_run_raw.startswith(('"', "'")) and code_to_run_raw.endswith(('"', "'")):
                          code_to_run_raw = code_to_run_raw[1:-1]
                else:
                    err_msg = f"Missing or malformed 'code_string' parameter. Could not extract from: '{params_str}'"
                    return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"
            else:
                code_to_run_raw = code_match.group(2) # Content between quotes

            # Process escape sequences and trim
            try:
                processed_code = codecs.decode(code_to_run_raw, 'unicode_escape')
            except Exception as decode_err:
                 print(f"Warning: Failed to decode unicode escapes: {decode_err}. Using raw string.")
                 processed_code = code_to_run_raw
            code_to_run = processed_code.strip()

            print(f"Code string processed, trimmed:\n-------\n{code_to_run}\n-------")
            if not code_to_run:
                err_msg = "Extracted code_string is empty after processing."
                return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"

            get_user_id_func = _create_get_user_id_func(merchant_id)
            print(f"Executing run_code for merchant_id {merchant_id}")
            result = run_code(code_string=code_to_run, user_context_globals={'get_user_id': get_user_id_func})
            return result # run_code returns formatted string

        elif func_name == "get_daily_report":
            print(f"Executing get_daily_report for merchant {merchant_id}")
            # Parse optional report_date parameter
            report_date_str = None
            date_match = re.search(r"""report_date\s*=\s*(['"])(.*?)\1""", params_str)
            if date_match:
                report_date_str = date_match.group(2)

            # Default to yesterday if not provided or invalid
            report_dt = date.today() - timedelta(days=1)
            if report_date_str:
                try:
                    parsed_dt = pd.to_datetime(report_date_str).date()
                    # Basic sanity check: don't allow future dates for standard report?
                    if parsed_dt <= date.today():
                         report_dt = parsed_dt
                    else:
                         print(f"Warning: Report date '{report_date_str}' is in the future. Defaulting to yesterday.")
                except ValueError:
                     print(f"Warning: Invalid date format '{report_date_str}' for report_date. Using yesterday.")

            print(f"Using report date: {report_dt.strftime('%Y-%m-%d')}")
            # Call the actual report generation function
            report_data = generate_daily_report(merchant_id, report_dt)
            # Return result as JSON string
            return json.dumps(report_data, indent=2, default=str) # Use default=str for potential non-serializable types like Timestamps

        elif func_name == "check_for_anomalies":
            print(f"Executing check_for_anomalies for merchant {merchant_id}")
            # Call the actual anomaly detection function
            detected_anomalies_list = detect_anomalies(merchant_id)
            print(f"Detected anomalies: {detected_anomalies_list}")
            # Return the list as a JSON string
            return json.dumps(detected_anomalies_list, indent=2, default=str) # Use default=str

        else:
            err_msg = f"Unknown function tool called: '{func_name}'"
            return f"--- Execution Failed ---\n--- Error Type ---\nToolNotFound\n--- Error Message ---\n{err_msg}"

    except Exception as e:
        # Catch errors during tool execution or parameter parsing
        error_msg = f"Error executing tool '{func_name}': {type(e).__name__}: {e}"
        print(f"Error: {error_msg}\n{traceback.format_exc()}") # Log full traceback
        return f"--- Execution Failed ---\n--- Error Type ---\n{type(e).__name__}\n--- Error Message ---\n{error_msg}"

def run_code(code_string: str, user_context_globals: dict = None) -> str:
    """
    Executes a string of Python code in a restricted environment and captures output.
    (Implementation remains the same as provided before)
    """
    output_capture = io.StringIO()
    error_capture = io.StringIO()
    result_parts = []

    # Base restricted global environment
    execution_globals = {
        'pd': pd,
        'loader': loader, # Make sure loader is accessible
        'np': np,
        'datetime': datetime, # Allow datetime usage within run_code
        'timedelta': timedelta,
        'date': date,
        '__builtins__': { # Limit builtins for security
            'print': print, 'len': len, 'round': round, 'range': range,
            'int': int, 'float': float, 'str': str, 'list': list, 'dict': dict,
            'set': set, 'tuple': tuple, 'bool': bool, 'max': max, 'min': min,
            'sum': sum, 'abs': abs, 'any': any, 'all': all, 'sorted': sorted,
            'isinstance': isinstance, 'getattr': getattr, 'hasattr': hasattr,
            'Exception': Exception, # Allow raising/catching generic exceptions
        },
        # Explicitly exclude dangerous builtins like open, eval, exec, input
        # Explicitly exclude modules like os, sys, requests, subprocess etc.
    }

    # Inject user-specific context (like get_user_id) safely
    if user_context_globals:
        for key, value in user_context_globals.items():
            if key not in execution_globals and key not in ['__builtins__']: # Protect core globals
                execution_globals[key] = value
            else:
                 print(f"Warning: Skipped overwriting global '{key}' in run_code environment.")

    execution_locals = {} # Keep locals separate

    try:
        # Redirect stdout and stderr
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(error_capture):
            # Execute the code with the restricted environment
            exec(code_string, execution_globals, execution_locals)

        stdout = output_capture.getvalue()
        stderr = error_capture.getvalue()

        result_parts.append("--- Execution Result ---")
        result_parts.append(f"--- stdout ---\n{stdout.strip() if stdout.strip() else '[No stdout]'}")
        result_parts.append(f"--- stderr ---\n{stderr.strip() if stderr.strip() else '[No stderr]'}")

    except Exception as e:
        # Capture output/error even if exception occurs
        stdout = output_capture.getvalue()
        stderr = error_capture.getvalue()
        tb_string = traceback.format_exc() # Get traceback

        result_parts.append("--- Execution Failed ---")
        if stdout.strip():
            result_parts.append(f"--- stdout (before error) ---\n{stdout.strip()}")
        if stderr.strip():
             result_parts.append(f"--- stderr (before error) ---\n{stderr.strip()}")
        result_parts.append(f"--- Error Type ---\n{type(e).__name__}")
        result_parts.append(f"--- Error Message ---\n{e}")
        # Log the traceback for backend debugging, don't return it to LLM unless necessary
        print(f"run_code execution error. Code:\n{code_string}\nTraceback:\n{tb_string}")

    # Return combined output/error string
    return "\n".join(result_parts).strip()


# --- Example Usage (if run directly) ---
if __name__ == '__main__':
    print("Testing Query Processor Setup...")

    # Mock necessary components if they aren't globally available/importable standalone
    # This requires your actual loader, gemini_service etc. to be set up
    # or replaced with mocks for standalone testing.

    # Example Mock Gemini Service:
    class MockGemini:
         def generate_text(self, prompt):
              print("--- MOCK LLM RECEIVED PROMPT ---")
              print(prompt[:200] + "..." + prompt[-200:])
              print("--- MOCK LLM SENDING RESPONSE ---")
              # Simulate LLM response based on prompt content
              if "how were my sales yesterday" in prompt.lower():
                   return """Thinking:
1. The merchant wants sales data for yesterday.
2. I need to get the total sales amount and order count.
3. The `run_code` tool seems appropriate for this calculation using the loader.
4. I need to load transaction data, filter by merchant ID and yesterday's date, then calculate sum of 'total_amount' and count transactions.
CALL_FUNCTION: run_code(code_string='import pandas as pd\nfrom datetime import date, timedelta\nmerchant_id = get_user_id()\nyesterday = date.today() - timedelta(days=1)\nstart_dt = pd.Timestamp(yesterday)\nend_dt = start_dt + timedelta(days=1)\norders_df = loader.get_transaction_data_df() # Assuming this function exists\nmerchant_orders = orders_df[(orders_df["merchant_id"] == merchant_id) & (orders_df["order_time"] >= start_dt) & (orders_df["order_time"] < end_dt)]\ntotal_sales = merchant_orders["total_amount"].sum()\norder_count = len(merchant_orders)\nprint(f"Date: {yesterday.strftime(\'%Y-%m-%d\')}\\nTotal Sales: {total_sales}\\nOrder Count: {order_count}")')"""
              elif "print(f" in prompt: # Simulate response after code execution
                   return """Thinking:
1. The system executed the code I requested.
2. The code calculated yesterday's sales and order count.
3. The output contains the required information.
4. I can now format this into a clear answer for the merchant.
ANSWER: Yesterday ({provided_data_date}), you had {provided_data_count} orders totaling ${provided_data_sales:.2f}. Keep up the good work! Maybe consider promoting a popular item today?
""" # Note: The ANSWER would ideally use placeholders replaced by data from provided_data
              else:
                   return """Thinking:
1. I need to understand the user's request: 'Hello there'
2. This is a simple greeting and requires no data.
ANSWER: Hello! How can I help you with your GrabFood business today?
"""

    gemini_service = MockGemini() # Use the mock

    # Mock Loader (replace with your actual loader)
    class MockLoader:
        def get_merchants_df(self):
             return pd.DataFrame({
                 'merchant_id': ['MOCK-123', 'MOCK-456'],
                 'city_id': [1, 3],
                 'name': ['Mock Cafe', 'Mock Bistro']
             })
        def get_products_df(self):
             return pd.DataFrame({
                 'item_id': ['P1', 'P2', 'P3'],
                 'merchant_id': ['MOCK-123', 'MOCK-123', 'MOCK-456'],
                 'item_name': ['Mock Coffee', 'Mock Pastry', 'Mock Burger'],
                 'price': [3.50, 2.80, 8.99]
             })
        def get_inventory_df(self): # Need this schema
             return pd.DataFrame({'product_id': ['P1', 'P2', 'P3'], 'current_stock': [50, 25, 100]})
        def get_transaction_data_df(self): # Need this schema for the example flow
             today = pd.Timestamp.now().normalize()
             yesterday = today - timedelta(days=1)
             return pd.DataFrame({
                'transaction_id': ['T1', 'T2', 'T3', 'T4'],
                'merchant_id': ['MOCK-123', 'MOCK-123', 'MOCK-456', 'MOCK-123'],
                'order_time': [yesterday + timedelta(hours=h) for h in [9, 12, 10, 18]],
                'total_amount': [6.30, 3.50, 8.99, 2.80],
                'prep_time_minutes': [5, 4, 10, 6]
            })
    loader = MockLoader() # Use the mock

    # --- Run Test ---
    test_merchant_id = "MOCK-123"
    test_question = "How were my sales yesterday?"
    # test_question = "Hello there"

    final_response = process_merchant_question(test_merchant_id, test_question)
    print("\n====== FINAL RESPONSE ======")
    print(final_response)
    print("==========================")