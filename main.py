# main.py (PostHog Analytics)
import os
import requests
from flask import Blueprint, jsonify, request, current_app # Import current_app
from flasgger import swag_from # Assuming you use Swagger here too
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

load_dotenv()

# Configuration for PostHog
POSTHOG_INSTANCE_URL = "https://us.posthog.com"
POSTHOG_PROJECT_ID = "128173"
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY") # Loaded from environment

# Insight IDs (keep as constants or make them dynamic if needed)
DAU_INSIGHT_ID = "2370862"
WAU_INSIGHT_ID = "2370863" # Consider fetching numeric ID if these are short_ids
RETENTION_INSIGHT_ID = "2370864"
GROWTH_ACCOUNTING_INSIGHT_ID = "2370865"

# Create a Blueprint for PostHog analytics
# All routes defined here will be prefixed with /analytics
posthog_bp = Blueprint('posthog_analytics', __name__, url_prefix='/analytics')


# --- Helper Functions (modified to use current_app.logger) ---
def get_date_range_params(time_range_str: str, custom_start_date_str: str = None, custom_end_date_str: str = None):
    # ... (your existing logic, no change needed in core logic) ...
    # For logging: current_app.logger.debug(...)
    today = date.today()
    params = {}
    # (rest of your get_date_range_params logic)
    if time_range_str == "today": # Example
        params["date_from"] = today.strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    # ... other cases ...
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
    return params


def fetch_posthog_insight_data(insight_id: str, date_params: dict = None):
    if not POSTHOG_API_KEY:
        current_app.logger.error("[PostHog] Missing POSTHOG_API_KEY.")
        return {"error": "Missing PostHog API key configuration"}, 500

    if not insight_id:
        return {"error": "Missing insight ID"}, 400

    headers = {"Authorization": f"Bearer {POSTHOG_API_KEY}", "Content-Type": "application/json"}
    params_req = {"refresh": "true"}
    if date_params:
        params_req.update(date_params)

    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/{insight_id}/"
    current_app.logger.info(f"[PostHog] Fetching insight: {url} with params: {params_req}")
    try:
        response = requests.get(url, headers=headers, params=params_req, timeout=30)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"[PostHog] API error: {str(e)}")
        return {"error": f"PostHog API error: {str(e)}"}, 500


def get_insight_data_for_endpoint(insight_id: str):
    time_range = request.args.get("time_range", "last_7_days")
    custom_start = request.args.get("start_date")
    custom_end = request.args.get("end_date")

    date_params = get_date_range_params(time_range, custom_start, custom_end)
    if "error" in date_params:
        return jsonify(date_params), 400

    data, status_code = fetch_posthog_insight_data(insight_id, date_params)
    return jsonify(data), status_code

# --- Blueprint Routes ---
@posthog_bp.route("/dau", methods=["GET"])
def get_dau():
    current_app.logger.info("[PostHog] /dau endpoint hit.")
    return get_insight_data_for_endpoint(DAU_INSIGHT_ID)

@posthog_bp.route("/wau", methods=["GET"])
def get_wau():
    current_app.logger.info("[PostHog] /wau endpoint hit.")
    return get_insight_data_for_endpoint(WAU_INSIGHT_ID) # Assuming WAU_INSIGHT_ID is numeric

@posthog_bp.route("/retention", methods=["GET"])
def get_retention():
    current_app.logger.info("[PostHog] /retention endpoint hit.")
    return get_insight_data_for_endpoint(RETENTION_INSIGHT_ID)

@posthog_bp.route("/growth-accounting", methods=["GET"])
def get_growth_accounting():
    current_app.logger.info("[PostHog] /growth-accounting endpoint hit.")
    return get_insight_data_for_endpoint(GROWTH_ACCOUNTING_INSIGHT_ID)


@posthog_bp.route("/health", methods=["GET"])
def health_check_posthog():
    current_app.logger.info("[PostHog] Health check.")
    return jsonify({"status": "healthy", "module": "posthog_analytics"}), 200

# REMOVE any app.run() or Gunicorn specific code if it was here
