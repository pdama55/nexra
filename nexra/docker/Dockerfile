# Stage 1: Builder
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install poetry==1.8.0
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --no-interaction --no-ansi --no-root

# Stage 2: Runtime
FROM python:3.12-slim AS runtime
RUN adduser --disabled-password --gecos '' appuser
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY . .
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
