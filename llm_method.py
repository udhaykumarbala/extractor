import io
import json
import logging
import pdfplumber
from openai import OpenAI
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from dotenv import load_dotenv
import os
import re
from dateutil import parser as date_parser

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables and initialize OpenAI client
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def safe_parse_date(date_str):
    """Safely parse date strings, handling special cases and multiple formats."""
    if not date_str:
        return None
        
    # Handle special cases
    special_cases = ["Upon Receipt", "upon receipt", "UPON RECEIPT", "Due on receipt", "DUE ON RECEIPT"]
    if any(case in date_str for case in special_cases):
        logger.warning(f"Special date case encountered: '{date_str}'. Returning None.")
        return None
    
    # Try ISO format first
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass
    
    # Try other common date formats
    try:
        return date_parser.parse(date_str)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}. Returning None.")
        return None


class MeterData(BaseModel):
    meter_number: Optional[str] = None
    bill_type: Optional[Literal["Water bill", "Telecom bill", "EB bill", "Gas bill"]] = Field(default=None, description="Type of utility bill")
    previous_read_date: Optional[datetime] = None
    read_date: Optional[datetime] = None
    previous_reading: Optional[float] = None
    meter_reading: Optional[float] = None
    multiplier: Optional[float] = 1.0
    usage: Optional[float] = None
    unit: Optional[str] = None
    estimated: Optional[bool] = Field(default=False)
    utility_charges: Optional[float] = Field(default=None, description="Base charges plus all fees and surcharges (except taxes)")
    utility_taxes: Optional[float] = Field(default=None, description="Sum of State Tax + Sales Tax + Utility Tax + City Tax only")
    supply_charges: Optional[float] = None
    supply_taxes: Optional[float] = None
    other_charge: Optional[float] = Field(default=None, description="Other charges or costs specified in the bill")
    therm_factor: Optional[float] = None
    adjustment_factor: Optional[float] = None
    demand: Optional[float] = None
    kw_actual: Optional[float] = None
    kw_billed: Optional[float] = None
    power_factor: Optional[float] = None


class BillData(BaseModel):
    account_number: Optional[str] = None
    bill_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    balance_forward: Optional[float] = 0.0
    current_charges: Optional[float] = None
    late_fee: Optional[float] = 0.0
    amount_due: Optional[float] = None
    rebill_adjustment: Optional[bool] = Field(default=False)
    meters: List[MeterData] = []
    source_file: Optional[str] = Field(default=None, description="Name of the source PDF file")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    }


