# backend/.py

import os

import sys

import re



# Add the project root to the Python path to allow finding modules

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

if project_root not in sys.path:
     sys.path.insert(0, project_root)



from insight_engine.query_processor import process_merchant_question



question = "Show me my daily report my latest operation date"



response = process_merchant_question("1d4f2", question)

print(f"Question: '{question}'")

print(f"Response: {response}")





# # from insight_engine.query_processor import get_merchant_context_prompt

# from data_access import loader

# from insight_engine.query_processor import get_available_data_schemas_prompt





# print(get_available_data_schemas_prompt())

