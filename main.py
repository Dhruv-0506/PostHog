import os
import requests
from flask import Flask, jsonify, request
from flasgger import Swagger, swag_from
from datetime import datetime, timedelta, date

POSTHOG_INSTANCE_URL = "https://us.posthog.com"  
POSTHOG_PROJECT_ID = "128173"                    

DAU_INSIGHT_ID = "2370862"
WAU_INSIGHT_ID = "2370863" 
RETENTION_INSIGHT_ID = "2370864"
GROWTH_ACCOUNTING_INSIGHT_ID = "2370865"

POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")

app = Flask(__name__)
swagger = Swagger(app)

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
                datetime.strptime(custom_start_date_str, "%Y-%m-%d")
                datetime.strptime(custom_end_date_str, "%Y-%m-%d")
                params["date_from"] = custom_start_date_str
                params["date_to"] = custom_end_date_str
            except ValueError:
                return {"error": "Invalid custom date format. Use YYYY-MM-DD."}
        else:
            return {"error": "Custom time range requires start_date and end_date parameters."}
    else:
        return {}
    return params

def get_insight_numeric_id(short_id: str):
    if not POSTHOG_API_KEY:
        return None
        
    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
    }
    
    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/?short_id={short_id}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("count") > 0 and data.get("results"):
            return str(data["results"][0]["id"])
    except Exception as e:
        app.logger.error(f"Error getting numeric ID for {short_id}: {str(e)}")
    return None

def fetch_posthog_insight_data(insight_id: str, date_params: dict = None):
    if not POSTHOG_API_KEY:
        return {"error": "Missing API key"}, 500

    if not insight_id:
        return {"error": "Missing insight ID"}, 400

    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
        "Content-Type": "application/json",
    }

    params = {"refresh": "true"}
    if date_params:
        params.update(date_params)

    url = f"{POSTHOG_INSTANCE_URL}/api/projects/{POSTHOG_PROJECT_ID}/insights/{insight_id}/"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.RequestException as e:
        error_msg = f"PostHog API error: {str(e)}"
        return {"error": error_msg}, 500

def get_insight_data_for_endpoint(insight_id: str):
    time_range = request.args.get("time_range", "last_7_days")
    custom_start = request.args.get("start_date")
    custom_end = request.args.get("end_date")

    date_params = get_date_range_params(time_range, custom_start, custom_end)
    if "error" in date_params:
        return jsonify(date_params), 400

    data, status_code = fetch_posthog_insight_data(insight_id, date_params)
    return jsonify(data), status_code

@app.route("/dau", methods=["GET"])
def get_dau():
    return get_insight_data_for_endpoint(DAU_INSIGHT_ID)

@app.route("/wau", methods=["GET"])
def get_wau():
    # First get numeric ID if not already set
    global WAU_INSIGHT_ID
    if not WAU_INSIGHT_ID:
        WAU_INSIGHT_ID = get_insight_numeric_id("F0cK26vH")
    if not WAU_INSIGHT_ID:
        return jsonify({"error": "Could not get WAU insight ID"}), 500
    return get_insight_data_for_endpoint(WAU_INSIGHT_ID)

@app.route("/retention", methods=["GET"])
def get_retention():
    global RETENTION_INSIGHT_ID
    if not RETENTION_INSIGHT_ID:
        RETENTION_INSIGHT_ID = get_insight_numeric_id("qkZyszZl")
    if not RETENTION_INSIGHT_ID:
        return jsonify({"error": "Could not get retention insight ID"}), 500
    return get_insight_data_for_endpoint(RETENTION_INSIGHT_ID)

@app.route("/growth-accounting", methods=["GET"])
def get_growth_accounting():
    global GROWTH_ACCOUNTING_INSIGHT_ID
    if not GROWTH_ACCOUNTING_INSIGHT_ID:
        GROWTH_ACCOUNTING_INSIGHT_ID = get_insight_numeric_id("uJFgIYDk")
    if not GROWTH_ACCOUNTING_INSIGHT_ID:
        return jsonify({"error": "Could not get growth accounting insight ID"}), 500
    return get_insight_data_for_endpoint(GROWTH_ACCOUNTING_INSIGHT_ID)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    if not POSTHOG_API_KEY:
        print("ERROR: Missing POSTHOG_API_KEY environment variable")
        exit(1)
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
