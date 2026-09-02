-- ================================================================
-- SENTINEL — Database Initialization
-- Creates schema-separated logical stores (Section 5 of project.md)
-- ================================================================

-- Create schemas for logical separation
CREATE SCHEMA IF NOT EXISTS ops;       -- Operational DB
CREATE SCHEMA IF NOT EXISTS kb;        -- Knowledge Store
CREATE SCHEMA IF NOT EXISTS artifacts; -- Artifact Store
CREATE SCHEMA IF NOT EXISTS audit;     -- Audit Store

-- Grant usage to application role
GRANT USAGE ON SCHEMA ops, kb, artifacts, audit TO sentinel_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ops TO sentinel_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kb TO sentinel_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA artifacts TO sentinel_admin;

-- Audit schema: application role can INSERT and SELECT only (FR7.6)
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA audit TO sentinel_admin;

-- Set default search path
ALTER ROLE sentinel_admin SET search_path TO ops, kb, artifacts, audit, public;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
