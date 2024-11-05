FROM python:3.11

# Install ffmpeg and ffprobe
RUN apt-get update && apt-get install -y ffmpeg

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port 8080, required by Cloud Run
EXPOSE $PORT

# Update Gunicorn command with additional parameters
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT --workers=2 --threads=8 --timeout=0 app:app"]