REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE ROLE bi_reader
WITH
    LOGIN
    PASSWORD 'local_reader_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT;

GRANT CONNECT ON DATABASE bi_copilot TO bi_reader;
GRANT USAGE ON SCHEMA public TO bi_reader;

ALTER ROLE bi_reader SET default_transaction_read_only = on;
ALTER ROLE bi_reader SET statement_timeout = '5s';

ALTER DEFAULT PRIVILEGES
IN SCHEMA public
GRANT SELECT ON TABLES TO bi_reader;

ALTER DEFAULT PRIVILEGES
IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO bi_reader;