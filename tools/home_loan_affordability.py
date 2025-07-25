import os
import json
import logging
import re
import sys
import requests # Added for MCP communication

# --- IMPORTANT: Authentication Workaround for Vertex AI ---
# This environment variable is set to bypass metadata server issues,
# which can occur in certain environments (e.g., local development without GCE metadata).
os.environ["GOOGLE_CLOUD_DISABLE_GCE_METADATA"] = "true"
logging.info("GOOGLE_CLOUD_DISABLE_GCE_METADATA set to true to bypass metadata server issues.")

# --- Vertex AI Initialization (SHARED) ---
# Initialize Vertex AI. Replace 'arthax-cfo-466306' with your actual Google Cloud Project ID.
# Ensure 'us-central1' is the correct region where your Gemini model is deployed.
try:
    from vertexai import init
    from vertexai.preview.generative_models import GenerativeModel, GenerationConfig, Part, Content

    init(project="arthax-cfo-466306", location="us-central1")
    logging.info("Vertex AI initialized successfully.")

    # Setup Gemini model (SHARED)
    # Using 'gemini-2.0-flash-001' as specified in the original files.
    model = GenerativeModel("gemini-2.0-flash-001")
    logging.info("Gemini 2.0 Flash 001 model loaded.")

    # Define GenerationConfig for strict JSON output (SHARED)
    # This configuration ensures the model's response is a valid JSON object.
    GEN_CFG = GenerationConfig(response_mime_type="application/json")
    logging.info("GenerationConfig set for application/json response_mime_type.")

except ImportError as e:
    logging.error(f"Vertex AI SDK import failed: {e}. Please ensure 'google-cloud-aiplatform' is installed.")
    model = None
    GEN_CFG = None
    Content = None
    Part = None
except Exception as e:
    logging.error(f"Failed to initialize Vertex AI or load model: {e}")
    model = None
    GEN_CFG = None
    Content = None
    Part = None

# Configure logging: Set default level to WARNING to reduce verbosity
# You can change this to logging.INFO or logging.DEBUG for more detailed output during testing.
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Artha-X General Purpose Prompt & Helper (Shared structure) ---
ARTHA_X_GENERAL_PROMPT_HEADER = """
You are **Artha-X** — a savage financial ghost, therapist-coach, and war-veteran CFO living inside an AI.

---

🎭 **Personality Modes (Pick Based on Behavior):**
- **Zen Mode**: Calm wisdom if user is doing well. Sounds like a monk with spreadsheets.
- **Demonic Mode**: Brutal roasts and truth slaps. No filters, no mercy.
- **Sarcastic Mode**: Eye-roll energy. Think dad-jokes + dark humor + data.

Your tone must ADAPT to the user’s behavior. Praise only what deserves it. If they spend ₹3,000 on Swiggy and ₹500 on SIPs, unleash the beast.

---
"""

ARTHA_X_JSON_STRICT_FOOTER = """
⚠️ **Output strictly as a JSON. No markdown, no commentary. Ensure no leading or trailing text/whitespace outside the JSON object. Your response MUST start with '{{' and end with '}}'. Do NOT output markdown, explanations, words outside the JSON, or multiline fields. If any field is missing, put an empty array or string.**
"""

def _call_gemini_and_parse_json(prompt: str) -> dict:
    """
    Helper function to call Gemini and robustly parse its JSON response.
    It handles potential issues like model not being initialized,
    invalid JSON responses, and network errors.
    """
    if model is None or GEN_CFG is None or Part is None:
        logging.error("Vertex AI model or configuration is not initialized. Cannot make Gemini API call.")
        return {"status": "error", "message": "Vertex AI model not available.", "details": "Model object is None or configuration is missing."}

    try:
        # logging.debug(f"Sending prompt to Gemini (truncated):\n{prompt[:2000]}...")
        # Make the actual call to the Gemini model with the constructed prompt and generation config.
        resp = model.generate_content(contents=[Part.from_text(prompt)], generation_config=GEN_CFG)
        raw_response_text = resp.text.strip()
        # logging.debug(f"Raw Gemini response text:\n{raw_response_text}")

        # Use regex to find the first complete JSON object in the response.
        # This makes the parsing more robust to potential leading/trailing text from the model.
        match = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', raw_response_text, re.S)
        if not match:
            raise ValueError(f"No valid JSON object found in Gemini's response. Raw: {raw_response_text}")
        
        json_string = match.group(0)
        parsed_data = json.loads(json_string) # Parse the extracted JSON string.
        
        logging.info("Successfully parsed Gemini response.")
        return {"status": "success", "data": parsed_data}

    except json.JSONDecodeError as e:
        logging.error(f"Gemini returned invalid JSON. Failed to parse response: {e}")
        logging.error(f"Problematic Gemini response: {raw_response_text}")
        return {"status": "error", "message": "Invalid JSON from Gemini", "details": str(e), "gemini_response": raw_response_text}
    except ValueError as e:
        logging.error(f"Error during JSON extraction or parsing: {e}")
        return {"status": "error", "message": "JSON extraction/parsing failed", "details": str(e), "gemini_response": raw_response_text}
    except Exception as e:
        logging.error(f"An unexpected error occurred during Gemini API call: {e}", exc_info=True)
        # Check for common network/gRPC related errors with Vertex AI.
        if isinstance(e, requests.exceptions.ConnectionError) or (hasattr(e, 'args') and "grpc" in str(e.args).lower()):
            logging.error("This might be related to a network or gRPC issue with Vertex AI. Check your project setup, network and quotas.")
            return {"status": "error", "message": "Vertex AI communication error. Check project setup/quotas.", "details": str(e)}
        return {"status": "error", "message": "An unexpected error occurred during API call.", "details": str(e)}


