FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Optional pip.conf (not in git) lets a server use a PyPI mirror without a server-only commit;
# deploy/karenseir-deploy-server.sh writes it. Absent = default PyPI.
COPY requirements.txt pip.con[f] ./
RUN if [ -f pip.conf ]; then mv pip.conf /etc/pip.conf; fi && pip install --no-cache-dir -r requirements.txt
COPY app ./app
ARG GIT_COMMIT=unknown
ARG BUILD_TIMESTAMP=unknown
ENV GIT_COMMIT=$GIT_COMMIT BUILD_TIMESTAMP=$BUILD_TIMESTAMP
RUN useradd --uid 10003 --create-home kassistant && chown -R kassistant:kassistant /app
USER kassistant
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
