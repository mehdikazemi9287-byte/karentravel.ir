# shared by deploy.sh / rollback.sh (sourced). Secrets are read from the running containers and never printed.
W=~/ks-checkline-work; B=$(cat $W/release_backup_dir); NEW=$(cat $W/release_image); NET=karenseir_default; PREV=karenseir-api-1-prev-d2ba674
OWNER_URL=$(docker inspect karenseir-db-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | python3 -c "
import sys,urllib.parse
e=dict(l.rstrip('\n').split('=',1) for l in sys.stdin if '=' in l)
print('postgresql+psycopg://%s:%s@db:5432/%s' % (e['POSTGRES_USER'], urllib.parse.quote(e['POSTGRES_PASSWORD'], safe=''), e.get('POSTGRES_DB', e['POSTGRES_USER'])))")
owner() { docker run --rm --network $NET -e DATABASE_URL="$OWNER_URL" -e ENVIRONMENT=production "$@"; }   # one-off, owner role, production network
sql() { docker exec -i karenseir-db-1 psql -U karenseir -d karenseir -v ON_ERROR_STOP=1 -At -F ' | ' "$@"; }
