# main.py (PostHog Analytics with Blueprint - Matching Original Logic)
import os
import requests
from flask import Blueprint, jsonify, request, current_app
from flasgger import swag_from
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

load_dotenv()

# --- Configuration for PostHog ---
POSTHOG_INSTANCE_URL = "https://us.posthog.com"
POSTHOG_PROJECT_ID = "128173"
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")

# --- Numeric Insight IDs (as per your original working code's constants) ---
DAU_INSIGHT_ID = "2370862"
WAU_INSIGHT_ID = "2370863"
RETENTION_INSIGHT_ID = "2370864"
GROWTH_ACCOUNTING_INSIGHT_ID = "2370865"

# --- Create a Blueprint for PostHog analytics ---
posthog_bp = Blueprint('posthog_analytics', __name__, url_prefix='/analytics')


# --- Helper Functions ---

def get_date_range_params(time_range_str: str, custom_start_date_str: str = None, custom_end_date_str: str = None):
    today = date.today()
    params = {}
    # (Exact same logic as your original get_date_range_params)
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
                datetime.strptime(custom_start_date_str, "%Y-%m-%d")
                datetime.strptime(custom_end_date_str, "%Y-%m-%d")
                params["date_from"] = custom_start_date_str
                params["date_to"] = custom_end_date_str
            except ValueError:
                return {"error": "Invalid custom date format. Use YYYY-MM-DD."}
        else:
            return {"error": "Custom time range requires start_date and end_date parameters."}
    else: # If time_range_str is not recognized, PostHog will use the insight's default.
        current_app.logger.info(f"[PostHog] Unrecognized or unhandled time_range_str: '{time_range_str}'. No date params sent to PostHog; insight's default will be used.")
        return {} # Return empty dict for PostHog to use insight's default
    return params

# get_insight_numeric_id can remain for other potential uses, but won't be called by these main routes.
def get_insight_numeric_id(short_id: str): # Kept for utility, but not used by primary routes below
    if not POSTHOG_API_KEY:
        current_app.logger.error(f"[PostHog] get_insight_numeric_id: POSTHOG_API_KEY not set for short_id '{short_id}'.")
        return None
    headers = {"Authorization": f"Bearer {POSTHOG_API_KEY}"}
    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/?short_id={short_id}"
    current_app.logger.info(f"[PostHog] get_insight_numeric_id: Fetching for short_id '{short_id}' from {url}")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        current_app.logger.info(f"[PostHog] get_insight_numeric_id: Status for '{short_id}': {response.status_code}")
        if response.status_code != 200:
            current_app.logger.warning(f"[PostHog] get_insight_numeric_id: Non-200 ({response.status_code}) for '{short_id}'. Text: {response.text[:200]}")
        response.raise_for_status()
        data = response.json()
        if data.get("count", 0) > 0 and data.get("results") and isinstance(data["results"], list) and len(data["results"]) > 0:
            if "id" in data["results"][0]:
                numeric_id = str(data["results"][0]["id"])
                current_app.logger.info(f"[PostHog] get_insight_numeric_id: Found numeric ID '{numeric_id}' for short_id '{short_id}'.")
                return numeric_id
        current_app.logger.warning(f"[PostHog] get_insight_numeric_id: No valid result for short_id '{short_id}'. Data: {data}")
        return None
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[PostHog] get_insight_numeric_id: HTTPError for '{short_id}'. Status: {e.response.status_code}. Response: {e.response.text[:200]}")
    except requests.exceptions.JSONDecodeError as e:
        current_app.logger.error(f"[PostHog] get_insight_numeric_id: JSONDecodeError for '{short_id}'. Text: {response.text[:200]}. Error: {e}")
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"[PostHog] get_insight_numeric_id: RequestException for '{short_id}'. Error: {e}")
    except Exception as e:
        current_app.logger.error(f"[PostHog] get_insight_numeric_id: Unexpected error for '{short_id}'. Error: {e}")
    return None


