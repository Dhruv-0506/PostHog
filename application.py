# application.py
import os
import logging
from flask import Flask, jsonify
from flasgger import Swagger
from dotenv import load_dotenv

# Import your blueprints
from Chat import chat_bp # Assuming Chat.py is in the same directory
from main import posthog_bp # Assuming main.py is in the same directory

# Load .env file for local development (will load ALL env vars from .env)
load_dotenv()

# Create the main Flask application instance
app = Flask(__name__)

# Configure logging for the main app
# Gunicorn will likely use its own logging config in production, but this helps for local.
if __name__ == '__main__': # Local "python application.py" run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s [%(module)s:%(lineno)d] %(message)s')
else: # When run by Gunicorn, it usually sets up its own handlers
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    # If blueprints use their own loggers, you might need to configure them too or ensure they propagate to root.
    # Using current_app.logger within blueprints should make them use this app's logger.

# Initialize Flasgger (Swagger) for the combined application
# It will pick up routes from registered blueprints
swagger_config = Swagger.DEFAULT_CONFIG
swagger_config['specs_route'] = "/apidocs/" # URL for Swagger UI
swagger = Swagger(app, config=swagger_config)

# Register the blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(posthog_bp)

# Optional: A root health check for the combined application
@app.route("/", methods=["GET"])
def combined_health_check():
    app.logger.info("Root health check for combined application HIT.")
    return jsonify({
        "status": "healthy",
        "message": "Combined API is running.",
        "services": {
            "chat_agent": {"health_url": "/chat_agent/health", "docs_prefix": "/chat_agent"},
            "posthog_analytics": {"health_url": "/analytics/health", "docs_prefix": "/analytics"}
        },
        "api_documentation": "/apidocs/"
    }), 200

if __name__ == "__main__":
    # This block is for local development only using "python application.py"
    # Ensure ALL necessary environment variables are set (e.g., in .env or exported)
    app.logger.info("Attempting to start application locally...")
    
    missing_vars = []
    if not os.environ.get("ON_DEMAND_API_KEY"): missing_vars.append("ON_DEMAND_API_KEY")
    if not os.environ.get("ON_DEMAND_EXTERNAL_USER_ID"): missing_vars.append("ON_DEMAND_EXTERNAL_USER_ID")
    if not os.environ.get("POSTHOG_API_KEY"): missing_vars.append("POSTHOG_API_KEY")

    if missing_vars:
        app.logger.error(f"CRITICAL: Missing environment variables for local run: {', '.join(missing_vars)}")
        app.logger.error("Please ensure they are set in your .env file or system environment.")
        exit(1)
    else:
        app.logger.info("All required API keys seem to be present in environment for local run.")

    local_port = int(os.environ.get("LOCAL_DEV_PORT", 8081)) # Use a different port for local dev
    app.logger.info(f"Starting Flask development server on http://0.0.0.0:{local_port}")
    app.run(host="0.0.0.0", port=local_port, debug=True)
