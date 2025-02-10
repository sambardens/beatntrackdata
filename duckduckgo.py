import re
import time
import random
import traceback
import os
import logging
from urllib.parse import quote

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# User agent rotation
from fake_useragent import UserAgent

# Custom regex functions
from regex import get_postcode_regex, get_phone_regex, get_patterns_for_country

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_driver():
    """Initialize Chrome driver with Streamlit cloud compatibility"""
    ua = UserAgent()
    chrome_options = Options()
    chrome_options.add_argument(f'user-agent={ua.random}')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--memory-pressure-off')
    chrome_options.add_argument('--single-process')  # Reduce memory usage
    
    # Add specific Streamlit cloud settings
    if os.getenv('STREAMLIT_RUNTIME'):
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
    
    try:
        if os.getenv('STREAMLIT_RUNTIME'):
            # Streamlit Cloud environment
            chrome_options.binary_location = "/usr/bin/chromium-browser"
            service = Service('/usr/bin/chromedriver')
        else:
            # Local environment
            service = Service(ChromeDriverManager().install())
        
        driver = webdriver.Chrome(
            service=service,
            options=chrome_options
        )
        return driver
    except Exception as e:
        print(f"Driver initialization error: {str(e)}")
        traceback.print_exc()
        # Fallback to direct ChromeDriver
        try:
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except Exception as e2:
            print(f"Fallback initialization error: {str(e2)}")
            traceback.print_exc()
            raise

def extract_address_from_results(driver):
    """Extract address information from DuckDuckGo search results"""
    results = driver.find_elements(By.CLASS_NAME, "result__body")
    text = "\n".join(result.text for result in results)
    return text

def get_address_from_duckduckgo(business_name, country="United Kingdom"):
    # Add random delay between requests
    time.sleep(random.uniform(2, 5))
    driver = None
    try:
        logger.info(f"Starting DuckDuckGo search for: {business_name}")
        driver = initialize_driver()
        
        # Increase timeouts for Streamlit environment
        wait = WebDriverWait(driver, 20)  # Increased from default
        driver.set_page_load_timeout(30)
        
        search_query = f"{business_name} {country} address contact"
        url = f"https://duckduckgo.com/?q={quote(search_query)}"
        
        logger.info(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for results with explicit logging
        try:
            results = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "result__body")))
            logger.info("Search results loaded successfully")
        except TimeoutException:
            logger.error("Timeout waiting for search results")
            return None
            
        # Extract and validate address
        address_data = extract_address_from_results(driver)
        
        if not address_data:
            logger.warning("No address found in results")
            return None
            
        # Validate extracted data
        if not any(address_data.values()):
            logger.warning("Address extracted but all fields are empty")
            return None
            
        logger.info(f"Successfully found address: {address_data}")
        return address_data
        
    except Exception as e:
        logger.error(f"Error in DuckDuckGo search: {str(e)}")
        traceback.print_exc()
        return None
        
    finally:
        if driver:
            try:
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
