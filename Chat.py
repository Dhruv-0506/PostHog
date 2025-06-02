import os
import requests
import json
from flask import Blueprint, request, jsonify, current_app # Assuming current_app is available
from dotenv import load_dotenv
from base64 import b64encode
import logging # For standalone logging if current_app.logger is not available

# Load environment variables from .env file if present for other keys
load_dotenv()

# --- Configuration from Environment Variables (excluding D-ID API Key) ---
ON_DEMAND_API_KEY = os.environ.get("ON_DEMAND_API_KEY")
ON_DEMAND_EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")

# --- D-ID Specific Configuration (API Key hardcoded for testing) ---
# WARNING: Hardcoding API keys is a security risk. Remove before production or public exposure.
# The key you provided appears to be in the format 'email:password_or_token'.
# This entire string needs to be Base64 encoded for Basic Authentication.
DID_API_KEY_STRING = "ZGhydXZhZ2Fyd2FsMDYwNUBnbWFpbC5jb20:qvaz9tO8vCAPweDOWg1w9"

DID_SOURCE_IMAGE_URL = "https://t3.ftcdn.net/jpg/02/43/12/34/360_F_243123463_zTooub557xEWABDLk0jJklDyLSGl2jrr.jpg"
DID_WEBHOOK_URL = "https://serverless.on-demand.io/apps/posthog"
DID_VOICE_ID = "en-US-GuyNeural" # Microsoft male voice (ensure this is valid for your D-ID plan)
DID_API_BASE_URL = "https://api.d-id.com"

# --- On-Demand Platform Chat Configuration ---
CHAT_BASE_URL = "https://api.on-demand.io/chat/v1"
CHAT_AGENT_IDS = ["agent-1712327325", "agent-1713962163", "agent-1747649298", "agent-1746427905", "agent-1747298877"]
CHAT_ENDPOINT_ID = "predefined-openai-gpt4.1"

# --- Flask Blueprint Setup ---
chat_bp_did = Blueprint('chat_agent_with_did', __name__, url_prefix='/chat_agent_did')

# --- Logger Setup ---
def get_logger():
    try:
        return current_app.logger
    except RuntimeError:
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

# --- Helper Functions for On-Demand Chat Platform ---
def _create_chat_session_internal():
    logger = get_logger()
    if not ON_DEMAND_API_KEY:
        logger.error("On-Demand API Key is not configured.")
        return None
        
    url = f"{CHAT_BASE_URL}/sessions"
    headers = {"apikey": ON_DEMAND_API_KEY}
    body = {"agentIds": [], "externalUserId": ON_DEMAND_EXTERNAL_USER_ID}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        response.raise_for_status()
        return response.json().get("data", {}).get("id")
    except requests.exceptions.RequestException as e:
        logger.error(f"On-Demand session creation failed: {e}")
        return None

def _submit_query_internal(session_id, query_text):
    logger = get_logger()
    if not ON_DEMAND_API_KEY:
        logger.error("On-Demand API Key is not configured for query submission.")
        return "Error: Chat service API Key not configured."

    url = f"{CHAT_BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": ON_DEMAND_API_KEY}
    body = {
        "endpointId": CHAT_ENDPOINT_ID,
        "query": query_text,
        "agentIds": CHAT_AGENT_IDS,
        "responseMode": "sync",
        "reasoningMode": "low",
        "modelConfigs": {
            "fulfillmentPrompt": "",
            "stopSequences": [],
            "temperature": 0.7,
            "topP": 1,
            "maxTokens": 0,
            "presencePenalty": 0,
            "frequencyPenalty": 0
        },
    }
    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json().get("data", {})
        answer_paths = [
            "answer", "queryResult.text", "queryResult.fulfillment.answer", "queryResult.fulfillment.text"
        ]
        for key_path in answer_paths:
            parts = key_path.split(".")
            val = data
            try:
                for part in parts: val = val.get(part) if isinstance(val, dict) else None
                if isinstance(val, str) and val.strip(): return val.strip()
            except AttributeError: continue
        logger.warning(f"No specific answer text found in expected paths. Full response data: {data}")
        return json.dumps(data) if data else "No specific answer found in chat service response."
    except requests.exceptions.RequestException as e:
        logger.error(f"On-Demand query submission failed: {e}")
        return f"Error from chat service: {e}"
    except Exception as e:
        logger.error(f"Unexpected error during query submission: {e}")
        return "Sorry, an unexpected error occurred while processing your query."

