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

chat_bp = Blueprint('chat_agent', __name__, url_prefix='/chat_agent')

# --- Helper Functions (create_chat_session, submit_query) ---
# KEEP THE ROBUST VERSIONS of create_chat_session and submit_query from the last full code I sent.
# They have better logging and error handling. For brevity, I'll omit them here,
# but assume they are the improved versions.
def create_chat_session(api_key, external_user_id):
    # ... (robust version from previous full Chat.py) ...
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
    except Exception as e: # Catch-all for other request/JSON issues
        current_app.logger.error(f"[ChatAgent] create_chat_session: Exception. Error: {str(e)}")
    return None

def submit_query(api_key, session_id, query_text, response_mode="sync"):
    # ... (robust version from previous full Chat.py, including fulfillmentPrompt) ...
    url = f"{BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    agent_ids_list = ["agent-1712327325", "agent-1713962163", "agent-1747649298"]
    stop_sequences_list = []
    body = {
        "endpointId": "predefined-openai-gpt4.1", "query": query_text, "agentIds": agent_ids_list,
        "responseMode": response_mode, "reasoningMode": "low",
        "modelConfigs": {
            "fulfillmentPrompt": """Provide only the direct answer to the user's query. Do not include any metadata, token counts, or conversational filler. Be concise and to the point.""",
            "stopSequences": stop_sequences_list, "temperature": 0.7,
            "topP": 1, "maxTokens": 4000, "presencePenalty": 0, "frequencyPenalty": 0
        },
    }
    current_app.logger.info(f"[ChatAgent] submit_query: Attempting query for session {session_id}. URL: {url}")
    try:
        if response_mode == "sync":
            response = requests.post(url, headers=headers, json=body, timeout=30)
            current_app.logger.info(f"[ChatAgent] submit_query: Response status: {response.status_code}")
            if response.status_code != 200:
                 current_app.logger.error(f"[ChatAgent] submit_query: Failed. Status: {response.status_code}, Response: {response.text[:500]}")
            response.raise_for_status()
            response_data = response.json()
            current_app.logger.info("[ChatAgent] submit_query: Sync query success.")
            return response_data
        else:
            current_app.logger.warning(f"[ChatAgent] submit_query: Unsupported responseMode '{response_mode}'.")
            return None
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[ChatAgent] submit_query: HTTPError. Session: {session_id}. Status: {e.response.status_code if e.response else 'N/A'}, Response: {e.response.text[:500] if e.response else 'No response text'}")
    except Exception as e: # Catch-all for other request/JSON issues
        current_app.logger.error(f"[ChatAgent] submit_query: Exception. Session: {session_id}. Error: {str(e)}")
    return None

# --- Blueprint Routes ---
@chat_bp.route('/chat', methods=['POST'])
# @swag_from(...) # Your existing swag definition
def chat_endpoint():
    current_app.logger.info(f"--- [ChatAgent] /chat_agent/chat endpoint HIT ---")
    
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>" or \
       not ON_DEMAND_EXTERNAL_USER_ID or ON_DEMAND_EXTERNAL_USER_ID == "<replace_external_user_id>":
        current_app.logger.critical("[ChatAgent] CRITICAL_CONFIG_ERROR: API Key or User ID not configured.")
        return jsonify({"error": "Chat Agent service is misconfigured. Please contact support."}), 503

    if not request.is_json:
        return jsonify({"error": "Invalid request: Content-Type must be application/json."}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request: Malformed or empty JSON body."}), 400
    user_query = data.get('query')
    if not user_query or not isinstance(user_query, str) or not user_query.strip():
        return jsonify({"error": "Missing 'query' in request body, or query is empty/invalid."}), 400

    current_app.logger.info(f"[ChatAgent] Validated query: '{user_query[:100]}...'")

    session_id = create_chat_session(ON_DEMAND_API_KEY, ON_DEMAND_EXTERNAL_USER_ID)
    if not session_id:
        return jsonify({"error": "Chat Agent: Failed to establish a session with the agent service."}), 502

    current_app.logger.info(f"[ChatAgent] Session created: {session_id}. Submitting query...")
    sync_response_data = submit_query(ON_DEMAND_API_KEY, session_id, user_query, response_mode="sync")

    if sync_response_data:
        current_app.logger.info(f"[ChatAgent] Raw response from submit_query for session {session_id}: {json.dumps(sync_response_data)[:1000]}...") # Log more for debugging
        
        # --- MODIFIED/REVERTED EXTRACTION LOGIC ---
        try:
            # Attempt to get the text, even if it might be None or empty
            response_text = sync_response_data.get("data", {}).get("answer")

            if response_text is not None: # Check if response_text is not None
                # If it's a string (even an empty one), strip and return it.
                # If it's not a string but not None (e.g. a number by mistake from API), this will cause an error below.
                if isinstance(response_text, str):
                    cleaned_reply = response_text.strip()
                    current_app.logger.info(f"[ChatAgent] Extracted reply (might be empty): '{cleaned_reply[:100]}...'")
                    return jsonify({"reply": cleaned_reply}) # This will now return {"reply": ""} if agent sends empty string
                else:
                    # response_text is not None AND not a string. This is unexpected.
                    current_app.logger.warning(f"[ChatAgent] 'data.queryResult.text' was found but is not a string. Type: {type(response_text)}, Value: {response_text}. Full response logged above.")
                    return jsonify({"error": "Chat Agent: Received an unexpected data type for the agent's reply."}), 502
            else:
                # response_text is None (path data.queryResult.text did not exist or was explicitly null)
                # This was the branch that previously gave you the "unexpected or incomplete response structure" error.
                # Let's see if the "direct chatbot" works when this path is missing.
                # For now, we'll log and return an error. If the direct chatbot somehow works
                # even when this path is missing, it implies it's looking at other fields.
                current_app.logger.warning(f"[ChatAgent] Path 'data.queryResult.text' resulted in None. Full response logged above.")
                # This is where your specific error message came from.
                # If the previous code worked, it means it either didn't hit this 'else'
                # or it handled this 'None' case by perhaps returning an empty reply or similar.
                # For now, we keep the error if the designated text field is truly missing/None.
                return jsonify({"error": "Chat Agent: The agent service did not provide a text reply in the expected location."}), 502

        except AttributeError as e: # If response_text was None and we tried .strip() on it - though `isinstance` check prevents this
            current_app.logger.error(f"[ChatAgent] AttributeError while processing reply (likely tried to .strip() a None value): {str(e)}. 'response_text' was {response_text}. Full response logged above.")
            return jsonify({"error": "Chat Agent: Error processing the agent's reply content.", "details": str(e)}), 500
        except Exception as e:
            current_app.logger.error(f"[ChatAgent] General exception while parsing/handling agent response: {str(e)}. Full response logged above.")
            return jsonify({"error": "Chat Agent: Error processing the response from the agent service.", "details": str(e)}), 500
    else:
        current_app.logger.error(f"[ChatAgent] submit_query returned None for session {session_id}.")
        return jsonify({"error": "Chat Agent: Failed to communicate with the underlying agent service."}), 502

@chat_bp.route("/health", methods=["GET"])
# @swag_from(...)
def health_check():
    current_app.logger.info("[ChatAgent] /chat_agent/health endpoint HIT.")
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>":
         current_app.logger.warning("[ChatAgent] Health check warning: ON_DEMAND_API_KEY not configured.")
    return jsonify({"status": "healthy", "module": "chat_agent"}), 200
