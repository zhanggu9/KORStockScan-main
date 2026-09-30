FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    PATH=/app/.venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git libgomp1 procps tzdata util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN python -m venv /app/.venv \
    && pip install --no-cache-dir -r requirements.txt \
        'pandas>=2.3.2,<3' 'pandas-ta==0.4.71b0' \
        'python-dotenv>=1,<2' 'gunicorn>=23,<24'

COPY src/ ./src/
COPY deploy/ ./deploy/
COPY configs/ ./configs/
RUN mkdir -p /app/data /app/logs \
    && chown 1000:1000 /app /app/data /app/logs

USER 1000:1000
