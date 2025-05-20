import requests
import json
import os
from flask import Flask, request, jsonify
from flasgger import Swagger, swag_from # For API documentation
from dotenv import load_dotenv # For local .env file loading
import logging

# Load environment variables from .env file if it exists (for local development)
# In production, environment variables should be set directly by the deployment platform.
load_dotenv()

# --- Configuration ---
API_KEY = os.environ.get("ON_DEMAND_API_KEY")
EXTERNAL_USER_ID = os.environ.get("ON_DEMAND_EXTERNAL_USER_ID")
BASE_URL = "https://api.on-demand.io/chat/v1"

# Initialize Flask App
app = Flask(__name__)
swagger = Swagger(app) # Initialize Flasgger

# Configure logging
if __name__ != '__main__': # When run by Gunicorn
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
else: # For local development (python api_server.py)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Chat Agent Logic (from your original script) ---
# If these are in other modules, import them: from your_module import ...

def create_chat_session(api_key, external_user_id):
    url = f"{BASE_URL}/sessions"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    body = {"agentIds": [], "externalUserId": external_user_id}
    app.logger.info(f"Attempting to create session at URL: {url}")
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        response_data = response.json()
        session_id = response_data.get("data", {}).get("id")
        if session_id:
            app.logger.info(f"Chat session created. Session ID: {session_id}")
            return session_id
        else:
            app.logger.error(f"Error: 'data.id' not found in response. Full response: {response_data}")
            return None
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"HTTP error creating chat session: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request failed during session creation: {e}")
        return None
    except json.JSONDecodeError as e:
        responseText = response.text if 'response' in locals() and hasattr(response, 'text') else "N/A"
        app.logger.error(f"Failed to decode JSON response during session creation: {e}. Response text: {responseText}")
        return None

def submit_query(api_key, session_id, query_text, response_mode="sync"):
    url = f"{BASE_URL}/sessions/{session_id}/query"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    agent_ids_list = ["agent-1712327325", "agent-1713962163", "agent-1747649298"]
    stop_sequences_list = []

    body = {
        "endpointId": "predefined-openai-gpt4.1",
        "query": query_text,
        "agentIds": agent_ids_list,
        "responseMode": response_mode,
        "reasoningMode": "low",
        "modelConfigs": {
            "fulfillmentPrompt": "",
            "stopSequences": stop_sequences_list,
            "temperature": 0.7,
            "topP": 1,
            "maxTokens": 4000,
            "presencePenalty": 0,
            "frequencyPenalty": 0
        },
    }
    app.logger.info(f"Attempting to submit query to URL: {url}")
    try:
        if response_mode == "sync":
            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            app.logger.info("Sync query submitted successfully.")
            return response.json()
        else:
            app.logger.error(f"Unsupported responseMode for Siri integration: {response_mode}")
            return None
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"HTTP error submitting sync query: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request failed during query submission: {e}")
        return None
    except json.JSONDecodeError as e:
        responseText = response.text if 'response' in locals() and hasattr(response, 'text') else "N/A"
        app.logger.error(f"Failed to decode JSON response during sync query: {e}. Response text: {responseText}")
        return None

# --- Flask Endpoints ---

@app.route('/chat', methods=['POST'])
@swag_from({ # Basic Flasgger documentation
    'tags': ['Chat'],
    'summary': 'Send a query to the chat agent.',
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'The user query for the chat agent.',
                        'example': 'What is the capital of France?'
                    }
                },
                'required': ['query']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Successful response from the agent.',
            'schema': {
                'type': 'object',
                'properties': {
                    'reply': {
                        'type': 'string',
                        'description': 'The agent\'s textual reply.'
                    }
                }
            }
        },
        400: {'description': 'Bad Request - Missing query in request body.'},
        500: {'description': 'Internal Server Error - e.g., API key issues or agent communication failure.'}
    }
})
def chat_endpoint():
    if not API_KEY or API_KEY == "<replace_api_key>" or \
       not EXTERNAL_USER_ID or EXTERNAL_USER_ID == "<replace_external_user_id>":
        app.logger.error("API_KEY or EXTERNAL_USER_ID not configured properly on the server.")
        return jsonify({"error": "Server configuration error for API credentials."}), 500

    data = request.get_json()
    if not data or 'query' not in data:
        app.logger.warning("Request received without 'query' in JSON body.")
        return jsonify({"error": "Missing 'query' in request body"}), 400

    user_query = data['query']
    app.logger.info(f"Received query: {user_query}")

    session_id = create_chat_session(API_KEY, EXTERNAL_USER_ID)
    if not session_id:
        app.logger.error("Failed to create chat session with the provider.")
        return jsonify({"error": "Failed to create chat session with the provider"}), 500

    sync_response_data = submit_query(API_KEY, session_id, user_query, response_mode="sync")

    if sync_response_data:
        try:
            response_text = sync_response_data.get("data", {}).get("queryResult", {}).get("text")
            if response_text:
                app.logger.info(f"Successfully processed query. Response: {response_text}")
                return jsonify({"reply": response_text})
            else:
                app.logger.warning(f"Could not extract text from agent's response. Full response: {json.dumps(sync_response_data)}")
                return jsonify({"warning": "Could not extract specific reply text from agent", "full_agent_response": sync_response_data})
        except Exception as e:
            app.logger.error(f"Error parsing agent response: {e}. Full response: {json.dumps(sync_response_data)}")
            return jsonify({"error": "Error parsing agent response", "details": str(e), "full_agent_response": sync_response_data}), 500
    else:
        app.logger.error("Failed to get response from chat agent provider.")
        return jsonify({"error": "Failed to get response from chat agent provider"}), 500

@app.route('/', methods=['GET'])
@swag_from({ # Basic Flasgger documentation
    'tags': ['Health'],
    'summary': 'Health check for the API.',
    'responses': {
        200: {
            'description': 'API is healthy.',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'healthy'},
                    'message': {'type': 'string', 'example': 'Chatbot API endpoint is running.'}
                }
            }
        }
    }
})
def health_check():
    app.logger.info("Health check endpoint hit.")
    return jsonify({"status": "healthy", "message": "Chatbot API endpoint is running."}), 200

# The Flasgger UI will be available at /apidocs
# if __name__ == '__main__':
    # For local development, ensure you have a .env file with:
    # ON_DEMAND_API_KEY="your_actual_api_key"
    # ON_DEMAND_EXTERNAL_USER_ID="your_actual_user_id"
    # app.run(debug=True, host='0.0.0.0', port=5001)
