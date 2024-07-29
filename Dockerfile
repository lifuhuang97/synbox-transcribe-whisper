FROM python:3.11
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# EXPOSE 5050
# CMD ["gunicorn", "-b", "0.0.0.0:8080", "--workers", "3", "--timeout", "900", "app:app"]

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]