async def llm_extract_data_from_pdf(file_path: str) -> BillData:
    """
    Extracts text from the specified PDF file using pdfplumber, sends it to an LLM using OpenAI's API,
    and returns a validated BillData instance.
    """
    # Extract text from PDF using pdfplumber
    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        logger.error(f"Error reading PDF file: {e}")
        raise

    pdf_stream = io.BytesIO(pdf_bytes)
    text = ""
    try:
        with pdfplumber.open(pdf_stream) as pdf:
            logger.info(f"PDF loaded successfully. Number of pages: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                logger.debug(f"Extracted {len(page_text)} characters from page {i+1}")
    except Exception as e:
        logger.error(f"Error extracting text using pdfplumber: {e}")
        raise

    if not text.strip():
        raise ValueError("No text could be extracted from the PDF")

    logger.info(f"Total extracted text length: {len(text)} characters")

    # Prepare LLM prompts
    system_prompt = """You are an expert in extracting utility bill data. Extract ALL available information from utility bills into a structured format.
For each bill, extract:
1. Basic Information:
   - account_number (string)
   - bill_date (YYYY-MM-DD)
   - due_date (YYYY-MM-DD)
   - balance_forward (float)
   - current_charges (float)
   - late_fee (float)
   - amount_due (float)
   - rebill_adjustment (boolean, true if bill mentions rebill/adjustment)

2. For each meter (up to 3 meters), extract:
   - meter_number (string)
   - bill_type (string, must be one of: "Water bill", "Telecom bill", "EB bill", "Gas bill")
   - previous_read_date (YYYY-MM-DD)
   - read_date (YYYY-MM-DD)
   - previous_reading (float)
   - meter_reading (float)
   - multiplier (float, default 1.0)
   - usage (float)
   - unit (string)
   - estimated (boolean, true if reading is estimated)
   - utility_charges (float, include:
     * Base meter charges
     * All fees and surcharges
     * E911 fees
     * Universal Service Fund
     * Telecommunications Relay Service
     * Any other regulatory fees or surcharges
     * Any miscellaneous charges not explicitly labeled as "other charge" or "other cost")
   - utility_taxes (float, sum of ONLY these taxes:
     * State Tax
     * Sales Tax
     * Utility Tax
     * City Tax)
   - supply_charges (float, include:
     * Generation charges
     * Supply service charges
     * Energy procurement costs
     * Commodity charges
     * Power supply adjustment)
   - supply_taxes (float, include:
     * Taxes on supply/generation charges
     * Taxes on energy procurement
     * Taxes specifically tied to supply portion
     * Tax on commodity charges
     Look for these in the supply/generation section of the bill)
   - other_charge (float, ONLY include charges that are explicitly labeled as:
     * "Other Charge"
     * "Other Charges"
     * "Other Cost"
     * "Other Costs"
     Do NOT include any other types of charges here)
   - therm_factor (float, if applicable)
   - adjustment_factor (float, if applicable)
   - demand (float, if applicable)
   - kw_actual (float, if applicable)
   - kw_billed (float, if applicable)
   - power_factor (float, if applicable)

Respond with a valid JSON object containing these fields. Include null for missing values.
Be precise with number extraction and pay attention to decimal places.
For boolean fields, use true/false values.
For dates, use ISO format (YYYY-MM-DD).

IMPORTANT DATE HANDLING RULES:
1. For standard dates, use ISO format (YYYY-MM-DD).
2. If a date field says "Upon Receipt" or similar non-date text, use the exact text "Upon Receipt".
3. If a date is completely missing, use null.
4. Don't make up dates - if you can't determine the exact date, use null.

For bill_type, determine the type based on:
- Water bill: If the bill is for water usage/consumption
- Telecom bill: If the bill is for telecom usage/consumption
- EB bill: If the bill is for electricity
- Gas bill: If the bill is for natural gas

For charges categorization:
1. utility_taxes should ONLY include:
   - State Tax
   - Sales Tax
   - Utility Tax
   - City Tax

2. utility_charges should include:
   - Base meter charges
   - All fees and surcharges
   - E911 fees
   - Universal Service Fund
   - Telecommunications Relay Service
   - Any other regulatory fees
   - Any miscellaneous charges not explicitly labeled as "other charge" or "other cost"

3. supply_charges and supply_taxes:
   - Look in the supply/generation section of the bill
   - supply_charges: Include generation charges, supply service, energy procurement
   - supply_taxes: Include any taxes specifically on supply/generation portion
   - These are often in a separate section from delivery/distribution charges

4. other_charge should ONLY include:
   - Charges explicitly labeled as "Other Charge"
   - Charges explicitly labeled as "Other Charges"
   - Charges explicitly labeled as "Other Cost"
   - Charges explicitly labeled as "Other Costs"
   DO NOT include any other types of charges in this field
"""

    user_prompt = f"Extract all required fields from the following utility bill text:\n\n{text}\n\nRespond with valid JSON only."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Using GPT-4 for better extraction accuracy
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"}  # Ensure JSON response
        )
        message_content = response.choices[0].message.content.strip()
        logger.debug(f"LLM raw response: {message_content}")
    except Exception as e:
        logger.error(f"Error during LLM API call: {e}")
        raise

    try:
        data = json.loads(message_content)
        
        # Handle nested structure if present
        if "basic_information" in data:
            # Merge basic_information into top level
            data.update(data.pop("basic_information"))
        
        # Convert string dates to datetime objects using safe_parse_date
        if data.get('bill_date'):
            data['bill_date'] = safe_parse_date(data['bill_date'])
        if data.get('due_date'):
            data['due_date'] = safe_parse_date(data['due_date'])
        
        # Process meter data
        if 'meters' in data:
            for meter in data['meters']:
                if meter.get('previous_read_date'):
                    meter['previous_read_date'] = safe_parse_date(meter['previous_read_date'])
                if meter.get('read_date'):
                    meter['read_date'] = safe_parse_date(meter['read_date'])

        bill_data = BillData(**data)
        logger.debug(f"Successfully created BillData instance: {bill_data}")
        return bill_data
        
    except Exception as e:
        logger.error(f"Error processing LLM response: {e}")
        logger.error(f"Raw LLM response: {message_content}")
        raise ValueError(f"Error processing LLM response: {e}")

    return bill_data


if __name__ == "__main__":
    import asyncio
    pdf_file = "018.02.17.25.768217.pdf"  # modify this path as needed
    bill_data = asyncio.run(llm_extract_data_from_pdf(pdf_file))
    print(bill_data.model_dump_json(indent=2)) 