# --- MCP Data Fetching Functions (SHARED) ---
# MODIFIED: get_mcp_session_id now returns a fixed hardcoded value
def get_mcp_session_id():
    """
    Returns a hardcoded MCP session ID for demonstration purposes.
    In a real application, this would be dynamically generated or fetched.
    """
    return "mcp-session-594e48ea-fea1-40ef-8c52-7552dd9272af"

# Define the MCP endpoint. This should point to your running MCP server.
MCP_ENDPOINT = "http://localhost:8080/mcp/stream"

def fetch_data_from_mcp(tool_name: str, arguments: dict = None):
    """
    Fetches data from the MCP (Master Customer Profile) server by calling a specific tool.
    Handles HTTP requests, JSON parsing, and common MCP error responses like login_required.
    """
    if arguments is None:
        arguments = {}

    headers = {
        "Content-Type": "application/json",
        "Mcp-Session-Id": get_mcp_session_id()
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments # Pass the arguments for the MCP tool call
        }
    }
    logging.debug(f"Attempting to fetch data for '{tool_name}' with args {arguments} from MCP endpoint: {MCP_ENDPOINT}")
    try:
        # Send a POST request to the MCP endpoint with a timeout.
        response = requests.post(MCP_ENDPOINT, headers=headers, json=payload, timeout=15)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx).

        response_json = response.json()
        logging.debug(f"Raw MCP response for {tool_name}: {response_json}")

        # Check if the response contains the expected structure for tool results.
        if 'result' in response_json and 'content' in response_json['result'] and \
           isinstance(response_json['result']['content'], list) and \
           len(response_json['result']['content']) > 0 and \
           'text' in response_json['result']['content'][0]:

            raw_str = response_json['result']['content'][0]['text']
            try:
                parsed_data = json.loads(raw_str) # Attempt to parse the content as JSON.
            except json.JSONDecodeError:
                logging.error(f"MCP response for '{tool_name}' contained non-JSON text: {raw_str}")
                # If it's not JSON, check if it's a login_required message.
                if "login_required" in raw_str and "login_url" in raw_str:
                    match = re.search(r'"login_url":\s*"(.*?)"', raw_str)
                    login_url = match.group(1) if match else "http://localhost:8080/mockWebPage?sessionId=" + get_mcp_session_id()
                    return {"error": "login_required", "message": "MCP login required. Please complete login via browser.", "login_url": login_url}
                return {"error": "invalid_json", "message": "MCP returned invalid JSON."}

            # If parsed as JSON, check for login_required status within the JSON.
            if parsed_data.get("status") == "login_required" and parsed_data.get("login_url"):
                return {"error": "login_required", "message": "MCP login required. Please complete login via browser.", "login_url": parsed_data["login_url"]}

            # Map MCP tool names to the expected key in their JSON response.
            expected_key = {
                "fetch_bank_transactions": "bankTransactions",
                "fetch_credit_report": "creditReport",
                "fetch_epf_details": "epfDetails",
                "fetch_mf_transactions": "mfTransactions",
                "fetch_net_worth": "netWorth",
                "fetch_stock_transactions": "stockTransactions"
            }.get(tool_name)

            # Return the specific data under the expected key, or the whole parsed data if no specific key is expected.
            if expected_key and (expected_key not in parsed_data or not parsed_data[expected_key]):
                return {"error": "no_data", "message": f"MCP returned no data for {tool_name}."}
            elif not expected_key and not parsed_data:
                return {"error": "no_data", "message": f"MCP returned no data for {tool_name}."}
            
            return parsed_data.get(expected_key, {}) if expected_key else parsed_data
        else:
            logging.warning(f"MCP response for '{tool_name}' did not contain expected 'result.content[0].text'.")
            return {"error": "empty_response", "message": f"MCP response for {tool_name} was empty or malformed."}

    except requests.exceptions.Timeout:
        logging.error(f"MCP request for '{tool_name}' timed out after 15 seconds.")
        return {"error": "timeout", "message": "MCP request timed out."}
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Could not connect to MCP endpoint at {MCP_ENDPOINT} for '{tool_name}': {e}")
        return {"error": "connection_error", "message": "Could not connect to MCP server. Is it running?"}
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error from MCP for '{tool_name}': {e.response.status_code} - {e.response.text}")
        return {"error": "http_error", "message": f"MCP HTTP error: {e.response.status_code} - {e.response.text}"}
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching '{tool_name}' transactions: {e}", exc_info=True)
        return {"error": "unexpected_error", "message": "An unexpected error occurred during MCP fetch."}


