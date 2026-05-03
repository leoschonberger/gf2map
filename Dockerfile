FROM python:3.11-slim

ARG VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${VERSION}

WORKDIR /app

LABEL org.opencontainers.image.version="${VERSION}"

# Install runtime deps. lxml ships manylinux wheels, no system libs needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user.
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY app/ app/

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)" \
  || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
