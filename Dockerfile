FROM python:3.11

# Install ffmpeg and ffprobe
RUN apt-get update && apt-get install -y ffmpeg

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port 8080, required by Cloud Run
EXPOSE 8080

WORKDIR /app

RUN apt-get update && apt-get install -y git

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables for Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create necessary directories
RUN mkdir -p media output/track

RUN mkdir -p /app/media && chmod 777 /app/media

# Create gunicorn config file - optimized for cold starts
RUN echo 'import multiprocessing\n\
bind = "0.0.0.0:8080"\n\
worker_class = "gthread"\n\
workers = 1\n\
threads = 8\n\
timeout = 300\n\
keepalive = 65\n\
accesslog = "-"\n\
errorlog = "-"\n\
loglevel = "info"\n\
preload_app = True\n\
max_requests = 1000\n\
max_requests_jitter = 50' > gunicorn.conf.py

# Create a startup script
RUN echo '#!/bin/bash\n\
echo "Starting Gunicorn server..."\n\
gunicorn --config gunicorn.conf.py app:app' > start.sh

# Make the startup script executable
RUN chmod +x start.sh

# Use the startup script as the entrypoint
ENTRYPOINT ["./start.sh"]