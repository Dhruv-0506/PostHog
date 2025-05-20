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
COPY . .

# 7. Expose the port the app runs on (Gunicorn will bind to this port internally)
EXPOSE 8080 
# 8. Run the application using Gunicorn
# Gunicorn binds to 0.0.0.0:8080 inside the container.
# The deployment platform maps an external port to this internal 8080.
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8080", "application:app"]
