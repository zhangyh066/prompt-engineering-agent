# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_NO_PYTHON_DOWNLOADS=1 \
    PATH="/opt/venv/bin:$PATH" \
    PEA_DATABASE_PATH=/data/pea.db \
    PEA_DEFAULT_PROVIDER=openai \
    PEA_ENABLE_REAL_PROVIDERS=False

WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.19
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable \
    && groupadd --system pea \
    && useradd --system --create-home --gid pea pea \
    && mkdir -p /data \
    && chown -R pea:pea /data /home/pea

USER pea

FROM runtime-base AS api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]
CMD ["python", "-m", "uvicorn", "pea.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime-base AS ui
ENV PEA_API_BASE_URL=http://api:8000
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "src/pea/ui/app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
