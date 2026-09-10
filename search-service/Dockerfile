FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ARG GIT_COMMIT=unknown
ARG BUILD_TIMESTAMP=unknown
ENV GIT_COMMIT=$GIT_COMMIT BUILD_TIMESTAMP=$BUILD_TIMESTAMP
RUN useradd --uid 10002 --create-home ksearch && chown -R ksearch:ksearch /app
USER ksearch
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
