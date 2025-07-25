import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- IMPORTANT: Path adjustment for robust module imports ---
# This block ensures that Python can find modules in 'tools' and 'backend'
# regardless of whether app.py is run from the project root or a subdirectory.
import sys
# Get the directory where app.py resides (e.g., /path/to/project_root/backend)
current_app_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level to reach the project root (e.g., /path/to/project_root)
project_root_dir = os.path.dirname(current_app_dir)
# Add the project root to sys.path
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)
# --- END Path adjustment ---

# Import the analysis functions from your tools
try:
    from tools.analyse_spending_patterns import (
        analyze_financial_data,
        suggest_expense_category,
        get_financial_goal_breakdown
    )
    from tools.home_loan_affordability import analyze_home_loan_affordability
    logging.info("Successfully imported financial analysis tools.")
except ImportError as e:
    logging.error(f"Failed to import financial analysis tools: {e}. Make sure 'tools' directory is correctly set up and files exist.")
    # Exit or handle gracefully if core components can't be loaded
    sys.exit(1)


# Configure logging (consistent with other files)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing requests from different origins

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """
    A simple health check endpoint to verify the API is running.
    """
    logging.info("Health check requested.")
    return jsonify({"status": "healthy", "message": "Artha-X API is running!"}), 200

# Endpoint for overall financial analysis (Artha-X main analysis)
@app.route('/analyze_spending', methods=['POST'])
def analyze_spending_route():
    """
    Analyzes user's financial spending patterns using the Artha-X persona.
    Requires 'user_id' in the request JSON.
    """
    logging.info("Received request for /analyze_spending")
    if not request.is_json:
        logging.warning("analyze_spending: Request must be JSON.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        logging.warning("analyze_spending: 'user_id' is missing from request.")
        return jsonify({"status": "error", "message": "'user_id' is required"}), 400

    logging.info(f"Calling analyze_financial_data for user_id: {user_id}")
    result = analyze_financial_data(user_id)
    
    # Check for specific login_required error from MCP
    if result.get("error") == "login_required" and result.get("login_url"):
        logging.info(f"MCP login required for user {user_id}. Redirecting to login_url.")
        return jsonify({
            "status": "login_required",
            "message": result.get("message", "MCP login required."),
            "login_url": result["login_url"]
        }), 401 # Unauthorized

    # Handle other errors or success
    if result.get("status") == "error":
        logging.error(f"Error analyzing spending for user {user_id}: {result.get('message')}. Details: {result.get('details')}")
        return jsonify(result), 500 # Internal Server Error
    
    logging.info(f"Successfully analyzed spending for user_id: {user_id}")
    return jsonify(result), 200

# Endpoint for expense category suggestion
@app.route('/suggest_category', methods=['POST'])
def suggest_category_route():
    """
    Suggests a financial category for a given expense description.
    Requires 'description' in the request JSON.
    """
    logging.info("Received request for /suggest_category")
    if not request.is_json:
        logging.warning("suggest_category: Request must be JSON.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    description = data.get('description')

    if not description:
        logging.warning("suggest_category: 'description' is missing from request.")
        return jsonify({"status": "error", "message": "'description' is required"}), 400

    logging.info(f"Calling suggest_expense_category for description: '{description}'")
    result = suggest_expense_category(description)

    if result.get("status") == "error":
        logging.error(f"Error suggesting category for '{description}': {result.get('message')}. Details: {result.get('details')}")
        return jsonify(result), 500
    
    logging.info(f"Successfully suggested category for '{description}'")
    return jsonify(result), 200

# Endpoint for financial goal breakdown
@app.route('/goal_breakdown', methods=['POST'])
def goal_breakdown_route():
    """
    Provides a structured breakdown for a financial goal, considering user's context.
    Requires 'goal' and 'user_id' in the request JSON.
    """
    logging.info("Received request for /goal_breakdown")
    if not request.is_json:
        logging.warning("goal_breakdown: Request must be JSON.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    goal = data.get('goal')
    user_id = data.get('user_id')

    if not goal or not user_id:
        logging.warning("goal_breakdown: 'goal' or 'user_id' is missing from request.")
        return jsonify({"status": "error", "message": "'goal' and 'user_id' are required"}), 400

    logging.info(f"Calling get_financial_goal_breakdown for user_id: {user_id}, goal: '{goal}'")
    result = get_financial_goal_breakdown(goal, user_id)

    # Check for specific login_required error from MCP
    if result.get("error") == "login_required" and result.get("login_url"):
        logging.info(f"MCP login required for user {user_id}. Redirecting to login_url.")
        return jsonify({
            "status": "login_required",
            "message": result.get("message", "MCP login required."),
            "login_url": result["login_url"]
        }), 401 # Unauthorized

    if result.get("status") == "error":
        logging.error(f"Error getting goal breakdown for user {user_id}, goal '{goal}': {result.get('message')}. Details: {result.get('details')}")
        return jsonify(result), 500
    
    logging.info(f"Successfully generated goal breakdown for user_id: {user_id}, goal: '{goal}'")
    return jsonify(result), 200

# Endpoint for home loan affordability analysis
@app.route('/analyze_home_loan', methods=['POST'])
def analyze_home_loan_route():
    """
    Analyzes user's home loan affordability based on their financial context and query.
    Requires 'user_id' and 'user_query' in the request JSON.
    """
    logging.info("Received request for /analyze_home_loan")
    if not request.is_json:
        logging.warning("analyze_home_loan: Request must be JSON.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    user_id = data.get('user_id')
    user_query = data.get('user_query')

    if not user_id or not user_query:
        logging.warning("analyze_home_loan: 'user_id' or 'user_query' is missing from request.")
        return jsonify({"status": "error", "message": "'user_id' and 'user_query' are required"}), 400

    logging.info(f"Calling analyze_home_loan_affordability for user_id: {user_id}, query: '{user_query}'")
    result = analyze_home_loan_affordability(user_id, user_query)

    # Check for specific login_required error from MCP
    if result.get("error") == "login_required" and result.get("login_url"):
        logging.info(f"MCP login required for user {user_id}. Redirecting to login_url.")
        return jsonify({
            "status": "login_required",
            "message": result.get("message", "MCP login required."),
            "login_url": result["login_url"]
        }), 401 # Unauthorized

    if result.get("status") == "error":
        logging.error(f"Error analyzing home loan for user {user_id}, query '{user_query}': {result.get('message')}. Details: {result.get('details')}")
        return jsonify(result), 500
    
    logging.info(f"Successfully analyzed home loan for user_id: {user_id}, query: '{user_query}'")
    return jsonify(result), 200

if __name__ == '__main__':
    # When running locally, Flask's debug mode provides auto-reloading and helpful error pages.
    # For production, you would typically use a WSGI server like Gunicorn.
    logging.info("Starting Flask application...")
    app.run(debug=True, host='0.0.0.0', port=5000)
