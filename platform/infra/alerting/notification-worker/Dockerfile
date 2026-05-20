FROM python:3.11-slim

WORKDIR /app

COPY notification-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY notification-worker/ .

RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

USER appuser

CMD ["python", "worker.py"]
