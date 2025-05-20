# 1. Base Image: Use an official Python runtime as a parent image.
FROM python:3.9-slim

# 2. Set Environment Variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080 

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
EXPOSE ${PORT} 
# 8. Run the application using Gunicorn with environment variable expansion
# Assuming your Flask app instance is named 'app' inside 'api_server.py'
CMD gunicorn --workers 4 --bind 0.0.0.0:${PORT} Chat:app