def fetch_posthog_insight_data(insight_numeric_id: str, date_params: dict = None):
    # Using current_app.logger for blueprint context
    if not POSTHOG_API_KEY:
        current_app.logger.error("[PostHog] fetch_posthog_insight_data: Missing API key.")
        return {"error": "Missing API key"}, 500 # This will cause a 500 if API key is missing

    if not insight_numeric_id: # Should not happen if called with constants
        current_app.logger.error("[PostHog] fetch_posthog_insight_data: Missing insight ID.")
        return {"error": "Missing insight ID"}, 400

    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
        "Content-Type": "application/json",
    }

    # Use a mutable copy for params to avoid modifying the original dict if it was passed around
    request_params = {"refresh": "true"}
    if date_params: # date_params could be an empty dict if no specific range was handled
        request_params.update(date_params)

    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/{insight_numeric_id}/"
    current_app.logger.info(f"[PostHog] fetch_posthog_insight_data: Fetching insight '{insight_numeric_id}' from URL: {url} with params: {request_params}")

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        current_app.logger.info(f"[PostHog] fetch_posthog_insight_data: Response status for insight '{insight_numeric_id}': {response.status_code}")

        # Log non-200 responses before raise_for_status for more insight
        if response.status_code != 200:
            current_app.logger.warning(f"[PostHog] fetch_posthog_insight_data: Received non-200 status ({response.status_code}) for insight '{insight_numeric_id}'. Response text: {response.text[:500]}")
        
        response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
        return response.json(), 200
    except requests.exceptions.HTTPError as e: # Catching specific HTTP errors
        current_app.logger.error(f"[PostHog] fetch_posthog_insight_data: HTTPError for insight '{insight_numeric_id}'. Status Code: {e.response.status_code}. Response: {e.response.text[:500]}")
        # Return what PostHog returned, if possible, or a generic error
        return {"error": f"PostHog API returned HTTP {e.response.status_code}", "details": e.response.text[:200]}, e.response.status_code
    except requests.exceptions.JSONDecodeError as e:
        current_app.logger.error(f"[PostHog] fetch_posthog_insight_data: JSONDecodeError for insight '{insight_numeric_id}'. Failed to parse PostHog response. Error: {str(e)}. Response text: {response.text[:500]}")
        return {"error": "Failed to parse response from PostHog", "details": str(e)}, 500
    except requests.exceptions.RequestException as e: # Catches ConnectionError, Timeout, etc.
        current_app.logger.error(f"[PostHog] fetch_posthog_insight_data: RequestException for insight '{insight_numeric_id}'. Error: {str(e)}")
        # This is a server-side error in connecting to PostHog
        return {"error": "Error connecting to PostHog data source", "details": str(e)}, 503 # Service Unavailable is appropriate
    except Exception as e: # Catch any other unexpected errors during the request
        current_app.logger.error(f"[PostHog] fetch_posthog_insight_data: Unexpected error for insight '{insight_numeric_id}'. Error: {str(e)}")
        return {"error": "An unexpected server error occurred while fetching data", "details": str(e)}, 500


def get_insight_data_for_endpoint(insight_numeric_id: str): # No is_short_id needed now
    time_range = request.args.get("time_range", "last_7_days")
    custom_start = request.args.get("start_date")
    custom_end = request.args.get("end_date")

    date_params = get_date_range_params(time_range, custom_start, custom_end)
    if "error" in date_params: # Check if get_date_range_params returned an error object
        return jsonify(date_params), 400 # Return 400 for bad date params

    # insight_numeric_id is passed directly
    data, status_code = fetch_posthog_insight_data(insight_numeric_id, date_params)
    
    # If fetch_posthog_insight_data returns a status code that indicates an error,
    # jsonify will correctly use that status code for the HTTP response.
    return jsonify(data), status_code


# --- Blueprint Routes ---
@posthog_bp.route("/dau", methods=["GET"])
def get_dau():
    current_app.logger.info("[PostHog] /analytics/dau endpoint hit.")
    return get_insight_data_for_endpoint(DAU_INSIGHT_ID)

@posthog_bp.route("/wau", methods=["GET"])
def get_wau():
    current_app.logger.info("[PostHog] /analytics/wau endpoint hit.")
    return get_insight_data_for_endpoint(WAU_INSIGHT_ID)

@posthog_bp.route("/retention", methods=["GET"])
def get_retention():
    current_app.logger.info("[PostHog] /analytics/retention endpoint hit.")
    return get_insight_data_for_endpoint(RETENTION_INSIGHT_ID)

@posthog_bp.route("/growth-accounting", methods=["GET"])
def get_growth_accounting():
    current_app.logger.info("[PostHog] /analytics/growth-accounting endpoint hit.")
    return get_insight_data_for_endpoint(GROWTH_ACCOUNTING_INSIGHT_ID)

@posthog_bp.route("/health", methods=["GET"])
def health_check_posthog_blueprint():
    current_app.logger.info("[PostHog] /analytics/health endpoint hit.")
    if not POSTHOG_API_KEY:
        return jsonify({"status": "unhealthy", "module": "posthog_analytics_blueprint", "reason": "POSTHOG_API_KEY not set"}), 503
    return jsonify({"status": "healthy", "module": "posthog_analytics_blueprint"}), 200
