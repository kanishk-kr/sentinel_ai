-- ================================================================
-- SENTINEL — Database Initialization
-- Creates schema-separated logical stores (Section 5 of project.md)
-- ================================================================

-- Create app role
CREATE ROLE sentinel_app WITH LOGIN PASSWORD 'sentinel_app_pass_2026';

-- Create schemas for logical separation
CREATE SCHEMA IF NOT EXISTS ops AUTHORIZATION sentinel_owner;
CREATE SCHEMA IF NOT EXISTS kb AUTHORIZATION sentinel_owner;
CREATE SCHEMA IF NOT EXISTS artifacts AUTHORIZATION sentinel_owner;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION sentinel_owner;

-- Grant usage to application role
GRANT USAGE ON SCHEMA ops, kb, artifacts, audit TO sentinel_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ops TO sentinel_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kb TO sentinel_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA artifacts TO sentinel_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT ALL ON TABLES TO sentinel_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA kb GRANT ALL ON TABLES TO sentinel_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA artifacts GRANT ALL ON TABLES TO sentinel_app;

-- Audit schema: application role can INSERT and SELECT only (FR7.6)
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA audit TO sentinel_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT, INSERT ON TABLES TO sentinel_app;

-- Set default search path
ALTER ROLE sentinel_owner SET search_path TO ops, kb, artifacts, audit, public;
ALTER ROLE sentinel_app SET search_path TO ops, kb, artifacts, audit, public;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
