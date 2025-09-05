-- PostgreSQL initialization script for Hackathon Backend
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create schema for application data
CREATE SCHEMA IF NOT EXISTS hackathon;

-- Grant privileges to the application user
GRANT ALL PRIVILEGES ON SCHEMA hackathon TO hackathon_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA hackathon TO hackathon_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA hackathon TO hackathon_user;

-- Set default search path for the application user
ALTER USER hackathon_user SET search_path = hackathon, public;

-- Create a sample configuration table for validation
CREATE TABLE IF NOT EXISTS hackathon.app_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial configuration
INSERT INTO hackathon.app_config (key, value, description) VALUES
    ('app_name', 'Hackathon Backend', 'Application name'),
    ('app_version', '1.0.0', 'Application version'),
    ('db_initialized_at', CURRENT_TIMESTAMP::TEXT, 'Database initialization timestamp')
ON CONFLICT (key) DO NOTHING;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_app_config_key ON hackathon.app_config(key);
CREATE INDEX IF NOT EXISTS idx_app_config_created_at ON hackathon.app_config(created_at);

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Hackathon Backend database initialized successfully at %', CURRENT_TIMESTAMP;
END $$;