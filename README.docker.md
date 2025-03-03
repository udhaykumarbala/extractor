# PDF Extractor - Docker Setup

This guide explains how to run the PDF Extractor application using Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- OpenAI API key (set in the `.env` file)

## Quick Start

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd extractor
   ```

2. Make sure your `.env` file contains your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. Build and start the Docker container:
   ```bash
   docker-compose up -d
   ```

4. Access the application at:
   ```
   http://localhost:8000
   ```

## Configuration

The Docker Compose setup includes:

- The main application container (extractor)
- Port mapping: 8000:8000
- Persistent volumes for:
  - Uploaded PDF files: `./uploads:/app/uploads`
  - SQLite database: `./extraction.db:/app/extraction.db`

## Maintenance

### View Logs

```bash
docker-compose logs -f
```

### Update Application

If you make changes to the code:

```bash
docker-compose build
docker-compose up -d
```

### Stop Application

```bash
docker-compose down
```

## Troubleshooting

1. If the application fails to start:
   - Check Docker logs: `docker-compose logs -f`
   - Verify your OpenAI API key is correct in the `.env` file

2. If uploads don't work:
   - Ensure the uploads directory has proper permissions
   - Check if the database is functioning correctly

3. For performance issues:
   - Adjust Docker resource allocation in Docker Desktop settings

## Notes

- This Docker setup uses Python 3.10 and includes all necessary dependencies to handle PDF files
- The application data is persisted using Docker volumes
- The container will automatically restart if it crashes 