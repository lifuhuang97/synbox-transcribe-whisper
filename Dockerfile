FROM python:3.11

# Install ffmpeg and ffprobe
RUN apt-get update && apt-get install -y ffmpeg

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port 8080, required by Cloud Run
EXPOSE 8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Update Gunicorn command with additional parameters
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]