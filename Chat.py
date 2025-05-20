# Chat.py (Revised based on comparison)
import os
import requests
import json
from flask import Blueprint, request, jsonify, current_app
from flasgger import swag_from
from dotenv import load_dotenv

load_dotenv()

ON_DEMAND_API_KEY = os.environ.get("ON_DEMAND_API_KEY")
ON_DEMAND_EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")
BASE_URL = "https://api.on-demand.io/chat/v1"

chat_bp = Blueprint('chat_agent', __name__, url_prefix='/chat_agent') # Keep consistent prefix

# --- Helper Functions (create_chat_session, submit_query) ---
# Use the robust versions from your "Current Chat.py" for these helpers.
# For brevity, I'll use placeholders but assume they are the ones with good logging and error handling.

def create_chat_session(api_key, external_user_id):
    url = f"{BASE_URL}/sessions"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    body = {"agentIds": [], "externalUserId": external_user_id}
    current_app.logger.info(f"[ChatAgent] create_chat_session: Attempting to create session. URL: {url}")
    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        current_app.logger.info(f"[ChatAgent] create_chat_session: Response status: {response.status_code}")
        if response.status_code != 201:
             current_app.logger.error(f"[ChatAgent] create_chat_session: Failed. Status: {response.status_code}, Response: {response.text[:500]}")
        response.raise_for_status()
        response_data = response.json()
        session_id = response_data.get("data", {}).get("id")
        if session_id:
            current_app.logger.info(f"[ChatAgent] create_chat_session: Session created. ID: {session_id}")
            return session_id
        else:
            current_app.logger.error(f"[ChatAgent] create_chat_session: 'data.id' not found. Response: {response_data}")
            return None
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[ChatAgent] create_chat_session: HTTPError. Status: {e.response.status_code if e.response else 'N/A'}, Response: {e.response.text[:500] if e.response else 'No response text'}")
    except Exception as e:
        current_app.logger.error(f"[ChatAgent] create_chat_session: Exception. Error: {str(e)}")
    return None

def submit_query(api_key, session_id, query_text, response_mode="sync"):
    url = f"{BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    # Agent IDs from "Current Chat.py"
    agent_ids_list = ["agent-1712327325", "agent-1713962163", "agent-1747649298"]
    stop_sequences_list = []
    body = {
        "endpointId": "predefined-openai-gpt4.1", "query": query_text, "agentIds": agent_ids_list,
        "responseMode": response_mode, "reasoningMode": "low",
        "modelConfigs": { # Using the specific fulfillmentPrompt from "Current Chat.py"
            "fulfillmentPrompt": """Provide only the direct answer to the user's query. Do not include any metadata, token counts, or conversational filler. Be concise and to the point.""",
            "stopSequences": stop_sequences_list, "temperature": 0.7,
            "topP": 1, "maxTokens": 4000, "presencePenalty": 0, "frequencyPenalty": 0
        },
    }
    current_app.logger.info(f"[ChatAgent] submit_query: Attempting query for session {session_id}. URL: {url}")
    try:
        if response_mode == "sync":
            response = requests.post(url, headers=headers, json=body, timeout=30) # Timeout for query
            current_app.logger.info(f"[ChatAgent] submit_query: Response status: {response.status_code}")
            if response.status_code != 200:
                 current_app.logger.error(f"[ChatAgent] submit_query: Failed. Status: {response.status_code}, Response: {response.text[:500]}")
            response.raise_for_status()
            response_data = response.json()
            current_app.logger.info("[ChatAgent] submit_query: Sync query success.")
            return response_data # Return the full dictionary
        else:
            current_app.logger.warning(f"[ChatAgent] submit_query: Unsupported responseMode '{response_mode}'.")
            return None
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[ChatAgent] submit_query: HTTPError. Session: {session_id}. Status: {e.response.status_code if e.response else 'N/A'}, Response: {e.response.text[:500] if e.response else 'No response text'}")
    except Exception as e:
        current_app.logger.error(f"[ChatAgent] submit_query: Exception. Session: {session_id}. Error: {str(e)}")
    return None

