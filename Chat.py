# Chat.py
import os
import requests
import json
from flask import Blueprint, request, jsonify, current_app
from flasgger import swag_from
from dotenv import load_dotenv

# Load .env file for local development (primarily for API keys if not set in environment)
load_dotenv()

# --- Configuration for the Chat Agent ---
ON_DEMAND_API_KEY = os.environ.get("ON_DEMAND_API_KEY")
ON_DEMAND_EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")
BASE_URL = "https://api.on-demand.io/chat/v1"

# --- Create a Blueprint for the chat agent ---
# All routes defined in this blueprint will be prefixed with /chat_agent
chat_bp = Blueprint('chat_agent', __name__, url_prefix='/chat_agent')


# --- Helper Functions ---

def create_chat_session(api_key, external_user_id):
    """
    Creates a new chat session with the on-demand.io service.
    Returns session_id on success, None on failure.
    """
    url = f"{BASE_URL}/sessions"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    body = {"agentIds": [], "externalUserId": external_user_id} # Assuming agentIds can be empty for session creation

    current_app.logger.info(f"[ChatAgent] create_chat_session: Attempting to create session. URL: {url}")
    # current_app.logger.debug(f"[ChatAgent] create_chat_session: Headers: {headers}, Body: {json.dumps(body)}")

    try:
        response = requests.post(url, headers=headers, json=body, timeout=15) # Added timeout
        current_app.logger.info(f"[ChatAgent] create_chat_session: Response status: {response.status_code}")
        if response.status_code != 201: # Usually 201 Created for new sessions
             current_app.logger.error(f"[ChatAgent] create_chat_session: Failed. Status: {response.status_code}, Response: {response.text[:500]}")
        response.raise_for_status()  # Will raise HTTPError for 4xx/5xx responses

        response_data = response.json()
        current_app.logger.debug(f"[ChatAgent] create_chat_session: Response data: {response_data}")
        session_id = response_data.get("data", {}).get("id")

        if session_id:
            current_app.logger.info(f"[ChatAgent] create_chat_session: Session created successfully. Session ID: {session_id}")
            return session_id
        else:
            current_app.logger.error(f"[ChatAgent] create_chat_session: 'data.id' (session_id) not found in response. Full response: {response_data}")
            return None
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[ChatAgent] create_chat_session: HTTPError. Status: {e.response.status_code if e.response else 'N/A'}, Response: {e.response.text[:500] if e.response else 'No response text'}")
    except requests.exceptions.RequestException as e: # Catches ConnectionError, Timeout, etc.
        current_app.logger.error(f"[ChatAgent] create_chat_session: RequestException. Error: {str(e)}")
    except json.JSONDecodeError as e:
        current_app.logger.error(f"[ChatAgent] create_chat_session: JSONDecodeError. Failed to parse response. Error: {str(e)}. Response text: {response.text[:500] if 'response' in locals() and hasattr(response, 'text') else 'N/A'}")
    except Exception as e:
        current_app.logger.error(f"[ChatAgent] create_chat_session: Unexpected error. Error: {str(e)}")
    return None


