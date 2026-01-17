-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Set default SRID to Lambert-93
ALTER DATABASE foncier_express SET search_path TO public, topology;

-- Tables will be created by the application migrations
-- This script only ensures PostGIS is ready