# --- Blueprint Routes ---
@chat_bp.route('/chat', methods=['POST']) # Changed from /chat_agent/chat to match OldChat.py if needed for Siri
def chat_endpoint(): # Renamed from ask_chat_agent_endpoint for consistency
    current_app.logger.info(f"--- [ChatAgent] {request.path} endpoint HIT ---")
    
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>" or \
       not ON_DEMAND_EXTERNAL_USER_ID or ON_DEMAND_EXTERNAL_USER_ID == "<replace_external_user_id>": # Use actual placeholder
        current_app.logger.critical("[ChatAgent] CRITICAL_CONFIG_ERROR: API Key or User ID not configured.")
        return jsonify({"answer": "Sorry, the chat service is not configured correctly on my end."}), 503 # Match OldChat.py user message

    if not request.is_json:
        return jsonify({"answer": "Please send your question in the correct format."}), 400
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict) or 'query' not in data:
        return jsonify({"answer": "Please tell me what your question is."}), 400

    user_query = data.get('query')
    if not isinstance(user_query, str) or not user_query.strip():
        return jsonify({"answer": "Your question seems to be empty. Please try again."}), 400

    current_app.logger.info(f"[ChatAgent] User query: '{user_query[:100]}...'")

    session_id = create_chat_session(ON_DEMAND_API_KEY, ON_DEMAND_EXTERNAL_USER_ID)
    if not session_id:
        current_app.logger.error(f"[ChatAgent] Failed to create chat session.")
        return jsonify({"answer": "Sorry, I couldn't start a new chat session right now."}), 503

    current_app.logger.info(f"[ChatAgent] Session created: {session_id}. Submitting query...")
    # submit_query now returns the full JSON dictionary from on-demand.io or None
    raw_response_data = submit_query(ON_DEMAND_API_KEY, session_id, user_query)

    if raw_response_data and isinstance(raw_response_data, dict):
        current_app.logger.info(f"[ChatAgent] Raw response from submit_query: {json.dumps(raw_response_data)[:1000]}...")
        
        extracted_answer = None
        # Defensive extraction, trying multiple common paths like in OldChat.py
        data_content = raw_response_data.get("data")
        if isinstance(data_content, dict):
            # Path 1: data.answer (seen in your logs)
            extracted_answer = data_content.get("answer")
            if isinstance(extracted_answer, str):
                current_app.logger.info(f"[ChatAgent] Extracted answer from 'data.answer'.")
            else: # If data.answer is not a string or is None, try other paths
                extracted_answer = None # Reset if not a string
                query_result = data_content.get("queryResult")
                if isinstance(query_result, dict):
                    # Path 2: data.queryResult.text (original attempt)
                    extracted_answer = query_result.get("text")
                    if isinstance(extracted_answer, str):
                        current_app.logger.info(f"[ChatAgent] Extracted answer from 'data.queryResult.text'.")
                    else:
                        extracted_answer = None # Reset
                        # Path 3: data.queryResult.fulfillment.answer (from OldChat.py)
                        fulfillment = query_result.get("fulfillment")
                        if isinstance(fulfillment, dict):
                            extracted_answer = fulfillment.get("answer")
                            if isinstance(extracted_answer, str):
                                current_app.logger.info(f"[ChatAgent] Extracted answer from 'data.queryResult.fulfillment.answer'.")
                            else:
                                extracted_answer = None # Reset
                                # Path 4: data.queryResult.fulfillment.text (from OldChat.py)
                                extracted_answer = fulfillment.get("text")
                                if isinstance(extracted_answer, str):
                                     current_app.logger.info(f"[ChatAgent] Extracted answer from 'data.queryResult.fulfillment.text'.")
                                else:
                                    extracted_answer = None # Reset


        # Fallback to top-level keys if still no answer (less likely based on your logged structure)
        if extracted_answer is None and isinstance(raw_response_data, dict):
            extracted_answer = raw_response_data.get("answer") # Path 5: top-level answer
            if isinstance(extracted_answer, str):
                current_app.logger.info(f"[ChatAgent] Extracted answer from top-level 'answer'.")
            else:
                extracted_answer = None # Reset
                extracted_answer = raw_response_data.get("text") # Path 6: top-level text
                if isinstance(extracted_answer, str):
                    current_app.logger.info(f"[ChatAgent] Extracted answer from top-level 'text'.")
                else:
                    extracted_answer = None # Reset

        if extracted_answer is not None: # This means a string (even empty) was found
            cleaned_reply = extracted_answer.strip()
            current_app.logger.info(f"[ChatAgent] Final extracted reply: '{cleaned_reply[:100]}...'")
            return jsonify({"reply": cleaned_reply}) # Using "reply" key like Current Chat.py
        else:
            current_app.logger.warning(f"[ChatAgent] Could not extract a definitive text answer from any known path. Full response logged above.")
            # Return a structured error, not the full JSON to the client
            return jsonify({"error": "Chat Agent: The agent service responded, but I could not understand its answer format."}), 502

    elif isinstance(raw_response_data, str): # submit_query itself returned an error string
        current_app.logger.error(f"[ChatAgent] submit_query returned an error string: {raw_response_data}")
        return jsonify({"answer": raw_response_data}), 502 # Pass error string from submit_query
    else: # submit_query returned None or unexpected type
        current_app.logger.error(f"[ChatAgent] submit_query returned None or unexpected data type. Session: {session_id}")
        return jsonify({"answer": "Sorry, I failed to get a response from the chat service."}), 502 # Match OldChat.py user message


@chat_bp.route("/health", methods=["GET"])
# @swag_from(...)
def health_check():
    current_app.logger.info("[ChatAgent] /chat_agent/health endpoint HIT.") # Path consistent with blueprint
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>":
         current_app.logger.warning("[ChatAgent] Health check warning: ON_DEMAND_API_KEY not configured.")
    return jsonify({"status": "healthy", "module": "chat_agent"}), 200
