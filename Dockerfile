# 1. Base Image: Use an official Python runtime as a parent image.
# Using python:3.9-slim as a good balance of features and size.
FROM python:3.9-slim

# 2. Set Environment Variables:
#    - PYTHONUNBUFFERED: Prevents Python output from being buffered, ensuring logs appear in real-time.
#    - PORT: The port your application will listen on inside the container. Gunicorn will use this.
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 3. Create and set the working directory in the container.
WORKDIR /app

# 4. Copy the dependencies file first to leverage Docker cache.
#    This layer will only be rebuilt if requirements.txt changes.
COPY requirements.txt .

# 5. Install Python dependencies.
#    --no-cache-dir: Reduces image size by not storing the pip cache.
#    --trusted-host pypi.python.org: Can help in environments with proxy/firewall issues for PyPI.
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# 6. Copy the rest of your application code into the working directory.
COPY . .

# 7. Expose the port the app runs on.
#    This informs Docker that the container listens on this port.
#    It doesn't actually publish the port to the host machine; that's done with `docker run -p`.
EXPOSE ${PORT}

# 8. Command to run the application using Gunicorn.
#    - "gunicorn": The WSGI server.
#    - "--bind 0.0.0.0:${PORT}": Bind to all available network interfaces on the port specified by the PORT env var.
#    - "main:app":
#        - "main": Refers to your Python file `main.py`.
#        - "app": Refers to the Flask application instance variable `app` (e.g., `app = Flask(__name__)`) within your `main.py`.
#    You can adjust the number of workers (e.g., --workers 4) based on your server's CPU cores and expected load.
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "main:app"]
