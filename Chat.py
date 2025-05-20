# Chat.py (Adapted from OldChat.py structure, for current PostHog agent)
import os
import requests
import json
from flask import Blueprint, request, jsonify, current_app # Using current_app for logger
from flasgger import swag_from # Assuming you want to keep Flasgger for future use
from dotenv import load_dotenv

# Load environment variables (e.g., from .env file for local dev)
load_dotenv()

# Configuration from environment variables
ON_DEMAND_API_KEY = os.environ.get("ON_DEMAND_API_KEY")
ON_DEMAND_EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")

# Using current_app.logger, but will effectively be used via current_app
# logger = logging.getLogger(__name__) # This line is not strictly needed if using current_app.logger

# Blueprint setup to match your current /chat_agent/chat structure
chat_bp = Blueprint('chat_agent', __name__, url_prefix='/chat_agent')

BASE_URL = "https://api.on-demand.io/chat/v1"

# --- Internal Helper Functions (Styled like OldChat.py) ---

def _create_chat_session_internal():
    """Internal helper to create a chat session with the On-Demand API."""
    url = f"{BASE_URL}/sessions"
    headers = {"apikey": ON_DEMAND_API_KEY}
    body = {"agentIds": [], "externalUserId": ON_DEMAND_EXTERNAL_USER_ID}
    
    try:
        # Using current_app.logger for Flask integration
        current_app.logger.info(f"[ChatAgent OCM] Attempting to create session at URL: {url}") # OCM = Old Chat Model
        current_app.logger.debug(f"[ChatAgent OCM] With headers containing API key (initial chars): {ON_DEMAND_API_KEY[:4] if ON_DEMAND_API_KEY else 'KEY_NOT_SET'}...")
        current_app.logger.debug(f"[ChatAgent OCM] With body: {json.dumps(body)}")
        
        response = requests.post(url, headers=headers, json=body, timeout=15) # Increased timeout slightly

        if response.status_code == 201:
            response_data = response.json()
            session_id = response_data.get("data", {}).get("id")
            if session_id:
                current_app.logger.info(f"[ChatAgent OCM] Chat session created. Session ID: {session_id}")
                return session_id
            else:
                current_app.logger.error(f"[ChatAgent OCM] Error - 'data.id' not found in session creation response. Full response: {response_data}")
                return None
        else:
            current_app.logger.error(f"[ChatAgent OCM] Error creating chat session: {response.status_code} - {response.text[:500]}")
            return None
    except requests.exceptions.Timeout:
        current_app.logger.error(f"[ChatAgent OCM] Request timed out during session creation.", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"[ChatAgent OCM] Request failed during session creation: {e}", exc_info=True)
        return None
    except json.JSONDecodeError as e:
        responseText = "N/A"
        if "response" in locals() and hasattr(response, "text"):
            responseText = response.text
        current_app.logger.error(f"[ChatAgent OCM] Failed to decode JSON response during session creation: {e}. Response text: {responseText[:500]}", exc_info=True)
        return None
    except Exception as e:
        current_app.logger.error(f"[ChatAgent OCM] Unexpected error during session creation: {e}", exc_info=True)
        return None


