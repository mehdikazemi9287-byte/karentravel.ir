\set ON_ERROR_STOP on
\if :{?api_password}
\else
  \echo 'api_password psql variable is required'
  \quit 2
\endif

SELECT format(
  'CREATE ROLE karenseir_api LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'api_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_api') \gexec

ALTER ROLE karenseir_api WITH LOGIN PASSWORD :'api_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE :"DBNAME" TO karenseir_api;
GRANT USAGE ON SCHEMA public TO karenseir_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO karenseir_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO karenseir_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO karenseir_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO karenseir_api;
REVOKE CREATE ON SCHEMA public FROM karenseir_api;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'find_login_identity') THEN
        GRANT EXECUTE ON FUNCTION public.find_login_identity(text) TO karenseir_api;
    END IF;
END $$;
