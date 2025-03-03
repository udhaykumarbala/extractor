#!/bin/bash
set -e

echo "Setting up data directory..."
mkdir -p /app/data
chmod 777 /app/data

echo "Checking for database file..."
DB_FILE="/app/data/extraction.db"
if [ -f "$DB_FILE" ]; then
    echo "Database file exists, checking permissions..."
    # Check if we can write to it
    if [ ! -w "$DB_FILE" ]; then
        echo "Setting write permissions on database file..."
        chmod 666 "$DB_FILE"
    fi
else
    echo "Database file doesn't exist yet, it will be created with proper permissions."
    # Creating an empty file to ensure proper permissions
    touch "$DB_FILE"
    chmod 666 "$DB_FILE"
fi

echo "Initializing database..."
python -c "from models import init_db; init_db()" || {
    echo "Database initialization failed. This could be due to permission issues."
    echo "Debugging information:"
    ls -la /app/data
    df -h
    id
    echo "Trying with a new database setup..."
    rm -f "$DB_FILE" || true
    touch "$DB_FILE" 
    chmod 666 "$DB_FILE"
    python -c "from models import init_db; init_db()"
}

echo "Starting PDF Extractor service..."
exec python run.py 