import os
import json
import matplotlib
matplotlib.use("Agg") # Use the Agg backend for non-interactive environments
import matplotlib.pyplot as plt
import logging
import re

# Import shared utilities from the new backend/gemini_mcp_utils.py
from backend.gemini_mcp_utils import (
    model,
    GEN_CFG,
    get_full_financial_context_from_mcp_shared,
    Content,
    Part
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Prompt template with Persona Instructions for financial analysis
PROMPT_TEMPLATE = '''
You are **Artha-X** — a savage financial ghost, therapist-coach, and war-veteran CFO living inside an AI.

---

🎭 **Personality Modes (Pick Based on Behavior):**
- **Zen Mode**: Calm wisdom if user is doing well. Sounds like a monk with spreadsheets.
- **Demonic Mode**: Brutal roasts and truth slaps. No filters, no mercy.
- **Sarcastic Mode**: Eye-roll energy. Think dad-jokes + dark humor + data.

Your tone must ADAPT to the user’s behavior. Praise only what deserves it. If they spend ₹3,000 on Swiggy and ₹500 on SIPs, unleash the beast.

---

🎯 **Tasks:**
1. **Flag Food Spending**
    - Identify food delivery, restaurant spends (Zomato, Swiggy, CCD, Uber Eats)
        - Example output:
            > "₹1,639 on Zomato? Hope those fries were worth your dreams of early retirement."

    2. **Flag Emotional or Impulse Spending**
        - Look for late-night orders, Amazon book buys, gadget splurges.
            - Example:
                > "₹450 for a book you’ll never finish and ₹180 for overpriced foam milk? Say hello to dopamine budgeting."

    3. **Score Investments (1-10)**
        - Track SIPs, Mutual Funds, Stocks
            - Judge diversification, frequency, discipline
                - Example:
                    > "You’ve married one fund and ghosted the rest. Portfolio score: 4/10."

    4. **Generate 3 Nudges**
        - Must be brutal, hilarious, or sharp. Avoid fluff.
            - Examples:
                - "Delete Swiggy. Cook twice. Save ₹600 and your gut."
                - "Add 10% more to SIPs. Future You just whispered ‘Thanks, boss.’"
                - "Before every Amazon order, ask: ‘Will I remember this in 6 months?’"

---

🧠 **Few-Shot Behavior Oracle Sample (for Gemini Context)**
Input:
"Amazon Book ₹450, CCD Coffee ₹180, Swiggy Dinner ₹410, SIP ₹1,000"

Sample Output:
{{
  "categories": [
    {{"type": "FOOD", "total": "₹590", "pattern": "Swiggy and CCD are your emotional crutches. Eat feelings, pay EMIs."}},
    {{"type": "EMOTIONAL", "examples": ["Amazon Book ₹450", "CCD Coffee ₹180"]}},
    {{"type": "INVESTMENT", "total": "₹1,000", "score": "6/10", "pattern": "Consistent SIP but no diversification. Your money’s on auto-pilot but going nowhere fast."}}
  ],
  "nudges": [
    "Uninstall food delivery apps. They're eating your goals.",
    "Build an actual investment plan. SIP isn’t a silver bullet.",
    "Buy coffee powder. Save ₹180 per day = ₹5,400/month. Hello, Bali trip."
  ]
}}

---

🏦 **Assume Context**
- User salary = ₹{salary}/month
- They provided these raw bank transactions below
- Feel free to infer behavior, mood, financial maturity based on patterns
- Be savage when necessary. Be wise when earned.

📊 **Additional Data (If Available):**
- **Credit Report**: For debt behavior, EMIs, credit score, and overleveraging.
- **Mutual Fund Transactions**: For detailed SIPs, withdrawals, and fund switches.
- **EPF Account**: For long-term retirement savings habits and employer contributions.
- **Stock Transactions**: For risk appetite, trading vs. investing mindset.
- **Net Worth Snapshot**: For total assets vs. liabilities, and detecting lifestyle inflation.

Use this additional data to:
- Judge if user is living below, at, or above their means.
- Detect financial red flags like debt-spending while investing.
- Highlight when net worth is good but behavior is poor (or vice versa).

⚠️ **Output strictly as a JSON. No markdown, no commentary. Ensure no leading or trailing text/whitespace outside the JSON object. Your response MUST start with '{{' and end with '}}'. Do NOT output markdown, explanations, words outside the JSON, or multiline fields. If any field is missing, put an empty array or string.**
{{
  "categories": [
    {{"type": "FOOD", "total": "₹X", "pattern": "..."}},
    {{"type": "EMOTIONAL", "examples": ["..."]}},
    {{"type": "INVESTMENT", "total": "₹Y", "score": "Z/10", "pattern": "..."}},
    {{"type": "CREDIT_BEHAVIOR", "score": "W/10", "pattern": "..."}},
    {{"type": "LIFESTYLE_INFLATION", "pattern": "...", "net_worth_flag": "Red/Yellow/Green"}}
  ],
  "nudges": ["...", "...", "..."]
}}

---

📉 **Do you need net worth to analyze spending patterns?**
If provided, yes — it allows you to:
- Judge spending vs actual savings
- Flag lifestyle inflation
- Detect hidden debt risks
- Say things like: "You’ve got ₹5L in mutual funds but spend like it’s 2008 Lehman crash."

But if not available, base your fire solely on transaction flow.

---

📄 **Full Financial Context Input Below (includes transactions and other data):**
{txns}
'''

# Analysis function
def analyze_financial_data(user_id: str) -> dict: # MODIFIED: Accepts user_id
    """
    Fetches all financial data for the given user_id from MCP and then analyzes it using Gemini.
    """
    full_ctx = get_full_financial_context_from_mcp_shared(user_id) # Pass user_id to shared utility
    if "error" in full_ctx:
        return {"status": "error", "message": full_ctx["message"], "details": full_ctx["details"], "login_url": full_ctx.get("login_url")} # Pass login_url

    # Check if any actual data was fetched (beyond just empty structures)
    # Using 'credit_rpt' as the key for credit report, matching get_full_financial_context_from_mcp_shared
    if not any(full_ctx.get(key) for key in ["bank_txns", "mf_txns", "credit_rpt", "epf", "stocks", "net_worth"]) and full_ctx.get("salary",0) == 0: # Use 0 for salary check
        logging.warning(f"No financial data provided for analysis for user {user_id} after MCP fetch.")
        return {"status": "error", "message": "No financial data available for analysis for this user. (MCP might be returning empty data)", "details": "Please ensure MCP server is running and returning data for this user ID."}

    try:
        salary = full_ctx.get("salary", "N/A")
        context_text = json.dumps(full_ctx, indent=2)
        logging.debug(f"Full context sent to Gemini (truncated):\n{context_text[:1000]}...")

        prompt = PROMPT_TEMPLATE.format(txns=context_text, salary=salary)
        logging.debug(f"Full prompt to Gemini (truncated):\n{prompt[:2000]}...")

        logging.info("Calling Gemini model for analysis...")

        resp = model.generate_content(prompt, generation_config=GEN_CFG)
        raw = resp.text.strip()
        logging.debug(f"Raw Gemini response text:\n{raw}")

        m = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', raw, re.S)
        if not m:
            logging.error("Gemini did not return a valid JSON object in its response.")
            return {"status": "error", "message": "Gemini returned invalid JSON for analysis.", "details": raw}

        json_str = m.group(0)
        result = json.loads(json_str)
        logging.info("Successfully parsed Gemini's analysis.")
        result["status"] = "success"
        return result
    except json.JSONDecodeError as e:
        logging.error(f"Gemini returned invalid JSON. Failed to parse response: {e}")
        logging.error(f"Problematic Gemini response: {raw}")
        return {"status": "error", "message": "Invalid JSON from Gemini for analysis", "details": str(e), "gemini_response": raw}
    except ValueError as e:
        logging.error(f"Error during JSON extraction or parsing: {e}")
        return {"status": "error", "message": "JSON extraction/parsing failed", "details": str(e), "gemini_response": raw}
    except Exception as e:
        logging.error(f"An unexpected error occurred during Gemini analysis: {e}", exc_info=True)
        # Attempt to catch specific Vertex AI related errors
        import requests
        if isinstance(e, requests.exceptions.ConnectionError) or isinstance(e, Exception) and "grpc" in str(e).lower():
            logging.error("This might be related to a network or gRPC issue with Vertex AI. Check your project setup, network and quotas.")
            return {"status": "error", "message": "Vertex AI communication error. Check project setup/quotas.", "details": str(e)}
        return {"status": "error", "message": "An unexpected error occurred during analysis.", "details": str(e)}

# Function to visualize spending categories with pie chart
def plot_spending_pie(insights, img_buffer=None):
    labels = []
    values = []

    for cat in insights.get("categories", []):
        if "total" not in cat:
            continue
        try:
            amount = float(cat["total"].replace("₹", "").replace(",", "").strip())
            labels.append(cat["type"])
            values.append(amount)
        except ValueError:
            logging.warning(f"Could not parse total amount '{cat.get('total')}' for category '{cat.get('type')}'. Skipping.")
            continue

    if not values:
        logging.info("No numeric categories found for pie chart. Plotting skipped.")
        return

    plt.figure(figsize=(10, 7))
    plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, pctdistance=0.85)
    plt.title("Spending Distribution by Category", fontsize=16)
    plt.axis("equal")
    plt.tight_layout()

    if img_buffer:
        plt.savefig(img_buffer, format='png')
    else:
        plt.savefig('spending_distribution.png')
    logging.info("Spending distribution pie chart saved to spending_distribution.png.")


