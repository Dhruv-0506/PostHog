import os
import requests
from flask import Flask, jsonify, request
from flasgger import Swagger, swag_from
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, WEEKLY, MO, SU # For week start/end

# --- Configuration ---
load_dotenv()

POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")
POSTHOG_INSTANCE_URL = os.environ.get("POSTHOG_INSTANCE_URL")
POSTHOG_PROJECT_ID = os.environ.get("POSTHOG_PROJECT_ID")

DAU_INSIGHT_ID = os.environ.get("DAU_INSIGHT_ID")
WAU_INSIGHT_ID = os.environ.get("WAU_INSIGHT_ID")
RETENTION_INSIGHT_ID = os.environ.get("RETENTION_INSIGHT_ID")
GROWTH_ACCOUNTING_INSIGHT_ID = os.environ.get("GROWTH_ACCOUNTING_INSIGHT_ID")

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
    """
    Converts a time range string into date_from and date_to parameters.
    Returns a dictionary with 'date_from' and 'date_to' keys (YYYY-MM-DD format) or None.
    """
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
        params["date_to"] = today.strftime("%Y-%m-%d") # Or end of month: (today.replace(day=1) + relativedelta(months=1) - timedelta(days=1)).strftime("%Y-%m-%d")
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
        # For "all_time", we typically omit date_from and date_to for PostHog API
        # or PostHog might have a specific way to denote this (e.g. "all")
        # For now, returning an empty dict signifies no specific date range override
        # which means PostHog will use the insight's default or its own "all time" logic.
        return {} # No specific date params, rely on insight default or PostHog's all time
    elif time_range_str == "custom":
        if custom_start_date_str and custom_end_date_str:
            try:
                # Validate date format (optional but good)
                datetime.strptime(custom_start_date_str, "%Y-%m-%d")
                datetime.strptime(custom_end_date_str, "%Y-%m-%d")
                params["date_from"] = custom_start_date_str
                params["date_to"] = custom_end_date_str
            except ValueError:
                # Handle invalid date format if needed, or let PostHog API handle it
                app.logger.warning(f"Invalid custom date format: start={custom_start_date_str}, end={custom_end_date_str}")
                return {"error": "Invalid custom date format. Use YYYY-MM-DD."} # Error dict
        else:
            return {"error": "Custom time range requires start_date and end_date parameters."}
    else: # Default to insight's saved time range if no valid time_range_str
        return {}

    return params


# --- Modified Helper Function to Fetch Data from PostHog ---
def fetch_posthog_insight_data(insight_id: str, date_params: dict = None):
    """
    Fetches data for a given PostHog insight ID, with optional date range overrides.
    """
    if not all([POSTHOG_API_KEY, POSTHOG_INSTANCE_URL, POSTHOG_PROJECT_ID]):
        # ... (same global config check as before) ...
        missing_configs = [ name for name, var in [("POSTHOG_API_KEY", POSTHOG_API_KEY), ("POSTHOG_INSTANCE_URL", POSTHOG_INSTANCE_URL), ("POSTHOG_PROJECT_ID", POSTHOG_PROJECT_ID)] if not var]
        error_msg = f"Missing global PostHog configuration(s): {', '.join(missing_configs)}"
        app.logger.error(error_msg)
        return {"error": "Server configuration error", "details": error_msg}, 500

    if not insight_id:
        # ... (same insight_id check as before) ...
        error_msg = "Insight ID parameter is missing for fetch_posthog_insight_data function."
        app.logger.error(error_msg)
        return {"error": "Internal server error", "details": error_msg}, 500

    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
        "Content-Type": "application/json",
    }

    # Construct query parameters for PostHog API
    query_params = {"refresh": "true"} # Always refresh when applying dynamic filters
    if date_params and "date_from" in date_params and "date_to" in date_params:
        query_params["date_from"] = date_params["date_from"]
        query_params["date_to"] = date_params["date_to"]
    # Add other potential overrides here if needed (e.g., interval)

    # Use the base insight endpoint, not /results/, to allow parameter overrides
    api_url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/{insight_id}/"

    try:
        response = requests.get(api_url, headers=headers, params=query_params, timeout=45) # Increased timeout
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.HTTPError as errh:
        # ... (same HTTPError handling as before) ...
        error_message = f"PostHog API HTTP Error: {errh.response.status_code} for insight {insight_id} with params {query_params}"
        try: error_detail = errh.response.json(); error_message += f" - Details: {error_detail}"
        except ValueError: error_message += f" - Response: {errh.response.text}"
        app.logger.error(error_message)
        return {"error": "Failed to fetch data from PostHog", "details": error_message}, errh.response.status_code
    except requests.exceptions.ConnectionError as errc:
        # ... (same ConnectionError handling as before) ...
        error_msg = f"Error connecting to PostHog for insight {insight_id}: {errc}"
        app.logger.error(error_msg)
        return {"error": "Error connecting to PostHog", "details": error_msg}, 503
    except requests.exceptions.Timeout as errt:
        # ... (same Timeout handling as before) ...
        error_msg = f"Request to PostHog timed out for insight {insight_id}: {errt}"
        app.logger.error(error_msg)
        return {"error": "Request to PostHog timed out", "details": error_msg}, 504
    except requests.exceptions.RequestException as err:
        # ... (same RequestException handling as before) ...
        error_msg = f"An unexpected error occurred while fetching data for insight {insight_id}: {err}"
        app.logger.error(error_msg)
        return {"error": "An unexpected error occurred", "details": error_msg}, 500

