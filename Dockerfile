# 1. Base Image: Use an official Python runtime as a parent image.
FROM python:3.9-slim

# 2. Set Environment Variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080 # This is good, Gunicorn will use it.
# Add your API keys here IF AND ONLY IF you cannot set them at runtime in your deployment.
# It's much more secure to set them in the deployment environment.
# ENV ON_DEMAND_API_KEY="your_api_key_value"
# ENV ON_DEMAND_EXTERNAL_USER_ID="your_user_id_value"

# 3. Set working directory
WORKDIR /app

# 4. Copy dependencies file first to leverage Docker cache
COPY requirements.txt .

# 5. Install dependencies
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# 6. Copy the rest of the application code
# This will copy api_server.py, main.py (if it exists and is used), and other project files.
COPY . .

# 7. Expose the port the app runs on (matches the PORT ENV var)
EXPOSE ${PORT} # Using the variable here for consistency, though EXPOSE is static.
               # Docker tooling might not expand it, but it's clear. 8080 is fine too.

# 8. Run the application using Gunicorn with environment variable expansion
# Assuming your Flask app instance is named 'app' inside 'api_server.py'
CMD gunicorn --workers 4 --bind 0.0.0.0:${PORT} api_server:app
