from openai import OpenAI
from typing import Optional, Dict, Any
import json
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Configure OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are a utility bill data extraction expert. Your task is to extract specific information from utility bill PDFs.
The data should be extracted in a consistent format following these rules:

1. All dates should be in YYYY-MM-DD format
2. All numerical values should be converted to appropriate types (float for money and readings)
3. Boolean fields should be true/false
4. Extract as much information as possible for each meter
5. If a field is not found, leave it as null
6. Be precise and accurate with the extraction
7. For charges categorization:
   - utility_taxes: ONLY include State Tax + Sales Tax + Utility Tax + City Tax
   - utility_charges: Include base charges plus all fees, surcharges, and miscellaneous charges (except taxes and explicit "other charges")
   - supply_charges: Include generation charges, supply service, energy procurement costs
   - supply_taxes: Look for taxes specifically on supply/generation portion of the bill
   - other_charge: ONLY include charges explicitly labeled as "Other Charge", "Other Charges", "Other Cost", or "Other Costs"

The expected fields are:
{
    "account_number": string,
    "bill_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD",
    "balance_forward": float,
    "current_charges": float,
    "late_fee": float,
    "amount_due": float,
    "rebill_adjustment": boolean,
    "meters": [
        {
            "meter_number": string,
            "bill_type": string,  // must be one of: "Water bill", "Telecom bill", "EB bill", "Gas bill"
            "previous_read_date": "YYYY-MM-DD",
            "read_date": "YYYY-MM-DD",
            "previous_reading": float,
            "meter_reading": float,
            "multiplier": float,
            "usage": float,
            "unit": string,
            "estimated": boolean,
            "utility_charges": float,  // Base charges plus all fees and surcharges (except taxes)
                                     // Includes: E911 fees, USF, TRS, regulatory fees, and any
                                     // miscellaneous charges not labeled as "other charge"/"other cost"
            "utility_taxes": float,   // ONLY sum of: State Tax + Sales Tax + Utility Tax + City Tax
            "supply_charges": float,  // Generation charges, supply service, energy procurement costs
                                     // Look in supply/generation section of the bill
            "supply_taxes": float,    // Taxes specifically on supply/generation portion
                                     // Check supply section for associated taxes
            "other_charge": float,    // ONLY include charges explicitly labeled as:
                                     // "Other Charge", "Other Charges", "Other Cost", or "Other Costs"
            "therm_factor": float,
            "adjustment_factor": float,
            "demand": float,
            "kw_actual": float,
            "kw_billed": float,
            "power_factor": float
        }
    ]
}"""

USER_PROMPT = """Extract the utility bill information from the following text. 
Respond ONLY with a JSON object matching the specified format.
Do not include any explanations or additional text.

Text content:
{text}"""

def clean_llm_response(response: str) -> Dict[str, Any]:
    """Clean and parse the LLM response into a proper dictionary."""
    try:
        # Try to parse the response as JSON
        if isinstance(response, str):
            # Remove any markdown code block indicators
            response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(response)
        return response
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing LLM response: {e}")
        raise ValueError(f"Invalid JSON response from LLM: {e}")

async def extract_with_llm(text: str) -> Dict[str, Any]:
    """Extract information from bill text using OpenAI's GPT model."""
    try:
        logger.info("Starting LLM-based extraction")
        
        # Create the chat completion
        response = await client.chat.completions.create(
            model="gpt-4",  # You can also use "gpt-3.5-turbo" for faster, cheaper processing
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(text=text)}
            ],
            temperature=0.1,  # Low temperature for more consistent outputs
            max_tokens=2000
        )
        
        # Extract the response text
        result = response.choices[0].message.content
        logger.debug(f"Raw LLM response: {result}")
        
        # Clean and parse the response
        extracted_data = clean_llm_response(result)
        logger.info("Successfully extracted data using LLM")
        
        return extracted_data
        
    except Exception as e:
        logger.error(f"Error in LLM extraction: {e}")
        raise 