def submit_query(api_key, session_id, query_text, response_mode="sync"):
    """
    Submits a query to an existing chat session.
    Returns the JSON response data from the agent on success, None on failure.
    """
    url = f"{BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    
    # Define agent IDs - these seem specific to your setup
    agent_ids_list = ["agent-1712327325", "agent-1713962163", "agent-1747649298"]
    stop_sequences_list = [] # Define if needed

    body = {
        "endpointId": "predefined-openai-gpt4.1", # Or your specific agent endpoint
        "query": query_text,
        "agentIds": agent_ids_list,
        "responseMode": response_mode,
        "reasoningMode": "low", # Or your desired mode
        "modelConfigs": {
            "fulfillmentPrompt": """Provide only the direct answer to the user's query. Do not include any metadata, token counts, or conversational filler. Be concise and to the point.""", # Key for clean output
            "stopSequences": stop_sequences_list,
            "temperature": 0.7,
            "topP": 1,
            "maxTokens": 4000, # Max tokens the model can generate for the reply
            "presencePenalty": 0,
            "frequencyPenalty": 0
        },
    }

    current_app.logger.info(f"[ChatAgent] submit_query: Attempting to submit query to session {session_id}. URL: {url}")
    # current_app.logger.debug(f"[ChatAgent] submit_query: Headers: {headers}, Body: {json.dumps(body)}")

    try:
        if response_mode == "sync":
            response = requests.post(url, headers=headers, json=body, timeout=30) # Added timeout
            current_app.logger.info(f"[ChatAgent] submit_query: Response status: {response.status_code}")
            if response.status_code != 200:
                 current_app.logger.error(f"[ChatAgent] submit_query: Failed. Status: {response.status_code}, Response: {response.text[:500]}")
            response.raise_for_status() # Will raise HTTPError for 4xx/5xx responses

            response_data = response.json()
            current_app.logger.info("[ChatAgent] submit_query: Sync query submitted and response received successfully.")
            current_app.logger.debug(f"[ChatAgent] submit_query: Response data: {json.dumps(response_data)[:500]}...")
            return response_data
        else:
            current_app.logger.warning(f"[ChatAgent] submit_query: Unsupported responseMode '{response_mode}'. Only 'sync' is currently handled for clean output.")
            return None # Or handle streaming differently if needed later
            
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"[ChatAgent] submit_query: HTTPError. Session: {session_id}. Status: {e.response.status_code if e.response else 'N/A'}, Response: {e.response.text[:500] if e.response else 'No response text'}")
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"[ChatAgent] submit_query: RequestException. Session: {session_id}. Error: {str(e)}")
    except json.JSONDecodeError as e:
        current_app.logger.error(f"[ChatAgent] submit_query: JSONDecodeError. Session: {session_id}. Failed to parse response. Error: {str(e)}. Response text: {response.text[:500] if 'response' in locals() and hasattr(response, 'text') else 'N/A'}")
    except Exception as e:
        current_app.logger.error(f"[ChatAgent] submit_query: Unexpected error. Session: {session_id}. Error: {str(e)}")
    return None


# --- Blueprint Routes ---

