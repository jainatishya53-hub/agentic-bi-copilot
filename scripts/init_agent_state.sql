-- Create a separate database user for LangGraph persistence.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'bi_agent'
    ) THEN
        CREATE ROLE bi_agent
        WITH
            LOGIN
            PASSWORD 'local_agent_password'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT;
    END IF;
END
$$;

-- Keep agent workflow data separate from business tables.
CREATE SCHEMA IF NOT EXISTS agent_state
AUTHORIZATION bi_agent;

-- Prevent other database users from using this schema automatically.
REVOKE ALL ON SCHEMA agent_state FROM PUBLIC;

-- Allow bi_agent to connect and manage checkpoint tables.
GRANT CONNECT ON DATABASE bi_copilot TO bi_agent;
GRANT USAGE, CREATE ON SCHEMA agent_state TO bi_agent;

-- Ensure tables created by bi_agent are placed in agent_state.
ALTER ROLE bi_agent
IN DATABASE bi_copilot
SET search_path = agent_state;

-- Explicitly prevent the persistence user from reading business data.
REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA public
FROM bi_agent;

REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA public
FROM bi_agent;