# LLM FEATURE 1: Expense Categorization Suggestor
def suggest_expense_category(description: str) -> dict:
    """
    Uses Gemini to suggest a category for a given expense description.
    """
    prompt = f"""
    You are a highly efficient financial categorization AI.
    Given a transaction description, suggest the most appropriate financial category.
    Be concise and provide only the category name.

    Examples:
    - Description: "Starbucks coffee"
    Category: "Food & Drink"
    - Description: "Electricity bill"
    Category: "Utilities"
    - Description: "Netflix subscription"
    Category: "Entertainment"
    - Description: "Flight ticket to Goa"
    Category: "Travel"
    - Description: "Monthly rent payment"
    Category: "Housing"
    - Description: "Gym membership"
    Category: "Health & Fitness"
    - Description: "Uber ride"
    Category: "Transportation"
    - Description: "Grocery shopping at Big Bazaar"
    Category: "Groceries"
    - Description: "Salary deposit"
    Category: "Income"
    - Description: "EMI for car loan"
    Category: "Loan Repayment"

    Description: "{description}"
    Category:
    """
    try:
        resp = model.generate_content(prompt)
        category_text = resp.text.strip()
        logging.info(f"Gemini suggested category for '{description}': {category_text}")
        return {"status": "success", "category": category_text}
    except Exception as e:
        logging.error(f"Error suggesting category for '{description}': {e}", exc_info=True)
        return {"status": "error", "message": "Could not suggest category", "details": str(e)}

