# regex.py

import re
from countries import get_country_code  # We import our helper that fetches alpha2 from a country name

################################################################################
# Base Regex Patterns for Specific Countries
################################################################################

# -- Canada
CANADA_POSTCODE_REGEX = re.compile(
    r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d\b",
    re.IGNORECASE
)
CANADA_PHONE_REGEX = re.compile(
    r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
    re.IGNORECASE
)

# -- USA
US_ZIPCODE_REGEX = re.compile(r"\b\d{5}(?:-\d{4})?\b")
US_PHONE_REGEX = re.compile(r"\+?1?\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

# -- UK
UK_POSTCODE_REGEX = re.compile(r"(?i)([A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})")
UK_PHONE_REGEX = re.compile(
    r"((\+44\s?(\(0\))?)|0)\s?\(?\d{2,5}\)?[\s.-]?\d{2,5}[\s.-]?\d{2,6}",
    re.IGNORECASE
)

# -- Australia
AU_POSTCODE_REGEX = re.compile(r"\b(0[2-9]\d{2}|[1-9]\d{3})\b")
AU_PHONE_REGEX = re.compile(
    r"(\+?61[\s.-]?)?\(?(0?[2-578])\)?[\s.-]?\d{4}[\s.-]?\d{4}",
    re.IGNORECASE
)

# -- New Zealand
NZ_POSTCODE_REGEX = re.compile(r"\b(0\d{2}|[1-9]\d{2})\d\b")  # simplistic 4-digit approach
NZ_PHONE_REGEX = re.compile(
    r"(\+?64[\s.-]?)?\(?(0?\d{1,2})\)?[\s.-]?\d{3,4}[\\s.-]?\d{3,4}",
    re.IGNORECASE
)

################################################################################
# Broader Regional Fallback Patterns
################################################################################

# -- European Union (Broad fallback)
EU_POSTCODE_REGEX = re.compile(
    r"""
    \b(
        \d{4,5}         # e.g., 4 or 5-digit numeric (many EU states)
        |
        [A-Z]\d[A-Z0-9]? \s? \d[A-Z]{2}  # partial overlap with UK/EIR
        |
        \d{3}\s?\d{2}   # just in case
    )\b
    """,
    re.IGNORECASE | re.VERBOSE
)
EU_PHONE_REGEX = re.compile(
    r"""
    (
      (\+?\d{2,3})      # e.g. +33, +49, +34
      [\s.-]?\(?\d+\)?  # optional area code
      [\s.-]?\d+        # local
      ([\s.-]?\d+)*     # more local
    )
    |
    (0\d{2,4}[\s.-]?\d{2,7}([\s.-]?\d{1,5})?)
    """,
    re.IGNORECASE | re.VERBOSE
)

# -- Asia (Broad fallback)
ASIA_POSTCODE_REGEX = re.compile(r"\b[0-9A-Za-z]{3,7}\b")  # broad 3–7 alphanumeric
ASIA_PHONE_REGEX = re.compile(
    r"""
    (
      (\+?\d{2,4})
      [\s.-]?\(?\d+\)? 
      [\s.-]?\d+ 
      ([\s.-]?\d+)* 
    )
    |
    (0\d{2,4}[\s.-]?\d{3,7}([\s.-]?\d{1,5})?)
    """,
    re.IGNORECASE | re.VERBOSE
)

# -- Africa (Broad fallback)
#   Many African countries use phone formats that start with +2xx or 0xx.
#   Postcodes can be numeric or nonexistent. We'll do a broad numeric fallback for now.
AFRICA_POSTCODE_REGEX = re.compile(r"\b\d{4,5}\b")  # e.g., 4 or 5 digits, very rough
AFRICA_PHONE_REGEX = re.compile(
    r"""
    (
        \+?2\d{1,2}[\s.-]?\d{3,}([\s.-]?\d{2,})*
    )
    |
    (0\d{2,4}[\s.-]?\d{3,7}([\s.-]?\d{1,5})?)
    """,
    re.IGNORECASE | re.VERBOSE
)

# -- Middle East (Broad fallback)
#   Many Middle Eastern nations have +9XX or +97X codes, but we keep it broad.
MIDEAST_POSTCODE_REGEX = re.compile(r"\b\d{4,5}\b")  # again, quite approximate
MIDEAST_PHONE_REGEX = re.compile(
    r"""
    (
        (\+?9\d{1,2})[\s.-]?\(?\d+\)?[\s.-]?\d+([\s.-]?\d+)* 
    )
    |
    (0\d{2,4}[\\s.-]?\d{3,7}([\s.-]?\d{1,5})?)
    """,
    re.IGNORECASE | re.VERBOSE
)

# -- Latin America (Broad fallback)
LATAM_POSTCODE_REGEX = re.compile(r"\b\d{4,5}\b")  # many LA countries do 4-5 digit codes
LATAM_PHONE_REGEX = re.compile(
    r"""
    (
      (\+?5\d{1,2})[\s.-]?\(?\d+\)?[\s.-]?\d+([\s.-]?\d+)* 
    )
    |
    (0\d{2,4}[\s.-]?\d{3,7}([\s.-]?\d{1,5})?)
    """,
    re.IGNORECASE | re.VERBOSE
)

# -- Fallback (truly anything)
FALLBACK_POSTCODE_REGEX = re.compile(r".*")
FALLBACK_PHONE_REGEX = re.compile(r".*")

################################################################################
# Address Keywords (Optional usage)
################################################################################
DEFAULT_ADDRESS_KEYWORDS = [
    "street", "st.", "road", "rd.", "lane", "ln.",
    "avenue", "ave", "drive", "dr", "postal code"
]

ADDRESS_KEYWORDS_REGEX = re.compile(r"(street|road|avenue|lane)", re.IGNORECASE)

################################################################################
# Primary Country-Specific Dictionary (By alpha2 Code)
################################################################################

COUNTRY_REGEX = {
    "CA": {
        "postcode": CANADA_POSTCODE_REGEX,
        "phone": CANADA_PHONE_REGEX,
        "address_keywords": DEFAULT_ADDRESS_KEYWORDS + ["province"]
    },
    "US": {
        "postcode": US_ZIPCODE_REGEX,
        "phone": US_PHONE_REGEX,
        "address_keywords": DEFAULT_ADDRESS_KEYWORDS + ["zip code", "zipcode", "state", "highway"]
    },
    "GB": {
        "postcode": UK_POSTCODE_REGEX,
        "phone": UK_PHONE_REGEX,
        "address_keywords": DEFAULT_ADDRESS_KEYWORDS + ["postcode", "post code", "house", "close"]
    },
    "AU": {
        "postcode": AU_POSTCODE_REGEX,
        "phone": AU_PHONE_REGEX,
        "address_keywords": DEFAULT_ADDRESS_KEYWORDS + ["post code"]
    },
    "NZ": {
        "postcode": NZ_POSTCODE_REGEX,
        "phone": NZ_PHONE_REGEX,
        "address_keywords": DEFAULT_ADDRESS_KEYWORDS + ["post code"]
    },
    # Add more individually if you want strict patterns for other countries
}

################################################################################
# Region Groupings: alpha2 sets
################################################################################

EU_ALPHA2_CODES = {
    # Partial list only
    "FR", "DE", "IT", "ES", "NL", "BE", "PT", "SE",
    "PL", "IE", "DK", "FI", "AT", "CZ", "HU", "RO",
    "SK", "SI", "LV", "LT", "EE", "BG", "HR", "GR", "LU"
}

ASIA_ALPHA2_CODES = {
    # Partial list only
    "CN", "IN", "ID", "PK", "BD", "JP", "VN", "PH",
    "TH", "MY", "SG", "KR", "KH", "LK", "NP"
}

AFRICA_ALPHA2_CODES = {
    # Partial list only
    "ZA", "NG", "EG", "DZ", "MA", "KE", "GH", "TZ",
    "UG", "CM", "CI", "SN", "SD", "ET", "ZM", "ZW",
    "NA", "BW", "RW", "MZ", "MG"
}

MIDDLE_EAST_ALPHA2_CODES = {
    # Partial list only
    "AE", "SA", "KW", "QA", "BH", "OM", "JO", "LB",
    "SY", "IQ", "IR", "YE", "IL", "PS"
}

LATIN_AMERICA_ALPHA2_CODES = {
    # Partial list only
    "MX", "BR", "AR", "CO", "CL", "PE", "VE", "EC",
    "GT", "CU", "BO", "PY", "UY", "SV", "HN", "CR",
    "PA", "DO", "NI"
}

################################################################################
# Region-level Dictionaries
################################################################################

EU_REGEX_DICT = {
    "postcode": EU_POSTCODE_REGEX,
    "phone": EU_PHONE_REGEX,
    "address_keywords": DEFAULT_ADDRESS_KEYWORDS + [
        "platz", "strasse", "straße", "boulevard", "blvd"
    ]
}

ASIA_REGEX_DICT = {
    "postcode": ASIA_POSTCODE_REGEX,
    "phone": ASIA_PHONE_REGEX,
    "address_keywords": DEFAULT_ADDRESS_KEYWORDS + [
        "district", "city", "prefecture"
    ]
}

AFRICA_REGEX_DICT = {
    "postcode": AFRICA_POSTCODE_REGEX,
    "phone": AFRICA_PHONE_REGEX,
    "address_keywords": DEFAULT_ADDRESS_KEYWORDS + [
        "province", "region", "town"
    ]
}

MIDEAST_REGEX_DICT = {
    "postcode": MIDEAST_POSTCODE_REGEX,
    "phone": MIDEAST_PHONE_REGEX,
    "address_keywords": DEFAULT_ADDRESS_KEYWORDS + [
        "district", "governate", "town"
    ]
}

LATAM_REGEX_DICT = {
    "postcode": LATAM_POSTCODE_REGEX,
    "phone": LATAM_PHONE_REGEX,
    "address_keywords": DEFAULT_ADDRESS_KEYWORDS + [
        "estado", "departamento", "municipio", "colonia"
    ]
}

OTHER_REGEX_DICT = {
    "postcode": FALLBACK_POSTCODE_REGEX,
    "phone": FALLBACK_PHONE_REGEX,
    "address_keywords": []
}

################################################################################
# Main Function
################################################################################

def get_patterns_for_country(user_selected_country: str):
    """
    Given a user-selected country name (e.g. "Canada", "Germany", etc.),
    this function:

    1. Fetches the alpha2 code from countries.py (get_country_code).
    2. Returns a dict with "postcode", "phone", and "address_keywords" 
       for that country or a relevant region fallback.
       If no region match, returns the 'OTHER' fallback.

    Example usage:
        patterns = get_patterns_for_country("New Zealand")
        phone_regex = patterns["phone"]
        ...
    """
    alpha2 = get_country_code(user_selected_country)  # e.g., "CA", "US", "GB", etc.

    # 1) If no alpha2 found at all, just do 'Other' fallback
    if not alpha2:
        return OTHER_REGEX_DICT

    # 2) Check if alpha2 is specifically in our COUNTRY_REGEX
    if alpha2 in COUNTRY_REGEX:
        return COUNTRY_REGEX[alpha2]

    # 3) Otherwise, see if alpha2 belongs to one of our region sets
    if alpha2 in EU_ALPHA2_CODES:
        return EU_REGEX_DICT
    
    if alpha2 in ASIA_ALPHA2_CODES:
        return ASIA_REGEX_DICT

    if alpha2 in AFRICA_ALPHA2_CODES:
        return AFRICA_REGEX_DICT

    if alpha2 in MIDDLE_EAST_ALPHA2_CODES:
        return MIDEAST_REGEX_DICT

    if alpha2 in LATIN_AMERICA_ALPHA2_CODES:
        return LATAM_REGEX_DICT

    # 4) If not recognized in any set, fallback to 'Other'
    return OTHER_REGEX_DICT

    if user_selected_country.lower() == "uk":
        patterns["extra_address_pattern"] = r"((?:\d+(?:st|nd|rd|th)\s+Floor,\s+[A-Za-z']+\s+House,\s+\d+\s+Hay's\s+Lane.*))"
    return patterns

def get_postcode_regex(country):
    """Returns the appropriate postcode regex pattern for the given country."""
    patterns = {
        "United Kingdom": r'[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}',
        "GB": r'[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}',
        "UK": r'[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}',
        "United States": r'\d{5}(?:-\d{4})?',
        "US": r'\d{5}(?:-\d{4})?',
        # Add more country patterns as needed
    }
    return patterns.get(country, "")

def get_phone_regex(country):
    """Returns the appropriate phone number regex pattern for the given country."""
    patterns = {
        "United Kingdom": r'(?:\+44|0)(?:\s*\(\s*0?\s*\))?[\s-]*([1-9][\d\s-]{8,})',
        "GB": r'(?:\+44|0)(?:\s*\(\s*0?\s*\))?[\s-]*([1-9][\d\s-]{8,})',
        "UK": r'(?:\+44|0)(?:\s*\(\s*0?\s*\))?[\s-]*([1-9][\d\s-]{8,})',
        "United States": r'(?:\+1|1)?[\s-]?\(?([0-9]{3})\)?[\s-]?([0-9]{3})[\s-]?([0-9]{4})',
        "US": r'(?:\+1|1)?[\s-]?\(?([0-9]{3})\)?[\s-]?([0-9]{3})[\s-]?([0-9]{4})',
        # Add more country patterns as needed
    }
    return patterns.get(country, "")

# Placeholder for regex helper functions if required by the application.
