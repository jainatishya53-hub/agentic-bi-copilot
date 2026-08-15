-- Prevent ordinary users from creating objects in the public schema.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Create the read-only role used by the application.
CREATE ROLE bi_reader
WITH
    LOGIN
    PASSWORD 'local_reader_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT;

-- Allow the reader to connect to the database and access the schema.
GRANT CONNECT ON DATABASE bi_copilot TO bi_reader;
GRANT USAGE ON SCHEMA public TO bi_reader;

-- Apply read-only and timeout protections to every reader session.
ALTER ROLE bi_reader
SET default_transaction_read_only = on;

ALTER ROLE bi_reader
SET statement_timeout = '5s';

-- Automatically grant read access to tables created in the future.
ALTER DEFAULT PRIVILEGES
IN SCHEMA public
GRANT SELECT ON TABLES TO bi_reader;

-- Automatically grant sequence access when required by table queries.
ALTER DEFAULT PRIVILEGES
IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO bi_reader;