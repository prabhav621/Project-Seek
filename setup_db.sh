#!/bin/bash
set -e

echo "Starting PostgreSQL database..."
docker-compose up -d db

echo "Waiting for PostgreSQL to be ready..."
sleep 5

echo "Running database migrations..."
alembic upgrade head

echo "Database setup complete."
