# gpt_helpers.py

import json
import openai
import re
import pandas as pd
from typing import Dict, List
import logging

# Set up logging at the top of the file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Global Prompt Constants ---

ADDRESS_PROMPT = """Extract the full postal address from the text below. The text may contain multiple sections separated by '====='.
Pay special attention to multi-line addresses and combine address components intelligently.

For example, if you see a pattern like this:
Studio Name
Street Number Street Name
Area/District
City Postcode

You should format it as:
Address line 1: "Studio Name, Street Number Street Name"
Address line 2: "Area/District"

Guidelines:
1. If there are multiple address lines, combine the venue/building name with the street address in Address line 1.
2. Use Address line 2 for additional location details (area, district, floor, etc.).
3. Make sure to capture the full postcode and city.
4. For UK addresses, always use "GB" as the country code, not "UK".
5. Ensure all components are properly identified and none are missed.

Return a JSON object with exactly these fields:
{
  "Full address": "Complete address as a single comma-separated string",
  "Address line 1": "Building/Venue name + Street address",
  "Address line 2": "Additional location details or empty string",
  "City": "City/Town name",
  "County": "County/Region or empty string",
  "Country": "Full country name",
  "Post code": "Full postcode",
  "Country code": "Two-letter ISO code (GB for UK)"
}

Example input:
"RAK STUDIOS
42-48 Charlbert Street,
St Johns Wood,
London NW8 7BU"

Should return:
{
  "Full address": "RAK STUDIOS, 42-48 Charlbert Street, St Johns Wood, London, NW8 7BU, United Kingdom",
  "Address line 1": "RAK STUDIOS, 42-48 Charlbert Street",
  "Address line 2": "St Johns Wood",
  "City": "London",
  "County": "",
  "Country": "United Kingdom",
  "Post code": "NW8 7BU",
  "Country code": "GB"
}

Now, analyze this text and extract the address:
"""

NAME_PROMPT = """You have a short site or listing description. 
Try to guess the name of the site or listing from the text. 
Return just the name, or an empty string if not found.

Text:
"""

CITY_COUNTRY_PROMPT = """Based on the text below, try to extract city and country if they appear. 
Return JSON with keys: "City", "Country". If you cannot find them, leave them empty.

Text:
"""

CONTACT_PROMPT = """Extract all valid email addresses and phone numbers from the text below.
Pay special attention to:
1. International phone formats
2. Local phone formats (especially UK and US)
3. Email addresses that might be obscured (e.g., 'at' instead of @)

Return a JSON object with these fields:
{
    "emails": ["email1@domain.com", "email2@domain.com"],
    "phones": ["+44123456789", "020 7123 4567"]
}

Guidelines:
1. Format UK phone numbers consistently (+44 or 0 prefix)
2. Clean and validate email addresses
3. Remove duplicates
4. Exclude obviously invalid entries
5. Handle international formats appropriately

Text:
"""

# --- GPT Description Generation ---

def generate_gpt_description(text):
    """
    Generate a concise and engaging description for a music map listing.
    The description should be around 100 words and highlight the most interesting
    and relevant details. (Addresses are excluded.)
    """
    if not text or not text.strip():
        logging.warning("Empty text provided to generate_gpt_description")
        return ""

    logging.info(f"Generating description for text of length: {len(text)}")

    prompt = (
        "You are generating descriptions for a music map website. "
        "Summarize the following content in around 100 words, focusing on the most interesting "
        "and relevant details about this venue, artist, or music-related service. "
        "Do NOT include addresses, as those will be shown separately. "
        "Highlight key features such as music styles, history, unique offerings, events, or reputation. "
        "Keep it engaging, clear, and informative:\n\n" +
        text +
        "\n\nMusic Map Description:"
    )
    
    try:
        logging.info("Sending request to OpenAI API for description generation...")
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.0,
        )
        description = response.choices[0].message.content.strip()
        logging.info(f"Generated description (first 50 chars): {description[:50]}...")
        return description
    except Exception as e:
        logging.error(f"OpenAI Error in generate_gpt_description: {str(e)}", exc_info=True)
        return f"(OpenAI Error: {e})"

