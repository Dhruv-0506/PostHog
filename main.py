# main.py (PostHog Analytics with Blueprint)
import os
import requests
from flask import Blueprint, jsonify, request, current_app
from flasgger import swag_from # Assuming you might want Swagger docs
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

# Load .env for local development if this file were run standalone (less common now)
load_dotenv()

# --- Configuration for PostHog ---
POSTHOG_INSTANCE_URL = "https://us.posthog.com"
POSTHOG_PROJECT_ID = "128173"
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY") # Loaded from environment

# --- Insight IDs (Numeric or Short IDs that will be converted) ---
# If these are short_ids that need conversion to numeric_id, the get_insight_numeric_id function
# will be used where appropriate. For simplicity, I'm assuming these might be direct numeric IDs
# or short_ids that your get_insight_numeric_id handles.
# The previous version had DAU_INSIGHT_ID as a direct numeric string.
DAU_INSIGHT_ID = "2370862" # Assuming this is the numeric ID
WAU_INSIGHT_SHORT_ID = "F0cK26vH" # Short ID for WAU
RETENTION_INSIGHT_SHORT_ID = "qkZyszZl" # Short ID for Retention
GROWTH_ACCOUNTING_INSIGHT_SHORT_ID = "uJFgIYDk" # Short ID for Growth Accounting

# --- Create a Blueprint for PostHog analytics ---
# All routes defined here will be prefixed with /analytics
posthog_bp = Blueprint('posthog_analytics', __name__, url_prefix='/analytics')


# --- Helper Functions (modified to use current_app.logger) ---

def get_date_range_params(time_range_str: str, custom_start_date_str: str = None, custom_end_date_str: str = None):
    today = date.today()
    params = {}

    if time_range_str == "today":
        params["date_from"] = today.strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "yesterday":
        yesterday = today - timedelta(days=1)
        params["date_from"] = yesterday.strftime("%Y-%m-%d")
        params["date_to"] = yesterday.strftime("%Y-%m-%d")
    elif time_range_str == "this_week":
        start_of_week = today - timedelta(days=today.weekday())
        params["date_from"] = start_of_week.strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "last_7_days":
        params["date_from"] = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "last_30_days":
        params["date_from"] = (today - timedelta(days=29)).strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "last_90_days":
        params["date_from"] = (today - timedelta(days=89)).strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "custom":
        if custom_start_date_str and custom_end_date_str:
            try:
                # Validate date format
                datetime.strptime(custom_start_date_str, "%Y-%m-%d")
                datetime.strptime(custom_end_date_str, "%Y-%m-%d")
                params["date_from"] = custom_start_date_str
                params["date_to"] = custom_end_date_str
            except ValueError:
                return {"error": "Invalid custom date format. Use YYYY-MM-DD."}
        else:
            return {"error": "Custom time range requires start_date and end_date parameters."}
    else: # Default or unrecognized time_range, could default to last_7_days or return empty
        current_app.logger.warning(f"[PostHog] Unrecognized time_range_str: {time_range_str}. Defaulting to no date filter.")
        # Or you could default:
        # params["date_from"] = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        # params["date_to"] = today.strftime("%Y-%m-%d")
    return params

def get_insight_numeric_id(short_id: str):
    """ Fetches the numeric ID for an insight given its short_id. """
    if not POSTHOG_API_KEY:
        current_app.logger.error("[PostHog] POSTHOG_API_KEY not set for get_insight_numeric_id.")
        return None

    headers = {"Authorization": f"Bearer {POSTHOG_API_KEY}"}
    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/?short_id={short_id}"
    current_app.logger.info(f"[PostHog] Fetching numeric ID for short_id {short_id} from {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("count", 0) > 0 and data.get("results") and len(data["results"]) > 0:
            numeric_id = str(data["results"][0]["id"])
            current_app.logger.info(f"[PostHog] Found numeric ID {numeric_id} for short_id {short_id}")
            return numeric_id
        else:
            current_app.logger.warning(f"[PostHog] No results or count zero for short_id {short_id}. Response: {data}")
            return None
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"[PostHog] Error getting numeric ID for {short_id}: {str(e)}")
    except Exception as e: # Catch any other unexpected errors
        current_app.logger.error(f"[PostHog] Unexpected error getting numeric ID for {short_id}: {str(e)}")
    return None

