FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Optional pip.conf (not in git) lets a server use a PyPI mirror without a server-only commit;
# deploy/karenseir-deploy-server.sh writes it. Absent = default PyPI.
COPY requirements.txt pip.con[f] ./
RUN if [ -f pip.conf ]; then mv pip.conf /etc/pip.conf; fi && pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY catalog_data ./catalog_data
COPY scripts/catalog ./scripts/catalog
COPY entrypoint.sh ./entrypoint.sh
ARG GIT_COMMIT=unknown
ARG BUILD_TIMESTAMP=unknown
RUN printf '{"git_commit": "%s", "build_timestamp_utc": "%s"}\n' "$GIT_COMMIT" "$BUILD_TIMESTAMP" > /app/build_info.json
RUN chmod 755 /app/entrypoint.sh && useradd --create-home --uid 10001 karenseir && chown -R karenseir:karenseir /app
RUN mkdir -p /app/media && chown karenseir:karenseir /app/media
VOLUME /app/media
USER karenseir
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["/app/entrypoint.sh"]
