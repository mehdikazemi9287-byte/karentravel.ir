\set ON_ERROR_STOP on
\if :{?worker_password}
\else
  \echo 'worker_password psql variable is required'
  \quit 2
\endif

SELECT format(
  'CREATE ROLE karenseir_worker LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS',
  :'worker_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karenseir_worker') \gexec

ALTER ROLE karenseir_worker WITH LOGIN PASSWORD :'worker_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
GRANT CONNECT ON DATABASE :"DBNAME" TO karenseir_worker;
GRANT USAGE ON SCHEMA public TO karenseir_worker;
GRANT SELECT, UPDATE ON outbox_events, notifications, notification_delivery_attempts TO karenseir_worker;
REVOKE ALL ON users, bookings, reservations, financial_ledger_entries, wallets FROM karenseir_worker;

