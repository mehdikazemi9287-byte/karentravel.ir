FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
RUN chmod 755 /app/entrypoint.sh && useradd --create-home --uid 10001 karenseir && chown -R karenseir:karenseir /app
USER karenseir
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["/app/entrypoint.sh"]
