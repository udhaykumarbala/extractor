FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for PDF libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    pkg-config \
    python3-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code - fixing wildcard copy syntax
COPY *.py ./
COPY .env .
COPY entrypoint.sh .

# Create necessary directories
RUN mkdir -p uploads
RUN mkdir -p static
RUN mkdir -p data
RUN chmod -R 777 data

# Copy static files if they exist
COPY static/ static/

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose the port the app runs on
EXPOSE 8000

# Run the application with initialization
CMD ["/app/entrypoint.sh"] 