def _submit_query_internal(session_id, query_text):
    """
    Internal helper to submit a query in sync mode to the On-Demand API 
    and attempt to extract the primary answer text.
    (Logic styled after OldChat.py's _submit_query_internal)
    """
    url = f"{BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": ON_DEMAND_API_KEY}

    # ** KEY CHANGE: Use Agent IDs relevant to your CURRENT PostHog agent setup **
    agent_ids = ["agent-1712327325", "agent-1713962163", "agent-1747649298"]
    
    # Stop sequences (empty as per OldChat.py's likely implication)
    stop_sequences = []

    body = {
        "endpointId": "predefined-openai-gpt4.1", # As per your current setup
        "query": query_text,
        "agentIds": agent_ids, 
        "responseMode": "sync",
        "reasoningMode": "low",
        "modelConfigs": { # Using modelConfigs from OldChat.py example
            "fulfillmentPrompt": "", 
            "stopSequences": stop_sequences,
            "temperature": 0.7,
            "topP": 1,
            "maxTokens": 0, 
            "presencePenalty": 0,
            "frequencyPenalty": 0
        },
    }

    try:
        current_app.logger.info(f"[ChatAgent OCM] Attempting to submit sync query to URL: {url}")
        current_app.logger.debug(f"[ChatAgent OCM] With headers containing API key (initial chars): {ON_DEMAND_API_KEY[:4] if ON_DEMAND_API_KEY else 'KEY_NOT_SET'}...")
        current_app.logger.debug(f"[ChatAgent OCM] submit_query BODY: {json.dumps(body)}") # Log the exact body

        response = requests.post(url, headers=headers, json=body, timeout=60) 
        
        current_app.logger.info(f"[ChatAgent OCM] (submit_query) - OnDemand API Response Status: {response.status_code}")
        # Log more of the response text for debugging if not 200
        if response.status_code != 200:
            current_app.logger.warning(f"[ChatAgent OCM] (submit_query) - OnDemand API Non-200 Response Text: {response.text[:1000]}")
        else:
            current_app.logger.debug(f"[ChatAgent OCM] (submit_query) - OnDemand API Response Text (first 500 chars): {response.text[:500]}")


        if response.status_code == 200:
            current_app.logger.info("[ChatAgent OCM] Sync query submitted successfully to OnDemand API.")
            response_data = response.json() # This might fail if response is not JSON, even with 200 OK
            current_app.logger.info(f"[ChatAgent OCM] Full response from OnDemand for query: {json.dumps(response_data)[:1000]}...")
            
            # Defensive extraction logic from OldChat.py
            answer = None
            if isinstance(response_data, dict):
                data_content = response_data.get("data")
                if isinstance(data_content, dict):
                    # Path 1: data.answer (This was seen in your successful logs)
                    answer = data_content.get("answer")
                    if isinstance(answer, str): current_app.logger.info("[ChatAgent OCM] Extracted from data.answer")
                    else: answer = None # Reset if not string

                    # Path 2: data.queryResult.text (Original path in your failing Current Chat.py)
                    if answer is None:
                        query_result = data_content.get("queryResult")
                        if isinstance(query_result, dict):
                            answer = query_result.get("text")
                            if isinstance(answer, str): current_app.logger.info("[ChatAgent OCM] Extracted from data.queryResult.text")
                            else: answer = None

                    # Path 3 & 4 (from OldChat.py's deeper extraction)
                    if answer is None:
                        query_result = data_content.get("queryResult") # Re-get in case it wasn't fetched
                        if isinstance(query_result, dict):
                            fulfillment = query_result.get("fulfillment")
                            if isinstance(fulfillment, dict):
                                answer = fulfillment.get("answer")
                                if isinstance(answer, str): current_app.logger.info("[ChatAgent OCM] Extracted from data.queryResult.fulfillment.answer")
                                else: answer = None

                                if answer is None:
                                    answer = fulfillment.get("text")
                                    if isinstance(answer, str): current_app.logger.info("[ChatAgent OCM] Extracted from data.queryResult.fulfillment.text")
                                    else: answer = None
                
                # Path 5 & 6: Top-level keys (from OldChat.py)
                if answer is None:
                    answer = response_data.get("answer")
                    if isinstance(answer, str): current_app.logger.info("[ChatAgent OCM] Extracted from top-level 'answer'")
                    else: answer = None
                
                if answer is None:
                    answer = response_data.get("text")
                    if isinstance(answer, str): current_app.logger.info("[ChatAgent OCM] Extracted from top-level 'text'")
                    else: answer = None

            if answer is not None: # Found a string answer
                return str(answer).strip() # Ensure it's a string and strip whitespace
            else:
                current_app.logger.warning(f"[ChatAgent OCM] Could not extract a definitive 'answer' string from OnDemand API response using known paths. Full response was: {response_data}")
                # Fallback to returning the full JSON string, like OldChat.py did
                return json.dumps(response_data) 
        else:
            # Non-200 response from OnDemand API for the query
            current_app.logger.error(f"[ChatAgent OCM] Error submitting sync query to OnDemand API: {response.status_code} - {response.text[:500]}")
            return f"Error from chat service: Status {response.status_code}. Please check server logs for details."
            
    except requests.exceptions.Timeout:
        current_app.logger.error(f"[ChatAgent OCM] Request timed out during query submission to OnDemand API.", exc_info=True)
        return "Sorry, the chat service took too long to respond."
    except requests.exceptions.RequestException as e: # Covers ConnectionError, etc.
        current_app.logger.error(f"[ChatAgent OCM] Request failed during query submission to OnDemand API: {e}", exc_info=True)
        return "Sorry, I couldn't connect to the chat service."
    except json.JSONDecodeError as e: # If response.json() fails
        responseText = "N/A"
        if "response" in locals() and hasattr(response, "text"):
            responseText = response.text
        current_app.logger.error(f"[ChatAgent OCM] Failed to decode JSON response from OnDemand API: {e}. Response text: {responseText[:500]}", exc_info=True)
        return "Sorry, I received an unexpected response from the chat service (not JSON)."
    except Exception as e:
        current_app.logger.error(f"[ChatAgent OCM] An unexpected error occurred during query submission: {e}", exc_info=True)
        return "Sorry, an unexpected error occurred while I was trying to get an answer."


# Endpoint path changed to /chat (relative to /chat_agent prefix)
# In Chat.py

# ... (Keep create_chat_session and the LATEST _submit_query_internal I provided,
#      which has all the try-except blocks returning strings) ...

