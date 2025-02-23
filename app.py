from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
import pdfplumber
import io
import re
import logging
import traceback
from llm_method import llm_extract_data_from_pdf, MeterData, BillData
import tempfile
import os
import PyPDF2
import pypdfium2 as pdfium
import json
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from models import init_db
from database import get_task_status, get_task_results
from worker import worker

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s'
)
logger = logging.getLogger(__name__)

description = """
# Utility Bill Data Extraction API

This API provides endpoints for extracting structured data from utility bill PDFs.

## Features

* Extract basic bill information (account number, dates, charges)
* Support for multiple meters (up to 3)
* Detailed meter readings and charges
* Handles various utility bill formats
* Advanced LLM-based extraction for complex bills

## Endpoints

The API provides three main endpoints:
- `/extract`: Traditional pattern matching extraction
- `/extract/llm`: Basic LLM-based extraction
- `/extract/enhanced`: Advanced LLM extraction with comprehensive field support
"""

app = FastAPI(
    title="PDF Data Extractor API",
    description=description,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize database
init_db()

class MeterData(BaseModel):
    meter_number: Optional[str] = None
    previous_read_date: Optional[date] = None
    read_date: Optional[date] = None
    previous_reading: Optional[float] = None
    meter_reading: Optional[float] = None
    multiplier: Optional[float] = 1.0
    usage: Optional[float] = None
    unit: Optional[str] = None
    estimated: Optional[bool] = Field(default=False, description="1 if estimated, 0 if not")
    utility_charges: Optional[float] = None
    utility_taxes: Optional[float] = None
    supply_charges: Optional[float] = None
    supply_taxes: Optional[float] = None
    other_charge: Optional[float] = None
    rec_charge: Optional[float] = None
    therm_factor: Optional[float] = None
    adjustment_factor: Optional[float] = None
    demand: Optional[float] = None
    kw_actual: Optional[float] = None
    kw_billed: Optional[float] = None
    power_factor: Optional[float] = None

class BillData(BaseModel):
    account_number: Optional[str] = None
    bill_date: Optional[date] = None
    due_date: Optional[date] = None
    balance_forward: Optional[float] = 0.0
    current_charges: Optional[float] = None
    late_fee: Optional[float] = 0.0
    amount_due: Optional[float] = None
    rebill_adjustment: Optional[bool] = Field(default=False, description="1 if rebill, 0 if not")
    meters: List[MeterData] = []

class ExtractedData(BaseModel):
    """
    Response model for extracted utility bill data.
    """
    status: str = Field(
        description="Status of the extraction (success/error)"
    )
    message: str = Field(
        description="Descriptive message about the extraction result"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Extracted bill data including basic information and meter readings"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
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
                    "rebill_adjustment": False,
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
                            "estimated": False,
                            "utility_charges": 150.00,
                            "utility_taxes": 7.50,
                            "supply_charges": 85.25,
                            "supply_taxes": 8.00
                        }
                    ]
                }
            }
        }
    }

def parse_date(date_str: str) -> Optional[date]:
    try:
        logger.debug(f"Attempting to parse date string: {date_str}")
        date_formats = [
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d-%m-%Y"
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt).date()
                logger.debug(f"Successfully parsed date {date_str} with format {fmt}")
                return parsed_date
            except ValueError:
                continue
        logger.warning(f"Failed to parse date string: {date_str}")
        return None
    except Exception as e:
        logger.error(f"Error parsing date string: {date_str}, Error: {str(e)}")
        return None

def parse_float(value_str: str) -> Optional[float]:
    try:
        logger.debug(f"Attempting to parse float value: {value_str}")
        cleaned = re.sub(r'[^\d.-]', '', value_str)
        result = float(cleaned)
        logger.debug(f"Successfully parsed float value: {result}")
        return result
    except Exception as e:
        logger.error(f"Error parsing float value: {value_str}, Error: {str(e)}")
        return None

def extract_field_value(text: str, patterns: List[str]) -> Optional[str]:
    logger.debug(f"Searching for patterns: {patterns}")
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                value = match.group(1).strip()
                logger.debug(f"Found match for pattern '{pattern}': {value}")
                return value
            except Exception as e:
                logger.error(f"Error extracting value with pattern '{pattern}': {str(e)}")
                continue
    logger.warning(f"No matches found for patterns: {patterns}")
    return None

