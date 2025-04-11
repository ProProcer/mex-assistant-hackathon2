# backend/test_gemini.py
import os
import sys

# Add the project root to the Python path to allow finding modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
     sys.path.insert(0, project_root)

# Now import the service
from backend.insight_engine import gemini_service

print("Attempting to test Gemini service...")

# Check if the model was loaded in gemini_service
if gemini_service.model:
    print("Gemini model seems loaded. Trying to generate text...")
    test_prompt = "Berikan tim saya 'Kodang Koding Kiding' semangat untuk Hackhathon pertama kami"
    response = gemini_service.generate_text(test_prompt)
    print(f"Prompt: '{test_prompt}'")
    print(f"Response: {response}")
else:
    print("Gemini model not loaded in gemini_service. Check API key and configuration.")