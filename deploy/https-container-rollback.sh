#!/usr/bin/env bash
# Rollback of https-container.sh: restores nginx conf and .env from a backup dir and reloads nginx / restarts api.
set -euo pipefail
BK=${1:?usage: https-container-rollback.sh /opt/karenseir/backups/https-YYYYmmdd-HHMMSS}
ROOT=/opt/karenseir
cp "$BK/default.conf" $ROOT/nginx/default.conf
cp "$BK/env.bak" $ROOT/.env
docker exec karenseir-nginx-1 nginx -t && docker exec karenseir-nginx-1 nginx -s reload
cd $ROOT && docker compose up -d --no-deps api
echo "ROLLBACK-OK (certificate files kept in /etc/letsencrypt; harmless)"
