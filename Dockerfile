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

# 7. Expose the port the app runs on
EXPOSE 8080

# 8. Run the application using Gunicorn with environment variable expansion
CMD gunicorn --bind 0.0.0.0:${PORT} main:app