# --- Helper Function for D-ID API ---
def _send_to_did_to_create_talk(text_input):
    logger = get_logger()
    if not DID_API_KEY_STRING: # Check if the hardcoded key string is present
        logger.error("D-ID API Key String is not configured in the code.")
        return None, "D-ID API Key missing. Video generation skipped."

    api_url = f"{DID_API_BASE_URL}/talks" # D-ID endpoint to create a talk. [4]
    
    # The DID_API_KEY_STRING is 'email:password' which needs to be Base64 encoded directly.
    encoded_auth = b64encode(DID_API_KEY_STRING.encode('utf-8')).decode('utf-8')

    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "script": {
            "type": "text",
            "input": text_input,
            "provider": {
                "type": "microsoft",
                "voice_id": DID_VOICE_ID
            }
        },
        "source_url": DID_SOURCE_IMAGE_URL,
        "webhook": DID_WEBHOOK_URL,
        "config": {
             "stitch": True
        }
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30) # Create a talk. [4]
        
        logger.info(f"D-ID API ('{api_url}') Response Status: {response.status_code}")
        logger.info(f"D-ID API Response Body: {response.text}")

        if response.status_code == 201: # 201 Created: Success for D-ID talk creation. [4]
            response_data = response.json()
            talk_id = response_data.get("id")
            if talk_id:
                return talk_id, None
            else:
                logger.error(f"D-ID talk creation succeeded (201) but no ID was returned. Response: {response.text}")
                return None, "D-ID talk creation succeeded but no ID was returned."
        else:
            error_message = f"D-ID API Error: Status {response.status_code} - {response.text}"
            logger.error(error_message)
            return None, error_message

    except requests.exceptions.Timeout:
        logger.error(f"D-ID API request timed out to {api_url}.")
        return None, "D-ID API request timed out."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to D-ID API ('{api_url}'): {e}")
        return None, f"D-ID API connection error: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during D-ID request: {e}")
        return None, f"Unexpected error with D-ID: {e}"

# --- Flask Routes ---
@chat_bp_did.route('/chat_with_avatar', methods=['POST'])
def chat_with_avatar_endpoint():
    logger = get_logger()
    if not request.is_json:
        logger.warning("Received non-JSON request to /chat_with_avatar")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    query_text = data.get("query", "").strip()

    if not query_text:
        logger.warning("Received empty query to /chat_with_avatar")
        return jsonify({"error": "Query parameter is missing or empty"}), 400

    session_id = _create_chat_session_internal()
    if not session_id:
        logger.error("Failed to create On-Demand chat session.")
        return jsonify({"error": "Failed to create chat session."}), 500

    text_response = _submit_query_internal(session_id, query_text)
    if text_response.startswith("Error:") or \
       text_response == "Sorry, an unexpected error occurred while processing your query.":
        logger.error(f"Failed to get valid response from chat service: {text_response}")
        return jsonify({"error": "Failed to get response from chat service.", "details": text_response}), 500
    
    if not text_response or text_response == "No specific answer found in chat service response.":
        logger.info("Chat service returned no specific or empty answer. Sending a default message to D-ID.")
        text_response = "I received your query, but there was no specific text content in the response to read out."


    talk_id, did_error = _send_to_did_to_create_talk(text_response)

    if did_error:
        logger.error(f"D-ID video initiation failed: {did_error}")
        return jsonify({
            "text_answer": text_response,
            "video_status": "failed_to_initiate",
            "d_id_error": did_error,
            "info": "Video generation could not be started. Text answer provided."
        }), 200 

    logger.info(f"Successfully initiated D-ID talk: {talk_id} for query: '{query_text}'")
    return jsonify({
        "text_answer": text_response,
        "d_id_talk_id": talk_id,
        "video_status": "processing",
        "info": f"Video generation initiated with D-ID. Talk ID: {talk_id}. "
                f"The final video URL will be sent to the webhook: {DID_WEBHOOK_URL}."
    }), 202

