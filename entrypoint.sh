#!/bin/bash
set -e

echo "Checking database directory permissions..."
# Ensure the app directory is writable
touch /app/permissions_test && rm /app/permissions_test || {
    echo "Error: Cannot write to /app directory. Fixing permissions..."
    chmod 777 /app
}

echo "Initializing database..."
# Make sure database file is writable or doesn't exist yet
if [ -f /app/extraction.db ]; then
    echo "Database file exists, checking permissions..."
    touch /app/extraction.db || {
        echo "Fixing database file permissions..."
        chmod 666 /app/extraction.db
    }
else
    echo "Database file doesn't exist yet, it will be created with proper permissions."
fi

# Try to initialize database
python -c "from models import init_db; init_db()" || {
    echo "Database initialization failed. Trying with a new database file..."
    # If volume-mounted DB fails, try with a new local DB
    mv /app/extraction.db /app/extraction.db.bak 2>/dev/null || true
    python -c "from models import init_db; init_db()"
}

echo "Starting PDF Extractor service..."
exec python run.py 