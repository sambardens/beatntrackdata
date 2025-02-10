import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()  # Ensure environment variables are loaded

def is_postcode_valid(postcode):
    # Modified regex: require exactly one space, ensuring proper full postcode (e.g. "LA2 9AN")
    import re
    pattern = re.compile(r'^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$', re.I)
    return bool(postcode and pattern.match(postcode.strip()))

def thorough_azure_lookup(entry):
    """Perform an Azure lookup using only Name, (City/State) and Country.
    If postcode is already valid, no lookup is performed."""
    if is_postcode_valid(entry.get("Post code", "")):
        return entry

    azure_key = os.getenv("AZURE_MAPS_KEY")
    if not azure_key:
        print("ERROR: Missing AZURE_MAPS_KEY environment variable.")
        return entry

    azure_url = "https://atlas.microsoft.com/search/address/json"
    
    # Use a simple cache mechanism if needed
    cache_key = f"{entry.get('Name', '')}-{entry.get('Country', '')}"
    if hasattr(thorough_azure_lookup, '_cache') and cache_key in thorough_azure_lookup._cache:
        return thorough_azure_lookup._cache[cache_key]

    # NEW: Build query from only Name, City/State, and Country.
    name = entry.get("Name", "").strip() or entry.get("Business name", "").strip()
    # Use City if available; otherwise, try State.
    location = entry.get("City", "").strip() or entry.get("State", "").strip()
    # Country always comes from the dropdown (or default to 'United Kingdom')
    country = entry.get("Country", "").strip() or "United Kingdom"
    
    query_parts = []
    if name:
        query_parts.append(name)
    if location:
        query_parts.append(location)
    query_parts.append(country)
    query = ", ".join(query_parts)
    
    # Set countrySet based solely on the country provided.
    params_country = "GB" if country.lower() in ["uk", "united kingdom", "great britain"] else entry.get("Country code", "GB")
    
    params = {
        "api-version": "1.0",
        "query": query,
        "limit": 1,
        "typeahead": True,
        "language": "en-GB",
        "countrySet": params_country
    }

    try:
        print(f"Azure lookup query: {query}")
        r = requests.get(azure_url, params=params, timeout=10, headers={"Subscription-Key": azure_key})
        print("Azure lookup status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                result = results[0]
                address = result.get("address", {})
                score = result.get("score", 0)
                freeform = address.get("freeformAddress", "").strip()
                print(f"Azure returned freeformAddress: {freeform} (score: {score})")
                if len(freeform.split()) >= 3 and score > 0.4:
                    entry["Full address"] = freeform
                    if address.get("postalCode"):
                        entry["Post code"] = address["postalCode"].strip()
                    # Removed assignment of extra field "Street" to enforce schema.
                    if address.get("locality"):
                        entry["City"] = address["locality"].strip()
                    if address.get("countrySubdivision"):
                        entry["Country"] = entry.get("Country", address["countrySubdivision"].strip())
                        entry["Country code"] = entry.get("Country code", params_country)
                    print("Azure fallback succeeded:", entry)
                else:
                    print(f"Azure lookup returned insufficient address info (score: {score})")
                return entry
            else:
                print("Azure lookup returned no results.")
        else:
            print("Azure lookup failed with status code:", r.status_code)
    except Exception as e:
        print("Azure lookup exception:", e)
    
    print("Returning entry without changes:", entry)
    if not hasattr(thorough_azure_lookup, '_cache'):
        thorough_azure_lookup._cache = {}
    thorough_azure_lookup._cache[cache_key] = entry

    return entry

def run_azure_fallback(df, i):
    print(f"Running Azure fallback for row {i}")
    # ...existing fallback logic can be added here...

# ...existing or additional helper functions...