@chat_bp_did.route('/health', methods=['GET'])
def health_check_chat_agent_did_new():
    logger = get_logger()
    on_demand_ok = ON_DEMAND_API_KEY and ON_DEMAND_EXTERNAL_USER_ID
    # D-ID API key is now hardcoded, so we check DID_API_KEY_STRING
    did_ok = DID_API_KEY_STRING and DID_SOURCE_IMAGE_URL and DID_WEBHOOK_URL and DID_VOICE_ID
    
    status_report = {
        "overall_status": "healthy" if on_demand_ok and did_ok else "degraded",
        "dependencies": {
            "on_demand_chat_service": {
                "status": "configured" if on_demand_ok else "misconfigured",
                "api_key_set": bool(ON_DEMAND_API_KEY),
                "external_user_id_set": bool(ON_DEMAND_EXTERNAL_USER_ID)
            },
            "d_id_service": {
                "status": "configured" if did_ok else "misconfigured",
                "api_key_string_set": bool(DID_API_KEY_STRING), # Check the hardcoded variable
                "source_image_url_set": bool(DID_SOURCE_IMAGE_URL),
                "webhook_url_set": bool(DID_WEBHOOK_URL),
                "voice_id_set": bool(DID_VOICE_ID)
            }
        }
    }
    logger.info(f"Health check performed: {status_report['overall_status']}")
    return jsonify(status_report), 200 if on_demand_ok and did_ok else 503

# --- Main block for standalone testing (optional) ---
if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    
    app.logger.handlers.clear() 
    app.logger.addHandler(get_logger().handlers[0])
    app.logger.setLevel(logging.INFO)

    app.register_blueprint(chat_bp_did)

    print("--- Standalone Test Mode ---")
    if not ON_DEMAND_API_KEY or not ON_DEMAND_EXTERNAL_USER_ID:
        app.logger.error("CRITICAL: ON_DEMAND_API_KEY or ON_DEMAND_EXTERNAL_USER_ID are missing!")
        app.logger.error("Please set them as environment variables or in a .env file.")
    else:
        app.logger.info("On-Demand Chat API keys seem to be present.")
    
    if not DID_API_KEY_STRING:
        app.logger.error("CRITICAL: DID_API_KEY_STRING is not set in the code. This is unexpected.")
    else:
        app.logger.info(f"D-ID API Key String is hardcoded for testing: {DID_API_KEY_STRING[:10]}... (truncated for safety)")
        app.logger.info(f"D-ID Source Image: {DID_SOURCE_IMAGE_URL}")
        app.logger.info(f"D-ID Voice: {DID_VOICE_ID}")
        app.logger.info(f"D-ID Webhook: {DID_WEBHOOK_URL}")


    app.logger.info(f"Flask app running. Blueprint '{chat_bp_did.name}' registered at '{chat_bp_did.url_prefix}'.")
    app.logger.info(f"To test, send a POST request to http://127.0.0.1:5000{chat_bp_did.url_prefix}/chat_with_avatar")
    app.logger.info(f"Example: curl -X POST -H \"Content-Type: application/json\" -d '{{\"query\":\"Tell me a fun fact\"}}' http://127.0.0.1:5000{chat_bp_did.url_prefix}/chat_with_avatar")
    
    app.run(debug=False, port=5000)