@chat_bp.route('/chat', methods=['POST'])
@swag_from({ # Corresponds to your OpenAPI schema's ChatQueryRequest/Response
    'tags': ['Chat Agent'],
    'summary': 'Send Query to Chat Agent',
    'description': 'Submits a query to the chat agent and attempts to return only the direct textual reply.',
    'requestBody': {
        'required': True,
        'content': {
            'application/json': {
                'schema': {'$ref': '#/components/schemas/ChatQueryRequest'}
            }
        }
    },
    'responses': {
        '200': {
            'description': 'Successful reply from the chat agent.',
            'content': { 'application/json': { 'schema': {'$ref': '#/components/schemas/ChatQueryResponse'} } }
        },
        '400': {
            'description': 'Bad Request (e.g., missing query, invalid JSON).',
            'content': { 'application/json': { 'schema': {'$ref': '#/components/schemas/ErrorResponse'} } }
        },
        '500': {
            'description': 'Internal Server Error (unexpected error within this service).',
            'content': { 'application/json': { 'schema': {'$ref': '#/components/schemas/ErrorResponse'} } }
        },
        '502': {
            'description': 'Bad Gateway (error communicating with or getting valid response from the upstream agent service).',
            'content': { 'application/json': { 'schema': {'$ref': '#/components/schemas/ErrorResponse'} } }
        },
        '503': {
            'description': 'Service Unavailable (could indicate upstream agent service is down or API keys misconfigured).',
            'content': { 'application/json': { 'schema': {'$ref': '#/components/schemas/ErrorResponse'} } }
        }
    }
})
def chat_endpoint():
    current_app.logger.info(f"--- [ChatAgent] /chat_agent/chat endpoint HIT. Request ID: {request.headers.get('X-Request-ID', 'N/A')} ---")
    
    # --- API Key and User ID Configuration Check ---
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>": # Check for placeholder
        current_app.logger.critical("[ChatAgent] CRITICAL_CONFIG_ERROR: ON_DEMAND_API_KEY is not configured or is a placeholder.")
        return jsonify({"error": "Chat Agent service is misconfigured (API key). Please contact support."}), 503
    if not ON_DEMAND_EXTERNAL_USER_ID or ON_DEMAND_EXTERNAL_USER_ID == "<replace_external_user_id>": # Check for placeholder
        current_app.logger.critical("[ChatAgent] CRITICAL_CONFIG_ERROR: ON_DEMAND_EXTERNAL_USER_ID is not configured or is a placeholder.")
        return jsonify({"error": "Chat Agent service is misconfigured (User ID). Please contact support."}), 503

    # --- Request Body Validation ---
    if not request.is_json:
        current_app.logger.warning("[ChatAgent] Request content type is not application/json.")
        return jsonify({"error": "Invalid request: Content-Type must be application/json."}), 400
        
    data = request.get_json(silent=True) # silent=True to prevent raising an exception if not JSON, we check 'not data' next
    if not data:
        current_app.logger.warning("[ChatAgent] Request received with invalid or empty JSON body.")
        return jsonify({"error": "Invalid request: Malformed or empty JSON body."}), 400
    
    user_query = data.get('query') # Use .get() for safer access
    if not user_query or not isinstance(user_query, str) or not user_query.strip():
        current_app.logger.warning(f"[ChatAgent] Request received without 'query', 'query' is not a string, or 'query' is empty/whitespace. Data: {data}")
        return jsonify({"error": "Missing 'query' in request body, or query is empty/invalid."}), 400

    current_app.logger.info(f"[ChatAgent] Validated query: '{user_query[:100]}...'") # Log a snippet

    # --- Create Chat Session ---
    session_id = create_chat_session(ON_DEMAND_API_KEY, ON_DEMAND_EXTERNAL_USER_ID)
    if not session_id:
        current_app.logger.error("[ChatAgent] Failed to create chat session (session_id is None). Upstream service might be unavailable or misconfigured.")
        return jsonify({"error": "Chat Agent: Failed to establish a session with the agent service. Please try again later."}), 502

    current_app.logger.info(f"[ChatAgent] Session created: {session_id}. Submitting query...")

    # --- Submit Query to Agent ---
    sync_response_data = submit_query(ON_DEMAND_API_KEY, session_id, user_query, response_mode="sync")

    if sync_response_data:
        current_app.logger.info(f"[ChatAgent] Raw response from submit_query for session {session_id}: {json.dumps(sync_response_data)[:500]}...") # Log first 500 chars
        try:
            # Attempt to extract the specific text response
            # Path: data -> queryResult -> text
            response_text = sync_response_data.get("data", {}).get("queryResult", {}).get("text")

            if response_text and isinstance(response_text, str):
                cleaned_reply = response_text.strip()
                current_app.logger.info(f"[ChatAgent] Successfully extracted reply for session {session_id}: '{cleaned_reply[:100]}...'")
                return jsonify({"reply": cleaned_reply}) # This is the desired clean output
            else:
                current_app.logger.warning(f"[ChatAgent] Could not extract 'data.queryResult.text' as a non-empty string from agent response for session {session_id}. 'response_text' is: '{response_text}'. Full response logged above.")
                return jsonify({"error": "Chat Agent: Received an unexpected or incomplete response structure from the agent service."}), 502
        except Exception as e: # Catch any unexpected error during the extraction process
            current_app.logger.error(f"[ChatAgent] Exception while parsing agent response for session {session_id}: {str(e)}. Full response logged above.")
            return jsonify({"error": "Chat Agent: Error processing the response from the agent service.", "details": str(e)}), 500
    else:
        # submit_query returned None, meaning an error occurred within submit_query (e.g., HTTPError from the API)
        current_app.logger.error("[ChatAgent] Failed to get any response from submit_query (it returned None) for session {session_id}. This usually indicates an API call failure to the agent service.")
        return jsonify({"error": "Chat Agent: Failed to communicate with the underlying agent service. Please try again later."}), 502


@chat_bp.route("/health", methods=["GET"])
@swag_from({ # From your OpenAPI schema
    'tags': ['Chat Agent', 'Utility'],
    'summary': 'Chat Agent Module Health Check',
    'description': 'Verifies if the Chat Agent module is running.',
    'operationId': 'getChatAgentHealth',
    'responses': {
        '200': {
            'description': 'Chat Agent module is healthy.',
            'content': {
                'application/json': {
                    'schema': {'$ref': '#/components/schemas/GeneralHealthCheckResponse'}
                }
            }
        }
    }
})
def health_check():
    current_app.logger.info("[ChatAgent] /chat_agent/health endpoint HIT.")
    # A more robust health check might try to see if ON_DEMAND_API_KEY is set
    if not ON_DEMAND_API_KEY or ON_DEMAND_API_KEY == "<replace_api_key>":
         current_app.logger.warning("[ChatAgent] Health check warning: ON_DEMAND_API_KEY is not configured or is a placeholder.")
         # Still return healthy if the service itself is up, but log a warning.
         # Or, you could return unhealthy if config is critical for basic operation.
    return jsonify({"status": "healthy", "module": "chat_agent"}), 200
