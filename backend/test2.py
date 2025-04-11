# backend/test_gemini.py
import os
import sys
import re

# Add the project root to the Python path to allow finding modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
     sys.path.insert(0, project_root)

from insight_engine.query_processor import get_available_data_schemas_prompt

question = "how is my sales performance in the last 3 days"

print(get_available_data_schemas_prompt())


# # from insight_engine.query_processor import get_merchant_context_prompt
# from data_access import loader
# from insight_engine.query_processor import get_available_data_schemas_prompt


# print(get_available_data_schemas_prompt())

