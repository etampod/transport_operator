FROM python:3.11-slim

# Declared so a proxy on the build machine is visible to pip. These do not
# become environment variables in the running image.
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /home/appuser/.streamlit

COPY requirements.txt .
COPY docker/extra-ca/ /tmp/extra-ca/
# Optional proxy CA: drop a *.crt file in docker/extra-ca before building.
# pip keeps its own CA bundle unless PIP_CERT points at the system store.
RUN set -eu; \
    if ls /tmp/extra-ca/*.crt >/dev/null 2>&1; then \
      cat /tmp/extra-ca/*.crt >> /etc/ssl/certs/ca-certificates.crt; \
    fi; \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    pip install --no-cache-dir -r requirements.txt; \
    rm -rf /tmp/extra-ca

ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY src ./src
COPY corpus ./corpus
COPY pyproject.toml ./pyproject.toml
COPY .streamlit ./.streamlit

ENV PYTHONPATH=/app/src \
    HOME=/home/appuser \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN chown -R appuser:appuser /app /home/appuser
USER appuser

EXPOSE 8000 8501

CMD ["streamlit", "run", "src/ui/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
