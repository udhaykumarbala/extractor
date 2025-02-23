# Utility Bill Data Extractor

A FastAPI-based service for extracting structured data from utility bill PDFs using advanced LLM-based extraction.

## Features

- Extract comprehensive utility bill data including:
  - Basic bill information (account number, dates, charges)
  - Multiple meter support (up to 3 meters)
  - Detailed meter readings and charges
  - Special flags and adjustments
- Advanced LLM-based extraction using GPT-4
- Robust error handling and validation
- Detailed logging for debugging
- OpenAPI documentation

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd utility-bill-extractor
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file with the following:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Start the server:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

2. Access the API documentation:
Open http://localhost:8000/docs in your browser to view the interactive API documentation.

3. Use the API:

Example using curl:
```bash
curl -X POST "http://localhost:8000/extract/enhanced" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@path/to/your/bill.pdf"
```

Example using Python:
```python
import requests

url = "http://localhost:8000/extract/enhanced"
files = {"file": ("bill.pdf", open("path/to/your/bill.pdf", "rb"), "application/pdf")}
response = requests.post(url, files=files)
data = response.json()
print(data)
```

## API Endpoints

### POST /extract/enhanced

Enhanced endpoint that uses GPT-4 to extract detailed utility bill data.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: PDF file

**Response:**
```json
{
  "status": "success",
  "message": "Data extracted successfully",
  "data": {
    "account_number": "123-456-789",
    "bill_date": "2025-01-24",
    "due_date": "2025-02-12",
    "balance_forward": 100.50,
    "current_charges": 250.75,
    "late_fee": 0.00,
    "amount_due": 351.25,
    "rebill_adjustment": false,
    "meters": [
      {
        "meter_number": "M123456",
        "previous_read_date": "2024-12-20",
        "read_date": "2025-01-24",
        "previous_reading": 1000.0,
        "meter_reading": 1500.0,
        "multiplier": 1.0,
        "usage": 500.0,
        "unit": "kWh",
        "estimated": false,
        "utility_charges": 150.00,
        "utility_taxes": 7.50,
        "supply_charges": 85.25,
        "supply_taxes": 8.00
      }
    ]
  }
}
```

## Testing

Run the test script to verify the extraction with sample files:
```bash
python test_api.py
```

## Error Handling

The API uses proper error handling and returns appropriate HTTP status codes:

- 200: Successful extraction
- 400: Invalid request (e.g., not a PDF file)
- 500: Server error (e.g., extraction failed)

Error responses include detailed error messages to help diagnose issues.

## Logging

The application uses comprehensive logging to help with debugging:

- DEBUG level: Detailed information about the extraction process
- INFO level: General operation information
- ERROR level: Error details with stack traces

Logs are output to stderr with timestamps and log levels.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 