# LLM FEATURE 2: Financial Goal Breakdown
def get_financial_goal_breakdown(goal: str, user_id: str) -> dict: # MODIFIED: Accepts user_id
    """
    Uses Gemini to provide a structured breakdown for a financial goal,
    considering the provided financial context fetched from MCP.
    Tailor the advice based on their current financial situation (salary, net worth, debt, investments).
    Include concrete steps, potential challenges, and a rough timeline.
    Output strictly as a JSON object with the following structure:
    {{
      "goal": "...",
      "summary": "...",
      "steps": [
        {{"step": "...", "details": "..."}},
        ...
      ],
      "challenges": ["...", "..."],
      "timeline_estimate": "..."
    }}
    If any field is missing, use an empty string or array.
    """
    full_ctx = get_full_financial_context_from_mcp_shared(user_id) # Pass user_id to shared utility
    if "error" in full_ctx:
        return {"status": "error", "message": full_ctx["message"], "details": full_ctx["details"], "login_url": full_ctx.get("login_url")} # Pass login_url

    salary = full_ctx.get("salary", "N/A")
    context_text = json.dumps(full_ctx, indent=2)
    
    prompt = f"""
    You are Artha-X, a no-nonsense financial strategist.
    Given a financial goal and the user's financial context, provide a brutal, actionable, and realistic breakdown.
    Tailor the advice based on their current financial situation (salary, net worth, debt, investments).
    Include concrete steps, potential challenges, and a rough timeline.
    Output strictly as a JSON object with the following structure:
    {{
      "goal": "...",
      "summary": "...",
      "steps": [
        {{"step": "...", "details": "..."}},
        ...
      ],
      "challenges": ["...", "..."],
      "timeline_estimate": "..."
    }}
    If any field is missing, use an empty string or array.

    User's Monthly Salary: ₹{salary}
    User's Financial Context:
    {context_text}

    Financial Goal: "{goal}"
    """
    try:
        resp = model.generate_content(prompt, generation_config=GEN_CFG)
        raw = resp.text.strip()
        logging.debug(f"Raw Gemini response for goal breakdown:\n{raw}")

        m = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', raw, re.S)
        if not m:
            logging.error("Gemini did not return a valid JSON object for goal breakdown.")
            return {"status": "error", "message": "Gemini returned invalid JSON for goal breakdown.", "details": raw}

        json_str = m.group(0)
        result = json.loads(json_str)
        logging.info(f"Gemini provided breakdown for goal: {goal}")
        result["status"] = "success"
        return result
    except json.JSONDecodeError as e:
        logging.error(f"Gemini returned invalid JSON for goal breakdown: {e}")
        logging.error(f"Problematic Gemini response: {raw}")
        return {"status": "error", "message": "Invalid JSON from Gemini for goal breakdown", "details": str(e), "gemini_response": raw}
    except Exception as e:
        logging.error(f"An unexpected error occurred during goal breakdown analysis: {e}", exc_info=True)
        return {"status": "error", "message": "Goal breakdown analysis failed", "details": str(e)}

__all__ = [
    "analyze_financial_data",
    "plot_spending_pie",
    "suggest_expense_category",
    "get_financial_goal_breakdown"
]
