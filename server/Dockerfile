FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# These are overridden by docker-compose env / volume mounts
ENV CAD_DB_PATH=/data/cad.db
ENV CAD_ARCHIVE_ROOT=/nas

EXPOSE 8765

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