def fetch_posthog_insight_data(insight_numeric_id: str, date_params: dict = None):
    if not POSTHOG_API_KEY:
        current_app.logger.error("[PostHog] Missing POSTHOG_API_KEY for fetching insight data.")
        return {"error": "Missing PostHog API key configuration"}, 500

    if not insight_numeric_id: # Ensure we have a numeric ID
        current_app.logger.error("[PostHog] Missing numeric insight ID for fetching data.")
        return {"error": "Missing numeric insight ID"}, 400

    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
        "Content-Type": "application/json",
    }

    params_req = {"refresh": "true"} # Ensure we get fresh data
    if date_params:
        params_req.update(date_params)

    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/{insight_numeric_id}/"
    current_app.logger.info(f"[PostHog] Fetching insight data from: {url} with params: {params_req}")

    try:
        response = requests.get(url, headers=headers, params=params_req, timeout=30)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json(), 200
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[PostHog] HTTPError fetching insight {insight_numeric_id}: {e.response.status_code} - {e.response.text}")
        return {"error": f"PostHog API HTTP error: {e.response.status_code}", "details": e.response.text}, e.response.status_code
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"[PostHog] RequestException fetching insight {insight_numeric_id}: {str(e)}")
        return {"error": f"PostHog API connection error: {str(e)}"}, 503 # Service Unavailable
    except Exception as e: # Catch any other unexpected errors
        current_app.logger.error(f"[PostHog] Unexpected error fetching insight {insight_numeric_id}: {str(e)}")
        return {"error": f"Unexpected error processing insight request: {str(e)}"}, 500


def get_insight_data_for_endpoint(insight_identifier: str, is_short_id: bool = False):
    time_range = request.args.get("time_range", "last_7_days") # Default to last_7_days
    custom_start = request.args.get("start_date")
    custom_end = request.args.get("end_date")

    date_params = get_date_range_params(time_range, custom_start, custom_end)
    if "error" in date_params: # Check if get_date_range_params returned an error object
        return jsonify(date_params), 400

    numeric_id_to_fetch = insight_identifier
    if is_short_id:
        current_app.logger.info(f"[PostHog] Converting short_id '{insight_identifier}' to numeric ID for endpoint.")
        numeric_id_to_fetch = get_insight_numeric_id(insight_identifier)
        if not numeric_id_to_fetch:
            err_msg = f"Could not resolve short_id '{insight_identifier}' to a numeric insight ID."
            current_app.logger.error(f"[PostHog] {err_msg}")
            return jsonify({"error": err_msg}), 500 # Internal server error or bad request

    data, status_code = fetch_posthog_insight_data(numeric_id_to_fetch, date_params)
    return jsonify(data), status_code

# --- Blueprint Routes ---
# Example of how to add Swagger documentation to a blueprint route
# You would define the YAML content in a separate file or inline.
# For brevity, I'm omitting the full @swag_from definitions.

@posthog_bp.route("/dau", methods=["GET"])
# @swag_from('your_swagger_doc_for_dau.yml')
def get_dau():
    """ Fetches Daily Active Users insight data. """
    current_app.logger.info("[PostHog] /dau endpoint hit.")
    return get_insight_data_for_endpoint(DAU_INSIGHT_ID, is_short_id=False) # DAU_INSIGHT_ID is numeric

@posthog_bp.route("/wau", methods=["GET"])
def get_wau():
    """ Fetches Weekly Active Users insight data. """
    current_app.logger.info("[PostHog] /wau endpoint hit.")
    # WAU uses a short_id that needs to be converted
    return get_insight_data_for_endpoint(WAU_INSIGHT_SHORT_ID, is_short_id=True)

@posthog_bp.route("/retention", methods=["GET"])
def get_retention():
    """ Fetches Retention insight data. """
    current_app.logger.info("[PostHog] /retention endpoint hit.")
    return get_insight_data_for_endpoint(RETENTION_INSIGHT_SHORT_ID, is_short_id=True)

@posthog_bp.route("/growth-accounting", methods=["GET"])
def get_growth_accounting():
    """ Fetches Growth Accounting insight data. """
    current_app.logger.info("[PostHog] /growth-accounting endpoint hit.")
    return get_insight_data_for_endpoint(GROWTH_ACCOUNTING_INSIGHT_SHORT_ID, is_short_id=True)


@posthog_bp.route("/health", methods=["GET"])
def health_check_posthog():
    """ Health check for the PostHog analytics module. """
    current_app.logger.info("[PostHog] Analytics module health check.")
    # Optionally, try a quick check of the PostHog API key
    if not POSTHOG_API_KEY:
        return jsonify({"status": "unhealthy", "module": "posthog_analytics", "reason": "POSTHOG_API_KEY not set"}), 503
    return jsonify({"status": "healthy", "module": "posthog_analytics"}), 200

# No app.run() here, as this is a blueprint to be registered by application.py
