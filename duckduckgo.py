import re
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# Import regex functions from regex.py (ensure this file exists and exports them)
from regex import get_postcode_regex, get_phone_regex

def get_address_from_duckduckgo(name):
    """
    Searches DuckDuckGo for "<name> address" and scrapes all text from results.
    """
    query = f"{name} address"
    search_url = f"https://duckduckgo.com/?q={query}"
    
    chrome_options = Options()
    # Modified Chrome options to handle GPU/graphics errors
    chrome_options.add_argument("--headless=new")  # Use new headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gl-drawing-for-tests")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"Searching DuckDuckGo for: {query}")
        driver.get(search_url)
        
        # Wait for any content to load
        driver.implicitly_wait(5)
        
        # Get all text from the page
        body_text = driver.find_element(By.TAG_NAME, "body").text
        print("Raw page text:")
        print("-" * 50)
        print(body_text[:1000])  # Print first 1000 chars for debugging
        print("-" * 50)
        
        return body_text
        
    except Exception as e:
        print(f"Error during DuckDuckGo search: {str(e)}")
        traceback.print_exc()
        return ""
        
    finally:
        try:
            if 'driver' in locals():
                driver.quit()
        except:
            pass

def extract_companies_house_data(text):
    """Extract address data specifically from Companies House format text"""
    ch_pattern = r"[Rr]egistered\s+office\s+address\s*:?\s*([^\.]+?(?:[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}))"
    ch_match = re.search(ch_pattern, text)
    if (ch_match):
        addr_text = ch_match.group(1).strip()
        return addr_text
    return None

def get_address_and_phone_from_duckduckgo(name, country_selected):
    """Returns data in a format compatible with main processing"""
    address_text = get_address_from_duckduckgo(name)
    if not address_text:
        return {}, []
    
    # Get patterns from regex.py
    from regex import get_patterns_for_country
    patterns = get_patterns_for_country(country_selected)
    postcode_pattern = patterns["postcode"]
    phone_pattern = patterns["phone"]
    
    # First try Companies House format
    companies_house_addr = extract_companies_house_data(address_text)
    if companies_house_addr:
        address_lines = [line.strip() for line in companies_house_addr.split(',')]
        postcode = ""
        if postcode_pattern:
            postcode_match = re.search(postcode_pattern, companies_house_addr)
            if postcode_match:
                postcode = postcode_match.group(0).strip()
        
        address_dict = {
            "Full address": ", ".join(address_lines),
            "Address line 1": address_lines[0] if len(address_lines) > 0 else "",
            "Address line 2": "",
            "City": "London" if any("london" in line.lower() for line in address_lines) else "",
            "County": "",
            "Post code": postcode
        }
        
        # Update Full address to include postcode if not already present
        if postcode and postcode not in address_dict["Full address"]:
            address_dict["Full address"] = f"{address_dict['Full address']}, {postcode}"
        
        return address_dict, []
    
    # If no Companies House data, continue with existing logic
    # NEW: More flexible address block detection
    best_address = []
    for line in address_text.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Look for lines containing the business name or address indicators
        name_parts = name.lower().split()
        if any(part in line.lower() for part in name_parts) or \
           any(word in line.lower() for word in ['street', 'road', 'avenue', 'lane']):
            # Found potential address start
            address_block = [line]
            line_count = 0
            
            # Collect following lines that look like address components
            for next_line in address_text.splitlines()[address_text.splitlines().index(line) + 1:]:
                next_line = next_line.strip()
                if not next_line or len(next_line) > 100:  # Skip empty or very long lines
                    continue
                    
                # Add line if it looks like an address component
                if any(word in next_line.lower() for word in ['street', 'road', 'london', 'uk', 'united kingdom']) or \
                   (postcode_pattern and re.search(postcode_pattern, next_line)):
                    address_block.append(next_line)
                    line_count += 1
                    if line_count >= 3:  # Stop after collecting 3 address lines
                        break
                else:
                    break
                    
            if len(address_block) >= 2:  # Must have at least 2 lines
                best_address = address_block
                break
    
    # Build address dictionary
    address_dict = {
        "Full address": ", ".join(best_address) if best_address else "",
        "Address line 1": best_address[0] if best_address else "",
        "Address line 2": best_address[1] if len(best_address) > 1 else "",
        "City": "London" if any("london" in line.lower() for line in best_address) else "",
        "County": "",
        "Post code": ""
    }
    
    # Extract postcode if pattern available
    if postcode_pattern:
        for line in best_address:
            postcode_match = re.search(postcode_pattern, line)
            if postcode_match:
                address_dict["Post code"] = postcode_match.group(0).strip()
                break
    
    # Extract phones (existing code)
    phones = []
    if phone_pattern:
        phone_matches = re.findall(phone_pattern, address_text)
        for match in phone_matches:
            if isinstance(match, tuple):
                phone = next((p for p in match if p), '')
            else:
                phone = match
            if phone.strip():
                phones.append(phone.strip())
    
    print(f"DuckDuckGo found address: {address_dict}")
    print(f"DuckDuckGo found phones: {phones}")
    
    return address_dict, phones
