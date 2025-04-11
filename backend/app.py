from flask import Flask, jsonify, send_from_directory, request
import sys
import os
import traceback

# Add the project root directory (one level up from 'backend') to the Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask_cors import CORS
from backend.insight_engine.query_processor import process_merchant_question


# Import blueprints or route functions
from backend.api.routes import api_bp
from backend.data_access import loader

def create_app():
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    CORS(app) # Enable CORS for all routes

    # Load data once on startup
    try:
        loader.load_all_data()
        print("Mock data loaded successfully.")
    except Exception as e:
        print(f"Error loading mock data: {e}")
        # Decide how to handle this - exit or run without data?

    # Register API blueprint
    app.register_blueprint(api_bp, url_prefix='/api')

    # Serve the frontend's index.html
    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    # Serve other static files (CSS, JS, Libs)
    @app.route('/<path:path>')
    def serve_static_files(path):
         # Security check: Ensure the path is safe and within the frontend directory
        safe_path = os.path.abspath(os.path.join(app.static_folder, path))
        if not safe_path.startswith(os.path.abspath(app.static_folder)):
            return "Forbidden", 403
        # Check if file exists before sending
        if os.path.exists(safe_path):
             return send_from_directory(app.static_folder, path)
        else:
             return "Not Found", 404

    # Define the chat endpoint
    @app.route('/chat', methods=['POST'])
    def chat():
        try:
            # Get the JSON data sent from the frontend
            data = request.get_json()

            if not data or 'message' not in data:
                return jsonify({"error": "Missing 'message' in request body"}), 400

            user_message = data['message']

            # Process the message using your logic
            bot_reply = process_merchant_question('1d4f2',user_message)

            # Return the bot's reply as JSON
            return jsonify({"reply": bot_reply})

        except Exception as e:
            print(f"Error processing chat request: {e}") # Log the error server-side
            return jsonify({"error": "An internal server error occurred"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True) # debug=True for development