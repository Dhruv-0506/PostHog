import os
import requests
from flask import Flask, jsonify, request
from flasgger import Swagger, swag_from
# from dotenv import load_dotenv # You might not need this if only API_KEY is from env
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, WEEKLY, MO, SU

# --- Configuration ---
# load_dotenv() # Keep if you still want to test API_KEY locally via .env

# Hardcode these values - REPLACE WITH YOUR ACTUAL VALUES
POSTHOG_INSTANCE_URL = "https://us.posthog.com"  
POSTHOG_PROJECT_ID = "128173"                    

DAU_INSIGHT_ID = "E6G99KnQ"
WAU_INSIGHT_ID = "F0cK26vH" 
RETENTION_INSIGHT_ID = "qkZyszZl"
GROWTH_ACCOUNTING_INSIGHT_ID = "uJFgIYDk"

# Keep API Key as an environment variable for security
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")


app = Flask(__name__)
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}
swagger = Swagger(app, config=swagger_config)

# --- Date Range Helper ---
def get_date_range_params(time_range_str: str, custom_start_date_str: str = None, custom_end_date_str: str = None):
    # ... (Date Range Helper function remains exactly the same) ...
    today = date.today()
    params = {}

    if time_range_str == "today":
        params["date_from"] = today.strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "yesterday":
        yesterday = today - timedelta(days=1)
        params["date_from"] = yesterday.strftime("%Y-%m-%d")
        params["date_to"] = yesterday.strftime("%Y-%m-%d")
    elif time_range_str == "this_week": # Assuming Monday as start of week
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        params["date_from"] = start_of_week.strftime("%Y-%m-%d")
        params["date_to"] = end_of_week.strftime("%Y-%m-%d")
    elif time_range_str == "last_week":
        last_week_end = today - timedelta(days=today.weekday() + 1)
        last_week_start = last_week_end - timedelta(days=6)
        params["date_from"] = last_week_start.strftime("%Y-%m-%d")
        params["date_to"] = last_week_end.strftime("%Y-%m-%d")
    elif time_range_str == "this_month":
        params["date_from"] = today.replace(day=1).strftime("%Y-%m-%d")
        params["date_to"] = today.strftime("%Y-%m-%d")
    elif time_range_str == "last_month":
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        params["date_from"] = last_month_start.strftime("%Y-%m-%d")
        params["date_to"] = last_month_end.strftime("%Y-%m-%d")
    elif time_range_str == "year_to_date":
        params["date_from"] = today.replace(month=1, day=1).strftime("%Y-%m-%d")
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
    elif time_range_str == "all_time":
        return {}
    elif time_range_str == "custom":
        if custom_start_date_str and custom_end_date_str:
            try:
                datetime.strptime(custom_start_date_str, "%Y-%m-%d")
                datetime.strptime(custom_end_date_str, "%Y-%m-%d")
                params["date_from"] = custom_start_date_str
                params["date_to"] = custom_end_date_str
            except ValueError:
                app.logger.warning(f"Invalid custom date format: start={custom_start_date_str}, end={custom_end_date_str}")
                return {"error": "Invalid custom date format. Use YYYY-MM-DD."}
        else:
            return {"error": "Custom time range requires start_date and end_date parameters."}
    else:
        return {}
    return params

# --- Modified Helper Function to Fetch Data from PostHog ---
def fetch_posthog_insight_data(insight_id: str, date_params: dict = None):
    # ... (Fetch PostHog Insight Data function remains largely the same) ...
    # The check for global configs will now primarily be for POSTHOG_API_KEY
    if not POSTHOG_API_KEY: # Simplified check
        error_msg = "Missing global PostHog configuration: POSTHOG_API_KEY"
        app.logger.error(error_msg)
        return {"error": "Server configuration error", "details": error_msg}, 500

    # POSTHOG_INSTANCE_URL and POSTHOG_PROJECT_ID are now hardcoded global vars
    # No need to check them here again explicitly if hardcoded correctly

    if not insight_id: # This check is still valid for the passed parameter
        error_msg = "Insight ID parameter is missing for fetch_posthog_insight_data function."
        app.logger.error(error_msg)
        return {"error": "Internal server error", "details": error_msg}, 500

    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
        "Content-Type": "application/json",
    }
    query_params = {"refresh": "true"}
    if date_params and "date_from" in date_params and "date_to" in date_params:
        query_params["date_from"] = date_params["date_from"]
        query_params["date_to"] = date_params["date_to"]

    api_url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/{insight_id}/"

    try:
        response = requests.get(api_url, headers=headers, params=query_params, timeout=45)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.HTTPError as errh:
        error_message = f"PostHog API HTTP Error: {errh.response.status_code} for insight {insight_id} with params {query_params}"
        try: error_detail = errh.response.json(); error_message += f" - Details: {error_detail}"
        except ValueError: error_message += f" - Response: {errh.response.text}"
        app.logger.error(error_message)
        return {"error": "Failed to fetch data from PostHog", "details": error_message}, errh.response.status_code
    except requests.exceptions.ConnectionError as errc:
        error_msg = f"Error connecting to PostHog for insight {insight_id}: {errc}"
        app.logger.error(error_msg)
        return {"error": "Error connecting to PostHog", "details": error_msg}, 503
    except requests.exceptions.Timeout as errt:
        error_msg = f"Request to PostHog timed out for insight {insight_id}: {errt}"
        app.logger.error(error_msg)
        return {"error": "Request to PostHog timed out", "details": error_msg}, 504
    except requests.exceptions.RequestException as err:
        error_msg = f"An unexpected error occurred while fetching data for insight {insight_id}: {err}"
        app.logger.error(error_msg)
        return {"error": "An unexpected error occurred", "details": error_msg}, 500


