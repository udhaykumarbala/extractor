#!/bin/bash
set -e

echo "Initializing database..."
python -c "from models import init_db; init_db()"

echo "Starting PDF Extractor service..."
exec python run.py 