def is_valid_meter_number(meter_num: str) -> bool:
    """Validate if a string is likely to be a meter number."""
    # Most meter numbers are 5-15 digits long, may include dashes
    if not meter_num or len(meter_num) < 5 or len(meter_num) > 15:
        return False
    
    # Should contain at least some digits
    if not any(c.isdigit() for c in meter_num):
        return False
    
    # Should not be mostly letters
    letter_count = sum(c.isalpha() for c in meter_num)
    if letter_count > len(meter_num) / 2:
        return False
    
    return True

def extract_meter_readings(section: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Extract previous and current readings from a meter section."""
    # Try to find the readings line that matches the format:
    # "65221 Actual 65969 Actual 748 748 kWh"
    readings_match = re.search(r'(\d+)\s+(?:Actual|Estimated)\s+(\d+)\s+(?:Actual|Estimated)\s+(\d+)', section)
    if readings_match:
        prev_reading = parse_float(readings_match.group(1))
        curr_reading = parse_float(readings_match.group(2))
        usage = parse_float(readings_match.group(3))
        return prev_reading, curr_reading, usage
    return None, None, None

def extract_data_from_pdf(pdf_content: bytes) -> BillData:
    try:
        logger.info("Starting PDF data extraction")
        
        # Create a PDF reader object
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            logger.info(f"PDF loaded successfully. Number of pages: {len(pdf.pages)}")
            
            # Initialize empty BillData
            bill_data = BillData()
            
            # Extract text from all pages
            text = ""
            for i, page in enumerate(pdf.pages):
                try:
                    logger.debug(f"Processing page {i+1}")
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"  # Add newline between pages
                        logger.debug(f"Page {i+1} text length: {len(page_text)} characters")
                    else:
                        logger.warning(f"No text extracted from page {i+1}")
                except Exception as e:
                    logger.error(f"Error extracting text from page {i+1}: {str(e)}")
                    continue
            
            if not text:
                logger.error("No text could be extracted from the PDF")
                raise ValueError("No text could be extracted from the PDF")
            
            logger.debug(f"Total extracted text length: {len(text)} characters")
            logger.debug("First 500 characters of extracted text:")
            logger.debug(text[:500])
            
            # Extract account number
            logger.info("Extracting account number")
            account_patterns = [
                r"Account\s*(?:No|Number|#)[:.\s]*([A-Za-z0-9-]+)",
                r"Account:\s*([A-Za-z0-9-]+)",
                r"Account\s+#?\s*([A-Za-z0-9-]+)",
                r"Account\s+([A-Za-z0-9-]+)"
            ]
            bill_data.account_number = extract_field_value(text, account_patterns)
            logger.info(f"Account number found: {bill_data.account_number}")
            
            # Extract dates
            logger.info("Extracting dates")
            bill_date_str = extract_field_value(text, [
                r"Bill\s*Date[:.\s]*([^\n]+)",
                r"Statement\s*Date[:.\s]*([^\n]+)",
                r"Bill\s+Date\s+([^\n]+)",
                r"Bill mailing date is ([^\n]+)"
            ])
            if bill_date_str:
                bill_data.bill_date = parse_date(bill_date_str)
                logger.info(f"Bill date found: {bill_data.bill_date}")
                
            due_date_str = extract_field_value(text, [
                r"Due\s*Date[:.\s]*([^\n]+)",
                r"Payment\s*Due\s*Date[:.\s]*([^\n]+)",
                r"Due\s+Date\s+([^\n]+)",
                r"Amount due on or before ([^\n]+)"
            ])
            if due_date_str:
                bill_data.due_date = parse_date(due_date_str)
                logger.info(f"Due date found: {bill_data.due_date}")
            
            # Extract charges
            logger.info("Extracting charges")
            current_charges_str = extract_field_value(text, [
                r"Current\s*Charges[:.\s]*\$?\s*([\d,.]+)",
                r"Total\s*Current\s*Charges[:.\s]*\$?\s*([\d,.]+)",
                r"Current\s+Charges\s*\$?\s*([\d,.]+)",
                r"Amount due on or before \$?([\d,.]+)"
            ])
            if current_charges_str:
                bill_data.current_charges = parse_float(current_charges_str)
                logger.info(f"Current charges found: {bill_data.current_charges}")
                
            amount_due_str = extract_field_value(text, [
                r"Amount\s*Due[:.\s]*\$?\s*([\d,.]+)",
                r"Total\s*Amount\s*Due[:.\s]*\$?\s*([\d,.]+)",
                r"Amount\s+Due\s*\$?\s*([\d,.]+)",
                r"Amount due on or before \$?([\d,.]+)"
            ])
            if amount_due_str:
                bill_data.amount_due = parse_float(amount_due_str)
                logger.info(f"Amount due found: {bill_data.amount_due}")
                
            # Check for rebill
            bill_data.rebill_adjustment = bool(re.search(r"rebill", text, re.IGNORECASE))
            logger.info(f"Rebill adjustment: {bill_data.rebill_adjustment}")
            
            # Extract meter data with improved detection
            logger.info("Extracting meter data")
            try:
                # Look for meter sections starting with "Meter Read Details:" or "Meter #"
                meter_sections = []
                
                # First try to find sections starting with "Meter Read Details:"
                details_sections = re.split(r"Meter Read Details:", text)[1:]
                for section in details_sections:
                    meter_num_match = re.search(r"Meter\s*#\s*([A-Za-z0-9-]+)", section)
                    if meter_num_match:
                        meter_num = meter_num_match.group(1)
                        if is_valid_meter_number(meter_num):
                            meter_sections.append((meter_num, section))
                            logger.debug(f"Found valid meter section with meter number: {meter_num}")
                        else:
                            logger.debug(f"Rejected invalid meter number: {meter_num}")
                
                logger.info(f"Found {len(meter_sections)} valid meter sections")
            except Exception as e:
                logger.error(f"Error splitting meter sections: {str(e)}")
                meter_sections = []
            
            for i, (meter_num, section) in enumerate(meter_sections):
                if i >= 3:  # Limit to 3 meters as per requirements
                    logger.info("Reached maximum number of meters (3)")
                    break
                
                logger.info(f"Processing meter {i+1}")
                meter = MeterData()
                
                try:
                    # Set meter number
                    meter.meter_number = meter_num
                    logger.info(f"Meter {i+1} number: {meter.meter_number}")
                    
                    # Extract readings using the specific format
                    prev_reading, curr_reading, usage = extract_meter_readings(section)
                    
                    if prev_reading is not None:
                        meter.previous_reading = prev_reading
                        logger.info(f"Meter {i+1} previous reading: {meter.previous_reading}")
                    
                    if curr_reading is not None:
                        meter.meter_reading = curr_reading
                        logger.info(f"Meter {i+1} current reading: {meter.meter_reading}")
                    
                    if usage is not None:
                        meter.usage = usage
                        logger.info(f"Meter {i+1} usage: {meter.usage}")
                    
                    # Extract unit (looking for kWh, kW, etc. after the usage value)
                    unit_match = re.search(r'\d+\s+(kWh|kW|CCF|MCF|Therms?)', section, re.IGNORECASE)
                    if unit_match:
                        meter.unit = unit_match.group(1)
                        logger.info(f"Meter {i+1} unit: {meter.unit}")
                    
                    # Check for estimated reading
                    meter.estimated = bool(re.search(r"Estimated", section, re.IGNORECASE))
                    logger.info(f"Meter {i+1} estimated: {meter.estimated}")
                    
                    # Extract multiplier
                    multiplier_match = re.search(r"Multiplier\s+(\d+(?:\.\d+)?)", section)
                    if multiplier_match:
                        meter.multiplier = parse_float(multiplier_match.group(1))
                        logger.info(f"Meter {i+1} multiplier: {meter.multiplier}")
                    
                    # Extract service period
                    period_match = re.search(r"Service Period\s+(\d{1,2}/\d{1,2})\s*-\s*(\d{1,2}/\d{1,2})", section)
                    if period_match:
                        start_date = period_match.group(1)
                        end_date = period_match.group(2)
                        # Add year to the dates (assuming they're in the same year as bill_date)
                        year = bill_data.bill_date.year if bill_data.bill_date else datetime.now().year
                        try:
                            meter.previous_read_date = datetime.strptime(f"{start_date}/{year}", "%m/%d/%Y").date()
                            meter.read_date = datetime.strptime(f"{end_date}/{year}", "%m/%d/%Y").date()
                            logger.info(f"Meter {i+1} read period: {meter.previous_read_date} to {meter.read_date}")
                        except:
                            logger.warning(f"Could not parse service period dates: {start_date} - {end_date}")
                    
                    # Validate meter data before adding
                    required_fields = [
                        meter.meter_number,
                        any([meter.previous_reading, meter.meter_reading, meter.usage])
                    ]
                    
                    if all(required_fields):
                        bill_data.meters.append(meter)
                        logger.info(f"Added valid meter {i+1} to bill data")
                    else:
                        logger.warning(f"Skipping meter {i+1} due to missing required data")
                    
                except Exception as e:
                    logger.error(f"Error processing meter {i+1}: {str(e)}")
                    continue
            
            logger.info("PDF data extraction completed successfully")
            return bill_data
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

@app.post("/extract", response_model=ExtractedData)
async def extract_pdf_data(file: UploadFile = File(...)):
    """Extract data using traditional pattern matching approach."""
    logger.info(f"Received file: {file.filename}")
    
    if not file.filename.lower().endswith('.pdf'):
        logger.error(f"Invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        contents = await file.read()
        logger.info(f"File size: {len(contents)} bytes")
        
        bill_data = extract_data_from_pdf(contents)
        
        logger.info("Successfully processed PDF file")
        return ExtractedData(
            status="success",
            message="Data extracted successfully",
            data=bill_data.model_dump()
        )
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return ExtractedData(
            status="error",
            message=str(e),
            data=None
        )

@app.post("/extract/llm", response_model=ExtractedData)
async def extract_pdf_data_llm(file: UploadFile = File(...)):
    """Extract data using LLM-based approach."""
    logger.info(f"Received file for LLM extraction: {file.filename}")
    
    if not file.filename.lower().endswith('.pdf'):
        logger.error(f"Invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Read the file content
        content = await file.read()
        # Write content to a temporary file and close it
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            temp_file_path = tmp_file.name
            logger.info(f"Temporary file created: {temp_file_path}")

        try:
            text = ""
            try:
                # Attempt to load PDF with pypdfium2
                pdf = pdfium.PdfDocument(temp_file_path)
                # Extract text using pdfium
                for i, page in enumerate(pdf):
                    try:
                        textpage = page.get_textpage()
                        page_text = textpage.get_text_range()
                        if page_text:
                            text += page_text + "\n"
                            logger.debug(f"Extracted {len(page_text)} characters from page {i+1} using pdfium")
                        else:
                            logger.warning(f"No text extracted from page {i+1} using pdfium")
                        textpage.close()
                        page.close()
                    except Exception as e:
                        logger.error(f"Error extracting text from page {i+1} using pdfium: {str(e)}")
                        continue
                pdf.close()
            except Exception as pdfium_error:
                logger.error(f"PDFium failed to load document: {pdfium_error}. Falling back to pdfplumber.")
                # Fallback extraction using pdfplumber with BytesIO
                with open(temp_file_path, "rb") as f:
                    file_bytes = f.read()
                from io import BytesIO
                with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                    for i, page in enumerate(pdf.pages):
                        try:
                            page_text = page.extract_text() or ""
                            if page_text:
                                text += page_text + "\n"
                                logger.debug(f"Extracted {len(page_text)} characters from page {i+1} using pdfplumber")
                            else:
                                logger.warning(f"No text extracted from page {i+1} using pdfplumber")
                        except Exception as e:
                            logger.error(f"Error extracting text from page {i+1} with pdfplumber: {str(e)}")
                            continue

            if not text:
                raise ValueError("No text could be extracted from the PDF")

            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            logger.debug("First 500 characters of extracted text:")
            logger.debug(text[:500])

            # Use LLM to extract data
            extracted_data = await extract_with_llm(text)

            # Convert the extracted data into BillData model
            bill_data = BillData(
                account_number=extracted_data.get("account_number"),
                bill_date=datetime.strptime(extracted_data.get("bill_date"), "%Y-%m-%d").date() if extracted_data.get("bill_date") else None,
                due_date=datetime.strptime(extracted_data.get("due_date"), "%Y-%m-%d").date() if extracted_data.get("due_date") else None,
                balance_forward=extracted_data.get("balance_forward", 0.0),
                current_charges=extracted_data.get("current_charges"),
                late_fee=extracted_data.get("late_fee", 0.0),
                amount_due=extracted_data.get("amount_due"),
                rebill_adjustment=extracted_data.get("rebill_adjustment", False),
                meters=[
                    MeterData(
                        meter_number=meter.get("meter_number"),
                        previous_read_date=datetime.strptime(meter.get("previous_read_date"), "%Y-%m-%d").date() if meter.get("previous_read_date") else None,
                        read_date=datetime.strptime(meter.get("read_date"), "%Y-%m-%d").date() if meter.get("read_date") else None,
                        previous_reading=meter.get("previous_reading"),
                        meter_reading=meter.get("meter_reading"),
                        multiplier=meter.get("multiplier", 1.0),
                        usage=meter.get("usage"),
                        unit=meter.get("unit"),
                        estimated=meter.get("estimated", False),
                        utility_charges=meter.get("utility_charges"),
                        utility_taxes=meter.get("utility_taxes"),
                        supply_charges=meter.get("supply_charges"),
                        supply_taxes=meter.get("supply_taxes"),
                        other_charge=meter.get("other_charge"),
                        rec_charge=meter.get("rec_charge"),
                        therm_factor=meter.get("therm_factor"),
                        adjustment_factor=meter.get("adjustment_factor"),
                        demand=meter.get("demand"),
                        kw_actual=meter.get("kw_actual"),
                        kw_billed=meter.get("kw_billed"),
                        power_factor=meter.get("power_factor")
                    )
                    for meter in extracted_data.get("meters", [])
                ]
            )

            logger.info("Successfully processed PDF file using LLM")
            return ExtractedData(
                status="success",
                message="Data extracted successfully using LLM",
                data=bill_data.model_dump()
            )
        finally:
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Temporary file removed: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing request with LLM: {str(e)}", exc_info=True)
        return ExtractedData(
            status="error",
            message=str(e),
            data=None
        )

@app.post(
    "/extract/enhanced",
    response_model=ExtractedData,
    summary="Extract utility bill data using enhanced LLM method",
    description="""
    Enhanced endpoint that uses GPT-4 to extract detailed utility bill data.
    This endpoint provides comprehensive data extraction including:
    
    * Basic bill information
    * Multiple meter support
    * Detailed charges and taxes
    * Special flags and adjustments
    
    The endpoint accepts PDF files and returns structured data in JSON format.
    """,
    response_description="Successfully extracted utility bill data in structured format",
    tags=["Extraction"]
)
async def extract_pdf_data_enhanced(
    file: UploadFile = File(
        ...,
        description="PDF file containing the utility bill to process"
    )
):
    """
    Enhanced endpoint that uses GPT-4 to extract detailed utility bill data.
    This endpoint provides more comprehensive data extraction including all meter-related fields.
    """
    try:
        logger.info(f"Received file: {file.filename}")
        
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            try:
                content = await file.read()
                logger.debug(f"Read {len(content)} bytes from uploaded file")
                temp_file.write(content)
                temp_file_path = temp_file.name
                logger.debug(f"Saved uploaded file to temporary path: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error saving uploaded file: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error saving uploaded file: {str(e)}"
                )
        
        try:
            # Extract data using our enhanced LLM method
            logger.info("Starting LLM extraction")
            bill_data = await llm_extract_data_from_pdf(temp_file_path)
            logger.info("LLM extraction completed successfully")
            
            # Convert BillData to JSON-serializable dict
            bill_data_dict = jsonable_encoder(bill_data)
            
            # Create response
            response = ExtractedData(
                status="success",
                message="Data extracted successfully using enhanced LLM method",
                data=bill_data_dict
            )
            
            # Log the response data
            logger.debug(f"Extracted data: {response.model_dump_json(indent=2)}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error during enhanced LLM extraction: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error during enhanced data extraction: {str(e)}"
            )
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error deleting temporary file: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error processing file: {str(e)}"
        )

@app.get("/")
async def root():
    """Serve the index.html file."""
    return FileResponse("static/index.html")

@app.post("/api/extract/batch")
async def extract_batch(files: List[UploadFile] = File(...)):
    """
    Upload multiple PDF files for data extraction
    Returns a task ID that can be used to check the status and results
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    try:
        # Read all files into memory
        file_data = []
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not a PDF"
                )
            content = await file.read()
            file_data.append((content, file.filename))
        
        # Create extraction task
        task_id = await worker.create_extraction_task(file_data)
        
        return JSONResponse({
            "task_id": task_id,
            "message": f"Processing {len(files)} files",
            "status": "pending"
        })
        
    except Exception as e:
        logger.error(f"Error processing batch upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/status")
async def get_task_progress(task_id: str):
    """Get the status and progress of a task"""
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@app.get("/api/tasks/{task_id}/results")
async def get_extraction_results(task_id: str):
    """Get the extraction results for a task"""
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    results = get_task_results(task_id)
    return {
        "task_id": task_id,
        "status": status,
        "results": results
    } 