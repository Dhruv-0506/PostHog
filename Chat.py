Chat.py
import os
import requests
import json
from flask import Blueprint, request, jsonify, current_app # Import current_app
from flasgger import swag_from # Assuming you might want Swagger docs for this too
from dotenv import load_dotenv
Load .env for local development of this blueprint if run standalone (less common now)
load_dotenv()
Configuration specific to the chat agent
ON_DEMAND_API_KEY = os.environ.get("ON_DEMAND_API_KEY")
ON_DEMAND_EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")
BASE_URL = "https://api.on-demand.io/chat/v1"
Create a Blueprint for the chat agent
All routes defined in this blueprint will be prefixed with /chat_agent
chat_bp = Blueprint('chat_agent', name, url_prefix='/chat_agent')
--- Helper Functions (create_chat_session, submit_query) ---
Modify these to use current_app.logger instead of app.logger
def create_chat_session(api_key, external_user_id):
url = f"{BASE_URL}/sessions"
headers = {"apikey": api_key, "Content-Type": "application/json"}
body = {"agentIds": [], "externalUserId": external_user_id}
current_app.logger.info(f"[ChatAgent] Attempting to create session at URL: {url}")
try:
response = requests.post(url, headers=headers, json=body)
response.raise_for_status()
response_data = response.json()
session_id = response_data.get("data", {}).get("id")
if session_id:
current_app.logger.info(f"[ChatAgent] Chat session created. Session ID: {session_id}")
return session_id
else:
current_app.logger.error(f"[ChatAgent] Error: 'data.id' not found. Full response: {response_data}")
return None
except requests.exceptions.HTTPError as e:
current_app.logger.error(f"[ChatAgent] HTTP error creating session: {e.response.status_code} - {e.response.text}")
return None
# ... (add other exception handling as before) ...
return None
def submit_query(api_key, session_id, query_text, response_mode="sync"):
url = f"{BASE_URL}/sessions/{session_id}/query"
headers = {"apikey": api_key, "Content-Type": "application/json"}
agent_ids_list = ["agent-1712327325", "agent-1713962163", "agent-1747649298"]
stop_sequences_list = []
body = {
"endpointId": "predefined-openai-gpt4.1", "query": query_text, "agentIds": agent_ids_list,
"responseMode": response_mode, "reasoningMode": "low",
"modelConfigs": {
"fulfillmentPrompt": "", "stopSequences": stop_sequences_list, "temperature": 0.7,
"topP": 1, "maxTokens": 4000, "presencePenalty": 0, "frequencyPenalty": 0
},
}
current_app.logger.info(f"[ChatAgent] Attempting to submit query to URL: {url}")
try:
if response_mode == "sync":
response = requests.post(url, headers=headers, json=body)
response.raise_for_status()
current_app.logger.info("[ChatAgent] Sync query submitted successfully.")
return response.json()
# ... (handle other response_mode if necessary) ...
except requests.exceptions.HTTPError as e:
current_app.logger.error(f"[ChatAgent] HTTP error submitting query: {e.response.status_code} - {e.response.text}")
# ... (add other exception handling as before) ...
return None
--- Blueprint Routes ---
@chat_bp.route('/chat', methods=['POST'])
@swag_from({ ... Swagger docs for this endpoint ... }) # Optional
def chat_endpoint():
current_app.logger.info("--- Chat Agent /chat endpoint HIT ---")
# Use the ON_DEMAND_API_KEY and ON_DEMAND_EXTERNAL_USER_ID loaded at the top of this file
if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>" or 
not ON_DEMAND_EXTERNAL_USER_ID or ON_DEMAND_EXTERNAL_USER_ID == "<replace_external_user_id>":
current_app.logger.error("[ChatAgent] API_KEY or EXTERNAL_USER_ID not configured.")
return jsonify({"error": "Chat Agent: Server configuration error for API credentials."}), 500
data = request.get_json()
if not data or 'query' not in data:
    return jsonify({"error": "Missing 'query' in request body"}), 400

user_query = data['query']
current_app.logger.info(f"[ChatAgent] Received query: {user_query}")

session_id = create_chat_session(ON_DEMAND_API_KEY, ON_DEMAND_EXTERNAL_USER_ID)
if not session_id:
    return jsonify({"error": "Chat Agent: Failed to create chat session"}), 500

sync_response_data = submit_query(ON_DEMAND_API_KEY, session_id, user_query, response_mode="sync")
if sync_response_data:
    try:
        response_text = sync_response_data.get("data", {}).get("queryResult", {}).get("text")
        if response_text:
            return jsonify({"reply": response_text})
        else:
            return jsonify({"warning": "Could not extract reply text", "full_response": sync_response_data})
    except Exception as e:
        return jsonify({"error": "Error parsing agent response", "details": str(e)}), 500
else:
    return jsonify({"error": "Chat Agent: Failed to get response from agent"}), 500

@chat_bp.route("/health", methods=["GET"])
def health_check():
current_app.logger.info("[ChatAgent] Health check.")
return jsonify({"status": "healthy", "module": "chat_agent"}), 200
