# backend/insight_engine/query_processor.py
import io
import re
import json
import pandas as pd
import numpy as np
import contextlib
import traceback
from datetime import date, timedelta, datetime, timezone # Keep these
import os
import sys
# REMOVE codecs import - we won't use it
from backend.reporting.daily_report_generator import generate_daily_report
from backend.core.anomaly_detector import detect_anomalies
from . import gemini_service
from backend.data_access import loader
from backend.core import metrics_calculator

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

    # --- Tool Bypass Instruction (for prompts) --
    report_exception_instruction = (
        "**Special Case:** If you call `get_daily_report`, the system will "
        "return its raw output directly. Do *not* try to summarize or analyze "
        "the report data yourself in a subsequent 'ANSWER:' step; the raw data "
        "is the final output for that specific tool call."
    )
    
    chart_instruction = (
        "**Generating Charts:** To show a chart: 1. Use `run_code` to calculate data & print JSON. 2. Wait for result. "
        "3. In the *final* step, provide *both* your textual `ANSWER:` explaining the chart, *and* then immediately follow with `CALL_FUNCTION: display_chart(...)` using the JSON data from step 1."
        " **Rule:** Keep charts simple. For bar charts, limit x-axis ticks (max ~20)."
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
                report_exception_instruction= report_exception_instruction,
                chart_instruction = chart_instruction
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
                chart_instruction = chart_instruction
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
             return json.dumps({"answer": f"Sorry, error reaching AI service: {e}"}) # Return JSON error


        # --- Parse LLM Response ---
        call_function_match = re.search(r"CALL_FUNCTION:(.*?)(?:ANSWER:|$)", raw_response, re.DOTALL | re.IGNORECASE)
        
        # --- **REVISED Parsing Logic** ---
        answer_match = re.search(r"ANSWER:(.*?)($|CALL_FUNCTION:|Thinking:)", raw_response, re.DOTALL | re.IGNORECASE)
        call_function_match = re.search(r"CALL_FUNCTION:(.*?)(?:ANSWER:|$|Thinking:)", raw_response, re.DOTALL | re.IGNORECASE)

        # Extract thinking part (before ANSWER or CALL_FUNCTION)
        thinking_end_pos = len(raw_response)
        if answer_match: thinking_end_pos = min(thinking_end_pos, answer_match.start())
        if call_function_match: thinking_end_pos = min(thinking_end_pos, call_function_match.start())
        thinking_part = raw_response[:thinking_end_pos].strip()
        current_thinking = thinking_part[len("thinking:"):].strip() if thinking_part.lower().startswith("thinking:") else thinking_part
        if not current_thinking: current_thinking = "(No thinking provided)"
        conversation_history.append({"role": "assistant", "thinking": current_thinking})
        print(f"Parsed Thinking: {current_thinking}")

        final_answer_text = answer_match.group(1).strip() if answer_match else None
        call_function_str = call_function_match.group(1).strip() if call_function_match else None
        # --- End Revised Parsing Logic ---


        # --- **REVISED Processing Logic** ---
        if final_answer_text is not None and call_function_str is not None:
            # Case: Both ANSWER and CALL_FUNCTION provided (Expected for final chart step)
            print(f"--> Found ANSWER and CALL_FUNCTION.")
            conversation_history.append({"role": "assistant", "answer_text": final_answer_text})
            # Parse function name
            func_match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", call_function_str)
            func_name = func_match.group(1) if func_match else None
            print(f"Function Name in combined response: {func_name}")

            if func_name == "display_chart":
                 print(f"--> Executing display_chart alongside ANSWER.")
                 chart_command_str = execute_tool_call(merchant_id, call_function_str)
                 print(f"<-- display_chart result: {chart_command_str[:200]}...")
                 # Try to parse the command string into an object
                 try:
                     chart_command_obj = json.loads(chart_command_str)
                     # Check if it's the expected chart command structure
                     if isinstance(chart_command_obj, dict) and chart_command_obj.get("type") == "chart":
                          # Return structured response for frontend
                          response_payload = {
                              "answer": final_answer_text,
                              "chart_command": chart_command_obj # Embed the parsed command object
                          }
                          conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": chart_command_obj})
                          return json.dumps(response_payload) # Return the combined structure
                     else:
                          print("Warning: display_chart did not return expected structure.")
                          # Fallback: Return only the text answer
                          return json.dumps({"answer": final_answer_text + "\n\n[Chart display failed: Invalid command format]"})

                 except json.JSONDecodeError:
                      print("Error: Failed to parse display_chart command string.")
                      # Fallback: Return only the text answer
                      return json.dumps({"answer": final_answer_text + "\n\n[Chart display failed: Command parse error]"})
            else:
                 # Unexpected: ANSWER and a *different* CALL_FUNCTION together. Prioritize ANSWER.
                 print(f"Warning: Received ANSWER and unexpected CALL_FUNCTION ({func_name}) together. Returning only ANSWER.")
                 return json.dumps({"answer": final_answer_text})

        elif final_answer_text is not None:
            # Case: Only ANSWER provided (Standard end)
            print(f"--> Final Answer Found: {final_answer_text}")
            conversation_history.append({"role": "assistant", "final_answer": final_answer_text})
            return json.dumps({"answer": final_answer_text}) # Return JSON

        elif call_function_str is not None:
            # Case: Only CALL_FUNCTION provided (Intermediate step)
            print(f"--> Function Call Requested: {call_function_str}")
            func_match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", call_function_str)
            func_name = func_match.group(1) if func_match else None
            print(f"Function Name: {func_name}")

            tool_result_string = execute_tool_call(merchant_id, call_function_str)
            print(f"<-- Tool Execution Result (String): {tool_result_string[:500]}...")

            # if func_name == "get_daily_report": # Handle daily report bypass
            #    print(f"--> Special Handling: '{func_name}'. Returning result directly.")
            #     conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": tool_result_string})
            #     return json.dumps({"answer": tool_result_string}) # Return raw report string as answer
            
            if "Execution Failed" in tool_result_string:
                 # If tool failed, pass the error back to the AI to potentially fix
                 print("--> Tool execution failed. Passing error back to AI.")
                 provided_data = tool_result_string
                 conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": provided_data})
                 # Continue loop for AI error handling
            else:
                 # Tool succeeded, pass result back for next turn
                 print(f"--> Continuing loop for AI to reason on '{func_name}' result.")
                 provided_data = tool_result_string
                 conversation_history.append({"role": "system", "tool_call": call_function_str, "tool_response": provided_data})
                 # Continue loop

        else:
            # Case: Neither ANSWER nor CALL_FUNCTION found
            print("Warning: LLM did not provide ANSWER or CALL_FUNCTION.")
            conversation_history.append({"role": "system", "status": "Ambiguous response"})
            # Return the thinking or a generic message as JSON
            return json.dumps({"answer": f"Thinking: {current_thinking}\n(Couldn't determine next step...)"})
        # --- END REVISED Processing Logic ---

    # Max turns reached
    print("Maximum turns reached.")
    conversation_history.append({"role": "system", "status": "Max turns reached"})
    return json.dumps({"answer": f"Sorry, I got stuck processing that. Last thought: {current_thinking}"})

# --- Prompt Building Helpers ---

# Updated to accept pre-fetched components and use f-strings correctly
def build_initial_prompt(briefing, core_principles, merchant_context, current_date, data_schemas, tool_descriptions, user_question, report_exception_instruction,chart_instruction):
    # Added a dedicated section for run_code rules
    return f"""
{briefing}
**Core Principles:**
{core_principles}
**Merchant Context:**
{merchant_context}
**Current Date:** {current_date}
**Data Schemas:**
{data_schemas}
**Available Tools:**
{tool_descriptions}

**Instructions:**
1. Analyze question: "{user_question}".
2. Think step-by-step under `Thinking:`.
3. Determine the **first** tool call needed (e.g., `run_code`, `get_daily_report`). Output `CALL_FUNCTION: ...`.
4. Follow **`run_code` Rules:** NO IMPORTS, NO PLOTTING, calculate data, print result (use JSON for chart data).
5. **{chart_instruction}** # Add chart instruction
6. **Handling `get_daily_report` Results:** If you call `get_daily_report` and receive JSON data back in the next turn, your **only** task in that *subsequent* turn is to format the received JSON data into a user-friendly summary using **Markdown** in the `ANSWER:` section.
    *   **IMPORTANT:** When formatting, act ONLY as a data presenter. **DO NOT** add any analysis, interpretation, or reasoning beyond what is explicitly stated in the JSON data provided by the tool. Stick strictly to the facts from the report.
    *   Use Markdown (headings, bold, lists) for clarity. Do NOT output the raw JSON.
7. Format: `Thinking: ...` then `CALL_FUNCTION: ...` (or `ANSWER:` if no tool needed, or for formatting the report as per instruction #6).

**Merchant's Question:**
{user_question}

**Your Response:**
Thinking:
"""

# Updated to accept the report_exception_instruction
def build_intermediate_prompt(briefing, core_principles, merchant_context, current_date, data_schemas, tool_descriptions, original_question, previous_thinking, provided_data,chart_instruction):
    # Added stricter rules for run_code and error handling
    return f"""
{briefing}

Continue answering: "{original_question}"
**Core Principles:** {core_principles}
**Merchant Context:** {merchant_context}
**Current Date:** {current_date}
**Data Schemas:** {data_schemas}
**Available Tools:** {tool_descriptions}

**Conversation History:**
*   **Previous Thinking:** {previous_thinking}
*   **Data/Result Provided:** {provided_data[:1000]}...

**Instructions:**
1. Review `Provided Data`.
2. Reason under `Thinking:`. What is the next logical step based *only* on the `Provided Data` and the `Original Question`?
3. Determine **next** step:
    *   **Is `Provided Data` the JSON from `get_daily_report`?** -> Your *only* action is to format this JSON data using **Markdown** in the `ANSWER:` section. **Strictly present the data; DO NOT analyze or interpret it** in this step. Stick to the facts from the JSON. Use Markdown (headings, bold, lists).
    *   Need more data/calculation? -> `CALL_FUNCTION: run_code(...)`. Follow `run_code` rules (NO IMPORTS/PLOTTING, print JSON for charts).
    *   Ready to display chart? -> Provide textual `ANSWER: ...` AND THEN `CALL_FUNCTION: display_chart(...)` using JSON data from previous `run_code`.
    *   Ready for final text answer (not related to report formatting)? -> `ANSWER: ...`.
    *   Handle errors from `Provided Data`: Explain correction in `Thinking:`, call corrected `run_code`. Give up after 1-2 tries.
4. **{chart_instruction}** # Add chart instruction
5. Format: `Thinking: ...` then *either* `CALL_FUNCTION: ...` *or* `ANSWER: ...` *or* (`ANSWER: ...` followed by `CALL_FUNCTION: display_chart(...)`).

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
            + "\nNote that the currency is in USD"
            + "\nNote that in loader.get_inventory_df(), this data indicate the change log of the stock. So the current stock quantity is the one that has the latest date updated")
    


# BARU
def get_available_tools_prompt():
    """
    Generates descriptions of tools, including the new display_chart.
    Informs LLM that pd, np, json, loader are pre-available in run_code.
    """
    run_code_tool_definition = {
        "name": "run_code",
        "description": (
            "Executes Python code ONLY to perform data calculations or retrieve specific data points. "
            "**IMPORTANT:** The following are PRE-LOADED and available for direct use: "
            "`pd` (pandas), `np` (numpy), `json`, `loader` (for data access like `loader.get_transaction_data_df()`), "
            "and the `get_user_id()` function. "
            "**DO NOT explicitly import `pandas`, `numpy`, or `json`.** You *can* import other standard libraries like `datetime` if necessary. "
            "**DO NOT attempt to use plotting libraries (matplotlib, seaborn, plotly).** "
            "Your code MUST output the calculated data using `print()`. "
            "**For chart data:** `print()` a VALID JSON string. Ensure complex objects like dates/timestamps are converted to strings (e.g., using `.astype(str)` or `.strftime('%Y-%m-%d')` on the index/column) BEFORE creating the JSON."
        ),
         "parameters": {
             "type": "object", "properties": {
                 "code_string": {
                     "type": "string",
                     "description": (
                         "Valid Python code string. Example for chart data: "
                         "'merchant_id = get_user_id(); df = loader.get_transaction_data_df(merchant_id=merchant_id); "
                         "# Convert date object index to string for JSON\n"
                         "df[\"order_time\"] = pd.to_datetime(df[\"order_time\"]); " # Ensure datetime
                         "sales_by_date = df.groupby(df[\"order_time\"].dt.date)[\"order_value\"].sum(); "
                         "labels = sales_by_date.index.strftime(\"%Y-%m-%d\").tolist(); " # Convert index to string list
                         "data = sales_by_date.values.tolist(); "
                         "print(json.dumps({\"labels\": labels, \"data\": data}))'"
                     )
                 }
             }, "required": ["code_string"]
         }
    }
    # --- Keep other tool definitions the same ---
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
                 "report_date": { "type": "string", "description": "The date for the report in YYYY-MM-DD format. Defaults to 'yesterday'." }
             }, "required": []
         }
     }
    check_for_anomalies_tool_definition = {
        "name": "check_for_anomalies",
        "description": "Checks for recent operational anomalies (yesterday vs day before). Returns a list.",
        "parameters": { "type": "object", "properties": {}, "required": [] }
    }
    display_chart_tool_definition = {
        "name": "display_chart",
        "description": (
            "Use this tool ONLY to display a visual chart in the chat interface, **AFTER providing a textual explanation in the `ANSWER:` section.** "
             "**Process:** 1. Use `run_code` to calculate data & print JSON. 2. Get the JSON result. 3. In your FINAL response, provide `ANSWER: [Your text explanation]` THEN immediately follow with `CALL_FUNCTION: display_chart(chart_data='[JSON string from run_code]', chart_type='bar', ...)`."
            " **Plotting Rule of Thumb:** Maintain simplicity. For bar charts, avoid too many x-axis ticks (e.g., keep it below 20)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": { "type": "string", "description": "Currently supported: 'bar', 'line'.", "enum": ["bar", "line"] },
                "chart_data": { "type": "string", "description": "A JSON string containing the Chart.js data structure (e.g., '{\"labels\": [...], \"data\": [...]}'). This MUST be the exact output from a previous `run_code` call."},
                "title": { "type": "string", "description": "Optional title." },
                "x_label": { "type": "string", "description": "Optional X-axis label." },
                "y_label": { "type": "string", "description": "Optional Y-axis label." }
            },
            "required": ["chart_type", "chart_data"]
        }
    }
    # --- End other tool definitions ---

    available_tools = [
        run_code_tool_definition,
        get_daily_report_tool_definition,
        check_for_anomalies_tool_definition,
        display_chart_tool_definition
    ]

    # --- Format for Prompt (remains the same structure) ---
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
                  # Use .get with defaults for safety
                  p_type = param_details.get('type', 'any')
                  p_desc = param_details.get('description', 'No description')
                  prompt_parts.append(f"  - {param_name} ({p_type}) {req_status}: {p_desc}")
         prompt_parts.append("-" * (len(tool['name']) + 10))
    return "\n".join(prompt_parts)

# --- Tool Execution Logic ---

# --- *** REVISED execute_tool_call *** ---
def execute_tool_call(merchant_id, call_function_str):
    call_function_str = call_function_str.strip()
    print(f"Attempting to parse and execute (full string start/end): {call_function_str[:100]}...{call_function_str[-100:]}")

    # 1. Extract Function Name (same as before)
    name_match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)", call_function_str)
    if not name_match:
        error_msg = f"Could not extract function name from: '{call_function_str[:100]}...'"
        print(f"Error: {error_msg}")
        return f"--- Execution Failed ---\n--- Error Type ---\nFormatError\n--- Error Message ---\n{error_msg}"
    func_name = name_match.group(1)
    print(f"Parsed Function Name: {func_name}")

    # 2. Find Parameter Block (same as before)
    open_paren_index = call_function_str.find('(', len(func_name))
    close_paren_index = call_function_str.rfind(')')
    if open_paren_index == -1 or close_paren_index == -1 or close_paren_index < open_paren_index:
        error_msg = f"Mismatched or missing parentheses in tool call: '{call_function_str[:100]}...{call_function_str[-100:]}'"
        print(f"Error: {error_msg}")
        return f"--- Execution Failed ---\n--- Error Type ---\nFormatError\n--- Error Message ---\n{error_msg}"
    params_str = call_function_str[open_paren_index + 1 : close_paren_index].strip()
    print(f"Parsed Parameters String (raw start/end): '{params_str[:100]}...{params_str[-100:]}'")

    # 3. Execute based on function name
    try:
        if func_name == "run_code":
            # --- *** Robust code_string Extraction *** ---
            # This regex handles single, double, or triple quotes and captures the content using DOTALL
            code_match = re.search(
                r"""code_string\s*=\s*(?P<quote>['"]|"{3}|'{3})(.*?)(?P=quote)\s*$""",
                params_str,
                re.DOTALL | re.IGNORECASE
            )
            if not code_match:
                err_msg = f"run_code: Missing or malformed 'code_string'. Could not find quoted string in params: '{params_str[:200]}...'"
                print(f"Error: {err_msg}")
                return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"

            code_to_run_raw = code_match.group(2)

            # **Crucial:** Decode common string escapes that exec expects
            # This step converts literal "\\n" etc. within the extracted string
            # into actual newline characters etc. for Python execution.
            try:
                 # Use the 'unicode_escape' codec carefully now that we have the *correct* string content
                 code_to_run = code_to_run_raw.encode('latin-1', 'backslashreplace').decode('unicode_escape')
            except Exception as decode_err:
                 print(f"Warning: Failed during unicode_escape decoding: {decode_err}. Using raw string with basic replacements.")
                 # Fallback: basic replacements if full decoding fails (less robust)
                 code_to_run = code_to_run_raw.replace('\\n', '\n').replace('\\t', '\t').replace("\\'", "'").replace('\\"', '"')

            code_to_run = code_to_run.strip() # Strip leading/trailing whitespace AFTER decoding

            print(f"Code string processed (decoded):\n-------\n{code_to_run}\n-------")

            if not code_to_run:
                err_msg = "run_code: Extracted code_string is empty after processing."
                print(f"Error: {err_msg}")
                return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"

            # Execute (call revised run_code)
            get_user_id_func = _create_get_user_id_func(merchant_id)
            print(f"Executing run_code for merchant_id {merchant_id}")
            result = run_code(code_string=code_to_run, user_context_globals={'get_user_id': get_user_id_func})
            return result
        # --- End run_code ---

        elif func_name == "get_daily_report":
             # --- Logic remains the same ---
            print(f"Executing get_daily_report for merchant {merchant_id}")
            report_date_str = None
            date_match = re.search(r"""report_date\s*=\s*(['"])(.*?)\1""", params_str, re.IGNORECASE)
            if date_match: report_date_str = date_match.group(2)
            report_dt = date.today() - timedelta(days=1)
            if report_date_str:
                try:
                    parsed_dt = pd.to_datetime(report_date_str).date()
                    if parsed_dt <= date.today(): report_dt = parsed_dt
                    else: print(f"Warning: Report date '{report_date_str}' is in the future. Defaulting to yesterday.")
                except ValueError: print(f"Warning: Invalid date format '{report_date_str}'. Using yesterday.")
            print(f"Using report date: {report_dt.strftime('%Y-%m-%d')}")

            report_data = generate_daily_report(merchant_id, report_dt)
            return json.dumps(report_data, indent=2, default=str)

        elif func_name == "check_for_anomalies":
             # --- Logic remains the same ---
             print(f"Executing check_for_anomalies for merchant {merchant_id}")
             detected_anomalies_list = detect_anomalies(merchant_id)
             print(f"Detected anomalies: {detected_anomalies_list}")
             return json.dumps(detected_anomalies_list, indent=2, default=str)

        elif func_name == "display_chart":
             # --- Logic remains the same (uses re.search on params_str) ---
            print(f"Executing display_chart command for merchant {merchant_id}")
            chart_type = None
            chart_data_str = None
            title = None
            x_label = None
            y_label = None

            # Extract individual args using re.search (more robust than parsing the whole string)
            chart_type_match = re.search(r"chart_type\s*=\s*['\"]([^'\"]*)['\"]", params_str, re.IGNORECASE)
            title_match = re.search(r"title\s*=\s*['\"]([^'\"]*)['\"]", params_str, re.IGNORECASE)
            x_label_match = re.search(r"x_label\s*=\s*['\"]([^'\"]*)['\"]", params_str, re.IGNORECASE)
            y_label_match = re.search(r"y_label\s*=\s*['\"]([^'\"]*)['\"]", params_str, re.IGNORECASE)
            if chart_type_match: chart_type = chart_type_match.group(1)
            if title_match: title = title_match.group(1)
            if x_label_match: x_label = x_label_match.group(1)
            if y_label_match: y_label = y_label_match.group(1)

            # Extract chart_data carefully (same careful logic as before)
            start_pattern = r"chart_data\s*=\s*(['\"])"
            start_match = re.search(start_pattern, params_str, re.IGNORECASE)
            if start_match:
                quote_char = start_match.group(1)
                start_index = start_match.end()
                # Find the *corresponding* closing quote carefully
                end_index = -1
                current_pos = start_index
                while current_pos < len(params_str):
                    find_quote = params_str.find(quote_char, current_pos)
                    if find_quote == -1: # Not found
                        break
                    if params_str[find_quote - 1] == '\\': # Escaped quote, skip
                        current_pos = find_quote + 1
                    else: # Found the non-escaped closing quote
                        end_index = find_quote
                        break
                # If still not found, maybe it's the end of the params string
                if end_index == -1:
                     if params_str.endswith(quote_char):
                         end_index = len(params_str) - 1
                     else: # Fallback if parsing is tricky
                          end_pattern = re.compile(f"{re.escape(quote_char)}(?:\\s*,|\\s*$)")
                          end_match = end_pattern.search(params_str, start_index)
                          if end_match: end_index = end_match.start()

                if end_index != -1 and end_index > start_index:
                    chart_data_str_raw = params_str[start_index:end_index]
                    # Decode escapes *within* the JSON string itself
                    chart_data_str = chart_data_str_raw.replace(f"\\{quote_char}", quote_char).replace('\\\\', '\\')
                else:
                     print("Warning: Could not reliably find closing quote for chart_data.")
                     chart_data_str = None
            else:
                 print("Warning: Could not find 'chart_data=' pattern.")
                 chart_data_str = None


            supported_chart = ["line", "bar"]

            # Validation (same as before)
            if not chart_type or chart_data_str is None:
                err_msg = f"display_chart: Missing required 'chart_type' or could not extract 'chart_data'. Params: '{params_str[:100]}...{params_str[-100:]}'"
                return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"
            if chart_type not in supported_chart:
                 err_msg = f"display_chart: Unsupported chart_type '{chart_type}'. Only 'bar' is supported."
                 return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"

            # JSON Parsing and Payload creation (same as before)
            try:
                print(f"[DEBUG display_chart] Attempting to parse chart_data_str: {chart_data_str[:100]}...{chart_data_str[-100:]}")
                chart_data_obj = json.loads(chart_data_str) # Parse the unescaped JSON string
                if not isinstance(chart_data_obj, dict) or not (('labels' in chart_data_obj and ('data' in chart_data_obj or 'datasets' in chart_data_obj))):
                     raise ValueError("chart_data JSON structure invalid (missing labels/data or labels/datasets)")
            except (json.JSONDecodeError, ValueError) as json_err:
                err_msg = f"display_chart: Invalid JSON in 'chart_data': {json_err}. Received: '{chart_data_str[:100]}...{chart_data_str[-100:]}'"
                return f"--- Execution Failed ---\n--- Error Type ---\nParameterError\n--- Error Message ---\n{err_msg}"

            command_payload = {
                "type": "chart",
                "payload": {
                    "chart_type": chart_type, "chart_data": chart_data_obj,
                    "options": {"title": title or f"Sales Data", "x_label": x_label, "y_label": y_label}
                }
            }
            print(f"Returning chart command to frontend: {json.dumps(command_payload)[:200]}...")
            return json.dumps(command_payload)
        # --- End display_chart ---

        else:
            err_msg = f"Unknown function tool called: '{func_name}'"
            return f"--- Execution Failed ---\n--- Error Type ---\nToolNotFound\n--- Error Message ---\n{err_msg}"

    except Exception as e:
        # --- General Tool Execution Error ---
        error_msg = f"Error executing tool '{func_name}': {type(e).__name__}: {e}"
        print(f"Error: {error_msg}\n{traceback.format_exc()}")
        return f"--- Execution Failed ---\n--- Error Type ---\n{type(e).__name__}\n--- Error Message ---\n{error_msg}"

# --- *** REVISED run_code *** ---
def run_code(code_string: str, user_context_globals: dict = None) -> str:
    """
    Executes a string of Python code in a restricted environment and captures output.
    Allows safe builtins (including __import__) and pre-injects pd, np, json, loader.
    """
    output_capture = io.StringIO()
    error_capture = io.StringIO()
    result_parts = []

    # Base restricted global environment
    execution_globals = {
        'pd': pd,           # Inject pandas
        'np': np,           # Inject numpy
        'json': json,       # Inject json
        'loader': loader,   # Inject loader
        'datetime': datetime, # Inject datetime module directly
        'timedelta': timedelta,
        'date': date,
        # --- Adjusted Builtins ---
        '__builtins__': {
            'print': print, 'len': len, 'round': round, 'range': range,
            'int': int, 'float': float, 'str': str, 'list': list, 'dict': dict,
            'set': set, 'tuple': tuple, 'bool': bool, 'max': max, 'min': min,
            'sum': sum, 'abs': abs, 'any': any, 'all': all, 'sorted': sorted,
            'isinstance': isinstance, 'getattr': getattr, 'hasattr': hasattr,
            'Exception': Exception,
            '__import__': __import__, # ALLOW standard imports
            'ValueError': ValueError, 'TypeError': TypeError, 'KeyError': KeyError,
            'IndexError': IndexError, 'AttributeError': AttributeError,
            'True': True, 'False': False, 'None': None,
            'zip': zip, 'map': map, 'filter': filter, 'enumerate': enumerate,
            'repr': repr, 'dir': dir, 'id': id, 'type': type,
             # Add common math functions if needed, avoid importing 'math' itself if possible
            # 'pow': pow,
            # Add other safe functions...
        },
    }

    # Inject user-specific context (like get_user_id)
    if user_context_globals:
        for key, value in user_context_globals.items():
            if key not in execution_globals and key != '__builtins__':
                execution_globals[key] = value
            else:
                 print(f"Warning: Skipped overwriting global '{key}' in run_code environment.")

    execution_locals = {}

    try:
        # Redirect stdout and stderr
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(error_capture):
            # Execute the DECODED code string
            exec(code_string, execution_globals, execution_locals)

        stdout = output_capture.getvalue()
        stderr = error_capture.getvalue()

        result_parts.append("--- Execution Result ---")
        result_parts.append(f"--- stdout ---\n{stdout.strip() if stdout.strip() else '[No stdout]'}")
        result_parts.append(f"--- stderr ---\n{stderr.strip() if stderr.strip() else '[No stderr]'}")

    except Exception as e:
        # --- Error Capturing (same as before) ---
        stdout = output_capture.getvalue()
        stderr = error_capture.getvalue()
        tb_string = traceback.format_exc()

        result_parts.append("--- Execution Failed ---")
        if stdout.strip(): result_parts.append(f"--- stdout (before error) ---\n{stdout.strip()}")
        if stderr.strip(): result_parts.append(f"--- stderr (before error) ---\n{stderr.strip()}")
        result_parts.append(f"--- Error Type ---\n{type(e).__name__}")
        result_parts.append(f"--- Error Message ---\n{e}")
        print(f"run_code execution error. Code:\n-------\n{code_string}\n-------\nTraceback:\n{tb_string}") # Log code and traceback

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