# --- GPT-based Address Extraction ---

def extract_address_fields_gpt(text, soup=None):
    """
    Uses ChatGPT to extract a structured postal address from the provided text.
    Combines (or falls back to) additional context if needed.
    Returns a dictionary with the extracted fields if successful;
    otherwise, returns an empty dictionary.
    """
    # (In a full application you might combine additional footer or context here.)
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": ADDRESS_PROMPT + text}
            ],
            max_tokens=500,
            temperature=0.0,
        )
        raw_json = response.choices[0].message.content.strip()
        result = json.loads(raw_json) if raw_json else {}
        return result if result.get("Full address") else {}
    except Exception as e:
        print(f"Address extraction error: {e}")
        return {}

# --- GPT-based Name Extraction ---

def extract_name_gpt(text):
    """
    Uses ChatGPT to guess the name of a site or listing from a short description.
    Returns the extracted name as a string.
    """
    prompt = NAME_PROMPT + text + "\nName:"
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""

# --- GPT-based City/Country Extraction ---

def extract_city_country_gpt(text):
    """
    First attempts to extract the city and country using GeoText.
    If not found, falls back to using ChatGPT.
    Returns a dictionary with keys "City" and "Country".
    """
    try:
        from geotext import GeoText
        places = GeoText(text)
        if places.cities or places.countries:
            return {"City": places.cities[0] if places.cities else "",
                    "Country": places.countries[0] if places.countries else ""}
    except Exception as e:
        print(f"GeoText extraction error: {e}")
    
    prompt = CITY_COUNTRY_PROMPT + text + "\n\nJSON:"
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.0,
        )
        raw_json = response.choices[0].message.content.strip()
        return json.loads(raw_json)
    except Exception as e:
        print(f"City/Country extraction error: {e}")
        return {}

# Add after other extraction functions

def extract_contacts_gpt(text: str) -> Dict[str, List[str]]:
    """
    Uses GPT to extract contact information from text.
    Returns dict with 'emails' and 'phones' lists.
    """
    if not text or not text.strip():
        logging.warning("Empty text provided to extract_contacts_gpt")
        return {"emails": [], "phones": []}

    logging.info(f"Extracting contacts from text of length: {len(text)}")
    
    try:
        logging.info("Sending contact extraction request to OpenAI API...")
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": CONTACT_PROMPT + text}
            ],
            max_tokens=500,
            temperature=0.0,
        )
        raw_json = response.choices[0].message.content.strip()
        logging.debug(f"Raw JSON response: {raw_json[:200]}...")
        
        result = json.loads(raw_json) if raw_json else {}
        
        contacts = {
            "emails": list(set(result.get("emails", []))),
            "phones": list(set(result.get("phones", [])))
        }
        
        logging.info(f"Extracted {len(contacts['emails'])} emails and {len(contacts['phones'])} phones")
        return contacts
        
    except Exception as e:
        logging.error(f"Contact extraction error: {str(e)}", exc_info=True)
        return {"emails": [], "phones": []}

def merge_contacts(existing_contacts: Dict[str, List[str]], 
                  new_contacts: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Merges two contact dictionaries, removing duplicates.
    """
    return {
        "emails": list(set(existing_contacts.get("emails", []) + new_contacts.get("emails", []))),
        "phones": list(set(existing_contacts.get("phones", []) + new_contacts.get("phones", [])))
    }

# --- Helper Functions ---

def fix_country_code(row):
    """
    If 'Country code' is missing or incorrect in a row, attempts to fix it based on the 'Country' field.
    """
    country_str = (row['Country'] if pd.notnull(row['Country']) else "").strip().lower()
    ccode_str = (row['Country code'] if pd.notnull(row['Country code']) else "").strip().upper()
    if ccode_str and ccode_str != "UK":
        return ccode_str
    if country_str in ("united kingdom", "uk", "great britain", "england", "scotland", "wales"):
        return "GB"
    elif country_str in ("united states", "usa", "us", "america"):
        return "US"
    return ccode_str or ""
