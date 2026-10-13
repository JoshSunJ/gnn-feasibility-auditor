FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY docs/real-data-study.json /build/docs/real-data-study.json
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements-service.lock ./
RUN pip install --no-cache-dir -r requirements-service.lock
COPY pyproject.toml ./
COPY gnn_auditor ./gnn_auditor
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home auditor
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER auditor
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8000')+'/api/health',timeout=2)"
CMD ["sh", "-c", "exec uvicorn gnn_auditor.service.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --limit-concurrency 32 --backlog 64 --timeout-keep-alive 5 --no-access-log"]