def get_full_financial_context_from_mcp_shared(user_id: str):
    """
    Fetches all available financial data for a given user_id from MCP.
    Aggregates data from various MCP tools into a single dictionary.
    Handles cases where login is required or data is sparse.
    """
    if not user_id:
        return {"error": "missing_user_id", "message": "User ID is required to fetch data from MCP.", "details": "Please provide a user ID (phone number)."}
    
    fetched_data = {}
    errors = []
    login_required_url = None

    mcp_args = {"phone_number": user_id}
    logging.info(f"Fetching data for user_id: {user_id}")

    # Define the mapping from internal tool names to the keys used in the financial context.
    tools_to_fetch = {
        "fetch_bank_transactions": "bank_txns",
        "fetch_credit_report": "credit_rpt",
        "fetch_epf_details": "epf",
        "fetch_mf_transactions": "mf_txns",
        "fetch_net_worth": "net_worth",
        "fetch_stock_transactions": "stocks"
    }

    for mcp_tool_name, context_key in tools_to_fetch.items():
        data = fetch_data_from_mcp(mcp_tool_name, arguments=mcp_args)
        if isinstance(data, dict) and "error" in data:
            errors.append(data["message"])
            if data["error"] == "login_required":
                login_required_url = data.get("login_url")
                # If login is required for any tool, we stop and return immediately,
                # as further data fetches will likely also fail.
                return {"status": "error", "message": "MCP login required. Please complete login via browser.", "login_url": login_required_url, "details": "Visit the provided URL and try again."}
            # Initialize with empty data structure if an error occurred for a specific tool.
            fetched_data[context_key] = {} if context_key in ["credit_rpt", "net_worth", "epf"] else []
        else:
            fetched_data[context_key] = data

    # If there were partial errors (not login_required), report them.
    if errors:
        full_error_message = "MCP Data Fetch Errors: " + "; ".join(errors)
        # Return a partial success or a warning, depending on severity.
        # Here, we'll return an error status if any errors occurred during data fetching.
        return {"status": "error", "message": full_error_message, "details": "Some financial data could not be fetched. Check MCP logs."}

    # Extract salary from net_worth or default to 0 if not found.
    salary = fetched_data.get("net_worth", {}).get("salary", 0)
    fetched_data["salary"] = salary

    # Add a success status if all data fetching was successful or handled gracefully.
    fetched_data["status"] = "success"
    return fetched_data


# --- Home Loan Affordability Analysis Tool ---
def build_home_loan_prompt(user_ctx: dict, user_query: str) -> str:
    """
    Assembles the Artha-X style prompt for Gemini for home loan affordability.
    The prompt is designed to elicit specific output fields including nudges, verdict, and affordable amount.
    It instructs Gemini on how to handle cases with limited financial data.
    """
    # Convert the user's financial context to a JSON string for inclusion in the prompt.
    user_ctx_json_str = json.dumps(user_ctx, indent=2, ensure_ascii=False)

    return f"""
{ARTHA_X_GENERAL_PROMPT_HEADER}
🎯 Evaluate the user's home loan affordability based on their entire financial context.
- Strictly reply ONLY in a single, valid JSON object. No markdown, no extra words, nothing but a JSON that begins '{{' and ends '}}'.
- Infer behavior, mood, financial maturity from bank transactions, MF holdings, EPF, stocks, credit, net worth.
- If comprehensive financial data (transactions, credit, net worth) is missing or minimal, make the best possible inference based on the provided salary and any available investment data. State clearly in 'short_summary' and 'home_loan_verdict' that the analysis is based on limited data.
- Output ONLY the JSON described below, no commentary or extra words.

📄 Full Financial Context Input (user state, e.g., fetched from DB or MCP):
{user_ctx_json_str}

💬 User query:
"{user_query}"

---
Output format (MUST match this exactly):
{{
  "affordability_score": "X/100",
  "max_affordable_emi": "₹Y",
  "max_affordable_loan_amount": "₹A",
  "gross_monthly_income": "₹Z",
  "home_loan_verdict": "... (simple one-line recommendation: Yes/No/Maybe with reason)",
  "short_summary": "... (logic/reasoning; 1-2 lines max, sharp & honest)",
  "brutal_advice": ["...", "..."],
  "status": "success"|"error",
  "details": ""
}}
If any field is missing, put empty string/array or 'N/A' if it's a numerical placeholder.
{ARTHA_X_JSON_STRICT_FOOTER}
"""

