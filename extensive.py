import re
from regex import get_address_patterns

def get_patterns_for_country(country_code):
    """Return address patterns for a specific country."""
    patterns = {
        "GB": {
            "street_indicators": ['street', 'road', 'avenue', 'lane', 'drive', 'way', 'plaza', 'boulevard', 'alley', 'route'],
            "building_indicators": ['building', 'suite', 'unit', 'floor', 'apt', 'apartment', 'office', 'room', 'house', 'tower', 'center', 'centre']
        }
    }
    return patterns.get(country_code, patterns["GB"])

def validate_postcode(postcode, country_code):
    """Validate postcode format for different countries."""
    if not postcode:
        return False
    # Basic validation - can be extended for different country formats
    return postcode.strip()

def is_valid_address(text, postcode, country_code="GB"):
    """Enhanced multi-country address validation with full postcode check"""
    print(f"Validating address: {text} with postcode: {postcode} in {country_code}")
    if not text or not postcode:
        print("Text or postcode is empty")
        return False

    # Get country-specific patterns
    patterns = get_patterns_for_country(country_code)
    # Get patterns from regex.py
    patterns = get_address_patterns().get(country_code, get_address_patterns()["GB"])
    
    # Get country-specific patterns
    address_patterns = get_address_patterns()
    street_indicators = address_patterns[country_code]["street_indicators"]
    building_indicators = patterns.get("building_indicators", [
        'building', 'suite', 'unit', 'floor', 'apt', 'apartment',
        'office', 'room', 'house', 'tower', 'center', 'centre'
    ])

    valid_postcode = validate_postcode(postcode, country_code)
    # New rule: full postcode must contain a space (e.g. "LA2 9AN")
    if not valid_postcode or " " not in valid_postcode.strip():
        print("Invalid full postcode format.")
        return False

    if len(text.split()) < 4:
        return False

    has_street = any(f" {indicator.lower()} " in f" {text.lower()} " for indicator in street_indicators)
    has_number = bool(re.search(r'\b\d+\b', text))
    has_building = any(f" {indicator.lower()} " in f" {text.lower()} " for indicator in building_indicators)
    has_location_identifier = has_number or has_building
    contains_full_postcode = valid_postcode.upper() in text.upper()

    if not has_street:
        print("Missing street indicator")
    if not has_location_identifier:
        print("Missing location identifier (number or building)")
    if not contains_full_postcode:
        print("Does not contain full postcode")

    is_valid = has_street and has_location_identifier and contains_full_postcode
    print(f"Address is valid: {is_valid}")
    return is_valid
