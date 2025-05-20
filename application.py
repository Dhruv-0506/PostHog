# application.py
import os
import logging
from flask import Flask, jsonify, current_app # Added current_app
from flasgger import Swagger, swag_from
from dotenv import load_dotenv

# Import your blueprints
from Chat import chat_bp
from main import posthog_bp

load_dotenv()

app = Flask(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s [%(module)s:%(lineno)d] %(message)s')
else:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    if gunicorn_logger.handlers: # Check if handlers are already set by Gunicorn
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
    else: # Fallback if Gunicorn hasn't set up its logger yet (e.g. during import time)
        logging.basicConfig(level=logging.INFO)
        app.logger.info("Gunicorn logger not found, using basicConfig for app.logger.")


swagger_config = Swagger.DEFAULT_CONFIG
swagger_config['specs_route'] = "/apidocs/"
swagger_config['title'] = "Combined API (Chat & PostHog)"
swagger_config['description'] = "API for Chat Agent and PostHog Analytics"
swagger_config['version'] = "1.0.0"
# You can add more Swagger global configs here
# swagger_config['host'] = "serverless.on-demand.io" # If needed for Swagger UI
# swagger_config['basePath'] = "/apps/posthog"     # If needed for Swagger UI

swagger = Swagger(app, config=swagger_config)

# Register the blueprints
app.register_blueprint(chat_bp) # Will be available at /chat_agent/*
app.register_blueprint(posthog_bp) # Will be available at /analytics/*

# --- Root Level Routes ---

@app.route("/", methods=["GET"])
@swag_from({ # Basic Swagger docs for the root endpoint
    'tags': ['Application Health'],
    'summary': 'Root health check for the combined application.',
    'responses': {
        200: {
            'description': 'Application is healthy and running.',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'healthy'},
                    'message': {'type': 'string', 'example': 'Combined API is running.'},
                    'services': {
                        'type': 'object',
                        'properties': {
                            'chat_agent': {'type': 'object', 'properties': {'health_url': {'type': 'string'}}},
                            'posthog_analytics': {'type': 'object', 'properties': {'health_url': {'type': 'string'}}}
                        }
                    },
                    'api_documentation': {'type': 'string'}
                }
            }
        }
    }
})
def combined_health_check():
    app.logger.info("Root health check for combined application HIT.")
    return jsonify({
        "status": "healthy",
        "message": "Combined API is running.",
        "services": {
            "chat_agent": {"health_url": "/chat_agent/health", "base_prefix": "/chat_agent"},
            "posthog_analytics": {"health_url": "/analytics/health", "base_prefix": "/analytics", "legacy_health_url_for_agent": "/health"}
        },
        "api_documentation": "/apidocs/"
    }), 200

# NEW ROUTE: This will handle requests to https://serverless.on-demand.io/apps/posthog/health
@app.route("/health", methods=["GET"])
@swag_from({ # Swagger docs for this specific /health endpoint
    'tags': ['Application Health'],
    'summary': 'Specific health check for PostHog component, accessible at application root/health.',
    'description': 'This endpoint is maintained for compatibility with agents expecting the PostHog health check at this specific path.',
    'responses': {
        200: {
            'description': 'PostHog component is healthy.',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'healthy'},
                    'service_checked': {'type': 'string', 'example': 'posthog_integration'}
                }
            }
        },
        503: {
            'description': 'PostHog component is unhealthy (e.g., API key missing).',
             'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'unhealthy'},
                    'service_checked': {'type': 'string', 'example': 'posthog_integration'},
                    'reason': {'type': 'string'}
                }
            }
        }
    }
})
def legacy_posthog_health_check():
    """
    Provides a health check at the application's /health path,
    specifically to check the status of the PostHog integration.
    This is for compatibility with the agent-1747649298.
    """
    app.logger.info("Legacy PostHog health check at /health (application root) HIT.")
    
    # Perform the PostHog specific health check logic here
    # For example, check if the POSTHOG_API_KEY is available
    posthog_api_key = os.environ.get("POSTHOG_API_KEY")
    if not posthog_api_key:
        app.logger.warning("POSTHOG_API_KEY not found for /health check.")
        return jsonify({
            "status": "unhealthy",
            "service_checked": "posthog_integration",
            "reason": "POSTHOG_API_KEY environment variable is not set."
        }), 503 # Service Unavailable

    # You could add a more sophisticated check here, like trying a lightweight
    # API call to PostHog if necessary, but checking the key is a good start.
    # For now, if key exists, we assume basic config is okay.
    app.logger.info("POSTHOG_API_KEY found for /health check. Marking as healthy.")
    return jsonify({
        "status": "healthy",
        "service_checked": "posthog_integration"
    }), 200


if __name__ == "__main__":
    app.logger.info("Attempting to start application locally for development...")
    missing_vars = []
    if not os.environ.get("ON_DEMAND_API_KEY"): missing_vars.append("ON_DEMAND_API_KEY")
    if not os.environ.get("ON_DEMAND_EXTERNAL_USER_ID"): missing_vars.append("ON_DEMAND_EXTERNAL_USER_ID")
    if not os.environ.get("POSTHOG_API_KEY"): missing_vars.append("POSTHOG_API_KEY")

    if missing_vars:
        app.logger.error(f"CRITICAL: Missing environment variables for local run: {', '.join(missing_vars)}")
        exit(1)
    else:
        app.logger.info("All required API keys seem to be present in environment for local run.")

    local_port = int(os.environ.get("LOCAL_DEV_PORT", 8081))
    app.logger.info(f"Starting Flask development server on http://0.0.0.0:{local_port}")
    app.run(host="0.0.0.0", port=local_port, debug=True) # debug=True is fine for local dev