# --- Modified Flask Endpoints ---
def get_insight_data_for_endpoint(hardcoded_insight_id: str): # Takes the hardcoded ID directly
    time_range_str = request.args.get("time_range", "last_7_days")
    custom_start_date = request.args.get("start_date")
    custom_end_date = request.args.get("end_date")

    date_params_or_error = get_date_range_params(time_range_str, custom_start_date, custom_end_date)

    if "error" in date_params_or_error:
        return jsonify(date_params_or_error), 400

    if not hardcoded_insight_id: # Check if the hardcoded ID is an empty string
        # This error message might need adjustment as it's no longer an "env_var_name"
        return jsonify({"error": "Insight ID for this endpoint is not properly hardcoded (empty)."}), 500

    data, status_code = fetch_posthog_insight_data(hardcoded_insight_id, date_params_or_error)
    return jsonify(data), status_code


@app.route("/dau", methods=["GET"])
@swag_from({
    'summary': 'Get Daily Active Users (DAU) data for a specified time range.',
    'parameters': [
        {
            'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False,
            'description': 'Time range preset. Default: "last_7_days".',
            'default': 'last_7_days',
            'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]
        },
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': {
        200: {'description': 'DAU data retrieved.'}, 400: {'description': 'Bad request.'}, 500: {'description': 'Server error.'}
    }
})
def get_dau():
    return get_insight_data_for_endpoint(DAU_INSIGHT_ID) # Pass the hardcoded global variable

@app.route("/wau", methods=["GET"])
@swag_from({
    'summary': 'Get Weekly Active Users (WAU) data for a specified time range.',
    'parameters': [
        { 'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False, 'description': 'Time range preset.', 'default': 'last_30_days', 'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]},
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': {
         200: {'description': 'WAU data retrieved.'}, 400: {'description': 'Bad request.'}, 500: {'description': 'Server error.'}
    }
})
def get_wau():
    return get_insight_data_for_endpoint(WAU_INSIGHT_ID) # Pass the hardcoded global variable

@app.route("/retention", methods=["GET"])
@swag_from({
    'summary': 'Get User Retention data for a specified time range.',
    'parameters': [
        { 'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False, 'description': 'Time range preset.', 'default': 'last_90_days', 'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]},
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': {
        200: {'description': 'Retention data retrieved.'}, 400: {'description': 'Bad request.'}, 500: {'description': 'Server error.'}
    }
})
def get_retention():
    return get_insight_data_for_endpoint(RETENTION_INSIGHT_ID) # Pass the hardcoded global variable

@app.route("/growth-accounting", methods=["GET"])
@swag_from({
    'summary': 'Get Growth Accounting data for a specified time range.',
    'parameters': [
        { 'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False, 'description': 'Time range preset.', 'default': 'last_30_days', 'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]},
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': {
        200: {'description': 'Growth Accounting data retrieved.'}, 400: {'description': 'Bad request.'}, 500: {'description': 'Server error.'}
    }
})
def get_growth_accounting():
    return get_insight_data_for_endpoint(GROWTH_ACCOUNTING_INSIGHT_ID) # Pass the hardcoded global variable

@app.route("/health", methods=["GET"])
@swag_from({ 'summary': 'Health Check', 'description': 'A simple health check endpoint.', 'responses': { 200: {'description': 'Service is healthy.'}}})
def health_check():
    return jsonify({"status": "healthy", "message": "PostHog agent is up and running."}), 200

# --- Main Execution (for local development) ---
if __name__ == "__main__":
    if not POSTHOG_API_KEY: # Only critical check left for startup is API Key
        print("ERROR: Missing critical PostHog environment variable: POSTHOG_API_KEY")
        print("Please set this environment variable.")
        exit(1)
    # Assume hardcoded values are correct and non-empty
    # You could add checks here for the hardcoded values if you want to be extra safe during development
    # e.g., if not POSTHOG_INSTANCE_URL or not POSTHOG_PROJECT_ID or not DAU_INSIGHT_ID:
    #          print("ERROR: One or more hardcoded PostHog configuration values are empty. Please check main.py")
    #          exit(1)

    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
