FROM python:3.13.3-alpine

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt --no-cache-dir

COPY api/ api/

# Development command with auto-reload - uncomment for local development
# CMD ["gunicorn", "--workers=1", "--bind", "0.0.0.0:5000", "--reload", "api.spotify:app"]

# Production command
CMD ["gunicorn", "--workers=1", "--bind", "0.0.0.0:5000", "api.spotify:app"]
