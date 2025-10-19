-- Bootstrap script for the Vehicle Tracking Management System database.
-- Run as a PostgreSQL superuser (e.g. psql -f scripts/postgres_init.sql).

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'vtms_app'
    ) THEN
        CREATE ROLE vtms_app WITH LOGIN PASSWORD 'change-this-password';
    END IF;
END;
$$;

CREATE DATABASE vtms OWNER vtms_app;

\c vtms

-- Ensure the role has basic privileges. Additional grants can be added later.
GRANT ALL PRIVILEGES ON DATABASE vtms TO vtms_app;

-- Optional: install PostGIS if geospatial queries are required.
-- CREATE EXTENSION IF NOT EXISTS postgis;
