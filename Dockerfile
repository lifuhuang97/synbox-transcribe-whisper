FROM python:3.11


# Install ffmpeg and ffprobe
RUN apt-get update && apt-get install -y ffmpeg


WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0", "--port=$PORT"]