import re

def get_patterns_for_country(country):
    """
    Returns regex patterns for address validation based on country.
    """
    patterns = {
        "UK": {
            "phone": r"\b(?:(?:\+44)|(?:0))(?:\d\s?){9,10}\b",
            "postcode": r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b",
            "address_keywords": r"\b(?:street|road|avenue|lane|drive|way|court|close)\b"
        },
        "US": {
            "phone": r"\b(?:\+1|1?)[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
            "postcode": r"\b\d{5}(?:-\d{4})?\b",
            "address_keywords": r"\b(?:street|road|avenue|lane|drive|way|court|close)\b"
        }
    }
    return patterns.get(country.upper(), patterns["UK"])

def quick_extract_address(text, country="UK"):
    """
    Enhanced quick_extract_address function using country-specific regex patterns.
    """
    segments = text.splitlines()
    # Retrieve regex patterns for the given country
    patterns = get_patterns_for_country(country)
    phone_pattern = patterns.get("phone", "")
    postcode_pattern = patterns.get("postcode", "")
    print(f"Debug: For country '{country}', phone_pattern: {phone_pattern}, postcode_pattern: {postcode_pattern}")
    # Compile regex for postcode and keywords
    postcode_regex = re.compile(postcode_pattern, re.IGNORECASE)
    address_keyword_regex = re.compile(patterns.get("address_keywords", ""), re.IGNORECASE)
    candidate_blocks = []
    # Iterate segments for a candidate address containing a valid postcode
    for i, segment in enumerate(segments):
        if postcode_regex.search(segment):
            block_segments = []
            # Collect prior segments if needed
            for j in range(max(0, i - 2), i):
                prev_seg = segments[j].strip()
                if prev_seg:
                    block_segments.append(prev_seg)
            # Append next segment if exists
            block_segments.append(segment.strip())
            if i < len(segments)-1:
                next_seg = segments[i + 1].strip()
                if next_seg:
                    block_segments.append(next_seg)
            candidate = ", ".join(block_segments)
            candidate_blocks.append((candidate, country))

    def is_valid_candidate(candidate, ctry):
        candidate_lower = candidate.lower()
        has_digit = bool(re.search(r'\d+', candidate))
        has_keyword = bool(address_keyword_regex.search(candidate_lower))
        if ctry.upper() in ("UK", "GB"):
            return has_digit
        elif ctry.upper() in ("US", "USA", "UNITED STATES"):
            return has_digit and has_keyword
        else:
            return has_digit and ("," in candidate)
        return True  # example placeholder

    valid_candidates = [c for c, ctry in candidate_blocks if is_valid_candidate(c, ctry)]
    if valid_candidates:
        best_candidate = max(valid_candidates, key=lambda b: len(b.split()))
        return best_candidate
    elif candidate_blocks:
        best_candidate = max(candidate_blocks, key=lambda t: len(t[0].split()))[0]
        return best_candidate
    return None  # final return