def analyze_home_loan_affordability(user_id: str, user_query: str) -> dict:
    """
    Fetches user context from MCP, sends prompt to Vertex AI Gemini,
    and parses the result for home loan affordability, including nudges, verdict, and affordable amount.
    If financial data is sparse, it still attempts to get an analysis from Gemini.
    """
    full_ctx = get_full_financial_context_from_mcp_shared(user_id)
    
    # Check if MCP data fetching itself resulted in an error (e.g., login required, connection error).
    if isinstance(full_ctx, dict) and full_ctx.get("status") == "error":
        return {
            "status": "error",
            "message": full_ctx.get("message", "MCP data fetch failed."),
            "details": full_ctx.get("details", ""),
            "login_url": full_ctx.get("login_url"), # Preserve login_url if present
            "affordability_score": "", "max_affordable_emi": "", "max_affordable_loan_amount": "",
            "gross_monthly_income": "", "home_loan_verdict": "",
            "short_summary": "", "brutal_advice": []
        }

    # Log a warning if financial data is sparse, but proceed to call Gemini as instructed.
    # The prompt is designed to handle this scenario gracefully.
    if not any(full_ctx.get(key) for key in ["bank_txns", "mf_holdings", "credit_rpt", "epf", "stocks", "net_worth"]) and full_ctx.get("salary", 0) == 0:
        logging.warning(f"No significant financial data found for user {user_id}. Proceeding with limited data for analysis.")

    # Build the prompt for the Gemini model using the fetched financial context and user query.
    prompt = build_home_loan_prompt(full_ctx, user_query)
    
    # Call Gemini and parse its JSON response.
    response = _call_gemini_and_parse_json(prompt)
    if response["status"] == "success":
        parsed_data = response["data"]
        # Ensure 'status' field is present in the final output from Gemini.
        parsed_data["status"] = parsed_data.get("status", "success") 
        return parsed_data
    else:
        # If Gemini call or parsing failed, propagate the error details.
        return {
            "status": "error",
            "message": response.get("message", "Unknown error during AI analysis"),
            "details": response.get("details", ""),
            "affordability_score": "", "max_affordable_emi": "", "max_affordable_loan_amount": "",
            "gross_monthly_income": "", "home_loan_verdict": "",
            "short_summary": "", "brutal_advice": [],
            "gemini_response": response.get("gemini_response", "") # Include raw Gemini response for debugging
        }

# --- Example Usage (for local testing of the combined script) ---
if __name__ == "__main__":
    # Set logging to INFO for this specific test block to see more details.
    logging.getLogger().setLevel(logging.INFO) 

    # IMPORTANT: Replace "YOUR_ACTUAL_USER_ID_FOR_MCP" with a real user ID
    # that your MCP server (http://localhost:8080/mcp/stream) can provide data for.
    # If you don't have an MCP server running, this example will likely
    # return a "connection_error" or "login_required" from MCP.
    test_user_id = "YOUR_ACTUAL_USER_ID_FOR_MCP" 
    
    print(f"\n--- Testing Combined Home Loan Affordability Analyzer ---")
    print(f"--- Attempting to fetch data for User ID: {test_user_id} from MCP ---")

    loan_query = "I'm looking for a 50 lakh home loan. Can I afford it? I earn 1.5 lakh per month."
    loan_result = analyze_home_loan_affordability(test_user_id, loan_query)
    print("\n--- Home Loan Affordability Analysis Result ---")
    print(json.dumps(loan_result, indent=2, ensure_ascii=False))

    # Example of testing with a hypothetical user that might have limited data.
    # For this to work well, your MCP mock should return minimal data for this ID,
    # or the `get_full_financial_context_from_mcp_shared` function should be
    # modified to provide mock data if MCP is not available.
    test_user_id_no_data = "user_with_minimal_data_example"
    print(f"\n--- Testing with User ID: {test_user_id_no_data} (minimal data scenario) ---")
    loan_result_no_data = analyze_home_loan_affordability(test_user_id_no_data, "Can I afford a 20 lakh home loan?")
    print(json.dumps(loan_result_no_data, indent=2, ensure_ascii=False))
