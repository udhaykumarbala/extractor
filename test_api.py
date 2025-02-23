import asyncio
import json
from pathlib import Path
import httpx
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_pdf_extraction(pdf_path: str, endpoint: str = "extract/enhanced"):
    """
    Test PDF extraction using the specified API endpoint.
    """
    api_url = f"http://localhost:8000/{endpoint}"
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return
    
    logger.info(f"Testing extraction for file: {pdf_path}")
    
    async with httpx.AsyncClient() as client:
        try:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                response = await client.post(api_url, files=files, timeout=60.0)
                
            if response.status_code == 200:
                result = response.json()
                logger.info("Extraction successful")
                logger.info("Extracted data:")
                print(json.dumps(result, indent=2))
                return result
            else:
                logger.error(f"API Error: Status {response.status_code}")
                try:
                    error_detail = response.json()
                    logger.error(f"Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    logger.error(f"Raw error response: {response.text}")
                return None
                
        except httpx.TimeoutException:
            logger.error("Request timed out - the server took too long to respond")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error during API call: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

async def main():
    # Test files
    pdf_files = [
        "018.02.03.25.020009.pdf",
        "018.02.17.25.768217.pdf",
        "019.02.12.247600_(1).pdf"
    ]
    
    for pdf_file in pdf_files:
        logger.info(f"\n{'='*50}\nTesting {pdf_file}\n{'='*50}")
        result = await test_pdf_extraction(pdf_file)
        if result:
            # Validate the extracted data
            data = result.get("data", {})
            
            # Check basic fields
            logger.info("\nValidation Summary:")
            logger.info(f"Account Number: {data.get('account_number')}")
            logger.info(f"Bill Date: {data.get('bill_date')}")
            logger.info(f"Due Date: {data.get('due_date')}")
            logger.info(f"Current Charges: {data.get('current_charges')}")
            logger.info(f"Amount Due: {data.get('amount_due')}")
            
            # Check meter data
            meters = data.get("meters", [])
            logger.info(f"\nNumber of meters found: {len(meters)}")
            for i, meter in enumerate(meters, 1):
                logger.info(f"\nMeter {i}:")
                logger.info(f"  Meter Number: {meter.get('meter_number')}")
                logger.info(f"  Previous Reading: {meter.get('previous_reading')}")
                logger.info(f"  Current Reading: {meter.get('meter_reading')}")
                logger.info(f"  Usage: {meter.get('usage')} {meter.get('unit')}")
                logger.info(f"  Utility Charges: {meter.get('utility_charges')}")
                logger.info(f"  Utility Taxes: {meter.get('utility_taxes')}")
                
        logger.info("\n")

if __name__ == "__main__":
    asyncio.run(main()) 