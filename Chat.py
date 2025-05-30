import os
import requests
import json
from flask import Blueprint, request, jsonify, current_app
from dotenv import load_dotenv
from base64 import b64encode

# Load environment variables
load_dotenv()

ON_DEMAND_API_KEY = os.environ.get("ON_DEMAND_API_KEY")
ON_DEMAND_EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")
DID_API_KEY = os.environ.get("DID_API_KEY")  # Add this to your .env
DID_AVATAR_URL = os.environ.get("DID_AVATAR_URL", "https://create-images-results.d-id.com/DefaultAvatarImage.png")

chat_bp = Blueprint('chat_agent', __name__, url_prefix='/chat_agent')
BASE_URL = "https://api.on-demand.io/chat/v1"

def _create_chat_session_internal():
    url = f"{BASE_URL}/sessions"
    headers = {"apikey": ON_DEMAND_API_KEY}
    body = {"agentIds": [], "externalUserId": ON_DEMAND_EXTERNAL_USER_ID}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        if response.status_code == 201:
            return response.json().get("data", {}).get("id")
        return None
    except Exception as e:
        current_app.logger.error(f"Session creation failed: {e}")
        return None

def _submit_query_internal(session_id, query_text):
    url = f"{BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": ON_DEMAND_API_KEY}
    agent_ids = ["agent-1712327325", "agent-1713962163", "agent-1747649298", "agent-1746427905", "agent-1747298877"]

    body = {
        "endpointId": "predefined-openai-gpt4.1",
        "query": query_text,
        "agentIds": agent_ids,
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
        if response.status_code == 200:
            data = response.json().get("data", {})
            for key in ["answer", "queryResult.text", "queryResult.fulfillment.answer", "queryResult.fulfillment.text"]:
                parts = key.split(".")
                val = data
                for part in parts:
                    val = val.get(part) if isinstance(val, dict) else None
                if isinstance(val, str): return val.strip()
            return json.dumps(response.json())
        else:
            return f"Error from chat service: Status {response.status_code}"
    except Exception as e:
        current_app.logger.error(f"Query submission failed: {e}")
        return "Sorry, I couldn't connect to the chat service."

def _send_to_did(text):
    try:
        auth = b64encode(f"{DID_API_KEY}:".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        }
        body = {
            "script": {
                "type": "text",
                "input": text,
                "provider": {
                    "type": "microsoft",
                    "voice_id": "en-US-JennyNeural"
                }
            },
            "source_url": DID_AVATAR_URL
        }
        response = requests.post("https://api.d-id.com/talks", headers=headers, json=body)
        if response.status_code == 200:
            return response.json().get("result_url")
        else:
            current_app.logger.error(f"D-ID Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        current_app.logger.error(f"Error sending to D-ID: {e}")
        return None

@chat_bp.route('/chat', methods=['POST'])
def chat_endpoint():
    if not request.is_json:
        return jsonify({"error": "Expected JSON request"}), 400

    data = request.get_json()
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing or empty query"}), 400

    session_id = _create_chat_session_internal()
    if not session_id:
        return jsonify({"error": "Failed to start chat session"}), 500

    text_response = _submit_query_internal(session_id, query)
    if text_response.startswith("Sorry") or text_response.startswith("Error"):
        return jsonify({"answer": text_response}), 500

    video_url = _send_to_did(text_response)
    if not video_url:
        return jsonify({"answer": "Failed to generate video avatar"}), 502

    return jsonify({
        "answer": text_response,
        "video_url": video_url
    })

@chat_bp.route('/health', methods=['GET'])
def health_check_chat_agent():
    return jsonify({
        "status": "healthy" if ON_DEMAND_API_KEY and DID_API_KEY else "unhealthy",
        "chat_api": "configured" if ON_DEMAND_API_KEY else "missing",
        "did_api": "configured" if DID_API_KEY else "missing"
    }), 200