# --- Modified Flask Endpoints ---
# Common function to handle request parsing and calling fetch
def get_insight_data_for_endpoint(insight_id_env_var_name: str, default_insight_id: str):
    time_range_str = request.args.get("time_range", "last_7_days") # Default if not provided
    custom_start_date = request.args.get("start_date")
    custom_end_date = request.args.get("end_date")

    date_params_or_error = get_date_range_params(time_range_str, custom_start_date, custom_end_date)

    if "error" in date_params_or_error: # Check if get_date_range_params returned an error
        return jsonify(date_params_or_error), 400 # Bad Request

    if not default_insight_id:
        return jsonify({"error": f"{insight_id_env_var_name} not configured on the server"}), 404

    data, status_code = fetch_posthog_insight_data(default_insight_id, date_params_or_error)
    return jsonify(data), status_code


@app.route("/dau", methods=["GET"])
@swag_from({
    'summary': 'Get Daily Active Users (DAU) data for a specified time range.',
    'parameters': [
        {
            'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False,
            'description': 'Time range preset. E.g., "today", "this_week", "last_month", "year_to_date", "last_7_days", "custom". Default: "last_7_days".',
            'default': 'last_7_days',
            'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]
        },
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'Required if time_range is "custom". Format: YYYY-MM-DD.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'Required if time_range is "custom". Format: YYYY-MM-DD.'}
    ],
    'responses': { # ... (responses as before) ...
        200: {'description': 'DAU data retrieved.'}, 400: {'description': 'Bad request (e.g. invalid time_range or custom dates).'}, 404: {'description': 'DAU_INSIGHT_ID not configured.'}, 500: {'description': 'Server error.'}
    }
})
def get_dau():
    return get_insight_data_for_endpoint("DAU_INSIGHT_ID", DAU_INSIGHT_ID)

@app.route("/wau", methods=["GET"])
@swag_from({
    'summary': 'Get Weekly Active Users (WAU) data for a specified time range.',
    'parameters': [ # Same parameters as /dau
        { 'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False, 'description': 'Time range preset.', 'default': 'last_30_days', 'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]},
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': { # ... (responses as before) ...
         200: {'description': 'WAU data retrieved.'}, 400: {'description': 'Bad request.'}, 404: {'description': 'WAU_INSIGHT_ID not configured.'}, 500: {'description': 'Server error.'}
    }
})
def get_wau():
    return get_insight_data_for_endpoint("WAU_INSIGHT_ID", WAU_INSIGHT_ID) # Default time_range for WAU could be last_30_days or similar

@app.route("/retention", methods=["GET"])
@swag_from({
    'summary': 'Get User Retention data for a specified time range.',
    'description': 'Note: Retention insights might have specific ways their date ranges are interpreted by PostHog.',
    'parameters': [ # Same parameters as /dau
        { 'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False, 'description': 'Time range preset.', 'default': 'last_90_days', 'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]},
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': { # ... (responses as before) ...
        200: {'description': 'Retention data retrieved.'}, 400: {'description': 'Bad request.'}, 404: {'description': 'RETENTION_INSIGHT_ID not configured.'}, 500: {'description': 'Server error.'}
    }
})
def get_retention():
    return get_insight_data_for_endpoint("RETENTION_INSIGHT_ID", RETENTION_INSIGHT_ID)

@app.route("/growth-accounting", methods=["GET"])
@swag_from({
    'summary': 'Get Growth Accounting data for a specified time range.',
    'description': 'Note: Growth Accounting insights might have specific ways their date ranges are interpreted by PostHog.',
    'parameters': [ # Same parameters as /dau
        { 'name': 'time_range', 'in': 'query', 'type': 'string', 'required': False, 'description': 'Time range preset.', 'default': 'last_30_days', 'enum': ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "year_to_date", "last_7_days", "last_30_days", "last_90_days", "all_time", "custom"]},
        {'name': 'start_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'},
        {'name': 'end_date', 'in': 'query', 'type': 'string', 'format': 'date', 'required': False, 'description': 'For custom time_range.'}
    ],
    'responses': { # ... (responses as before) ...
        200: {'description': 'Growth Accounting data retrieved.'}, 400: {'description': 'Bad request.'}, 404: {'description': 'GROWTH_ACCOUNTING_INSIGHT_ID not configured.'}, 500: {'description': 'Server error.'}
    }
})
def get_growth_accounting():
    return get_insight_data_for_endpoint("GROWTH_ACCOUNTING_INSIGHT_ID", GROWTH_ACCOUNTING_INSIGHT_ID)

@app.route("/health", methods=["GET"])
# ... (health check as before) ...
@swag_from({ 'summary': 'Health Check', 'description': 'A simple health check endpoint.', 'responses': { 200: {'description': 'Service is healthy.'}}})
def health_check():
    return jsonify({"status": "healthy", "message": "PostHog agent is up and running."}), 200

# --- Main Execution (for local development) ---
if __name__ == "__main__":
    # ... (same startup checks as before) ...
    if not all([POSTHOG_API_KEY, POSTHOG_INSTANCE_URL, POSTHOG_PROJECT_ID]):
        print("ERROR: Missing one or more critical PostHog environment variables...")
        # ... (print missing vars) ...
        exit(1)

    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