@chat_bp.route('/chat', methods=['POST'])
def chat_endpoint():
    current_app.logger.info(f"--- [ChatAgent OCM] {request.path} endpoint HIT ---")
    
    # ... (API key checks, request validation - keep as is) ...
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>" or \
       not ON_DEMAND_EXTERNAL_USER_ID or ON_DEMAND_EXTERNAL_USER_ID == "<replace_external_user_id>":
        current_app.logger.critical("[ChatAgent OCM] CRITICAL_CONFIG_ERROR: API Key or User ID not configured.")
        return jsonify({"answer": "Sorry, the chat service is not configured correctly on my end."}), 503

    if not request.is_json:
        current_app.logger.warning(f"[ChatAgent OCM] Request Content-Type is not application/json.")
        return jsonify({"answer": "Please send your question in the correct format (JSON)."}), 400
        
    data = request.get_json(silent=True) 
    if not data or not isinstance(data, dict) or 'query' not in data:
        current_app.logger.warning(f"[ChatAgent OCM] Missing 'query' or invalid JSON. Data: {data}")
        return jsonify({"answer": "Please tell me what your question is."}), 400

    user_query = data.get('query')
    if not isinstance(user_query, str) or not user_query.strip():
        current_app.logger.warning(f"[ChatAgent OCM] 'query' is empty or not a string. Query: '{user_query}'")
        return jsonify({"answer": "Your question seems to be empty. Please try again."}), 400

    current_app.logger.info(f"[ChatAgent OCM] User query: '{user_query[:100]}...'")

    session_id = _create_chat_session_internal()
    if not session_id:
        current_app.logger.error(f"[ChatAgent OCM] Failed to create chat session.")
        return jsonify({"answer": "Sorry, I couldn't start a new chat session right now."}), 503

    current_app.logger.info(f"[ChatAgent OCM] Session created: {session_id}. Submitting query...")
    
    # _submit_query_internal is now expected to ALWAYS return a string.
    # This string is either the extracted answer, a JSON dump, or an error message.
    answer_string = _submit_query_internal(session_id, user_query)

    # Check if _submit_query_internal itself had an issue and returned one of its error strings
    # or if it returned the JSON dump because it couldn't extract a clean answer.
    # We can log this for clarity. The main thing is that answer_string should be a string.

    if not isinstance(answer_string, str):
        # This case should ideally NOT be hit if _submit_query_internal is correctly returning strings from all paths.
        # This would indicate a bug in _submit_query_internal's return logic.
        current_app.logger.error(f"[ChatAgent OCM] CRITICAL BUG: _submit_query_internal did NOT return a string. Returned type: {type(answer_string)}, value: {str(answer_string)[:200]}. Session: {session_id}")
        return jsonify({"answer": "Sorry, an internal error occurred while processing your request (unexpected return type)."}), 500
    
    # Log what kind of string we got (is it JSON, or a simple answer, or an error message?)
    # This helps in debugging if the client gets unexpected content.
    if answer_string.startswith("Error from chat service:") or \
       answer_string.startswith("Sorry,"):
        current_app.logger.warning(f"[ChatAgent OCM] _submit_query_internal returned an error message: '{answer_string}'")
    elif answer_string.startswith("{") and answer_string.endswith("}"): # Crude check for JSON string
        current_app.logger.info(f"[ChatAgent OCM] _submit_query_internal returned full JSON response as string (length: {len(answer_string)}). Answer not specifically extracted.")
    else:
        current_app.logger.info(f"[ChatAgent OCM] _submit_query_internal returned extracted answer string (length: {len(answer_string)}).")

    # The client always gets the string from _submit_query_internal in the "answer" field.
    return jsonify({"answer": answer_string})

# ... (rest of Chat.py, including health_check, _create_chat_session_internal, and the LATEST _submit_query_internal)


# Test endpoint (similar to OldChat.py's /ping-ondemand-config)
@chat_bp.route('/health', methods=['GET']) # Renamed from ping-ondemand-config for consistency
# @swag_from(...)
def health_check_chat_agent(): # Renamed for clarity
    """ Health check for the Chat Agent module, including a basic API key check. """
    current_app.logger.info(f"ENDPOINT {chat_bp.url_prefix}/health: Request received.")
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>":
         return jsonify({
            "status": "unhealthy",
            "module": "chat_agent",
            "message": "OnDemand Chat API Key is NOT configured correctly (using placeholder or missing).",
            "api_key_status": "MISCONFIGURED",
            "external_user_id_status": "CONFIGURED" if ON_DEMAND_EXTERNAL_USER_ID and ON_DEMAND_EXTERNAL_USER_ID != "<replace_external_user_id>" else "MISCONFIGURED"
        }), 503 # Use 503 for configuration issues making service unavailable
    
    # Optional: A light ping to session creation could be added here if truly needed for health.
    # For now, checking key presence is sufficient for this basic health check.
    return jsonify({
        "status": "healthy",
        "module": "chat_agent",
        "message": "Chat Agent module is running and API Key appears to be configured.",
        "api_key_status": "CONFIGURED",
        "external_user_id_status": "CONFIGURED" if ON_DEMAND_EXTERNAL_USER_ID and ON_DEMAND_EXTERNAL_USER_ID != "<replace_external_user_id>" else "MISCONFIGURED"
    }), 200
