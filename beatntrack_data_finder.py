from geotext import GeoText
import csv
import time
import re
import socket
import requests
import phonenumbers
import pandas as pd
import streamlit as st
import openai
from io import StringIO
from bs4 import BeautifulSoup
from PIL import Image
from urllib.parse import urljoin
from dotenv import load_dotenv
import os
from requests.adapters import HTTPAdapter
import cloudscraper  # Add this import
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import traceback  # Add this import
from playwright.sync_api import sync_playwright  # Add this import

# Define custom styles right after imports
CUSTOM_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

/* Modern container styling */
.stApp {
    background-color: #fdfdfd;
    font-family: 'Poppins', sans-serif;
}

/* Card-like containers */
.css-1r6slb0, .css-12oz5g7 {
    background-color: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    margin: 1rem 0;
}

/* Enhanced Modern Button Styling */
.stButton > button {
    background-color: #FF0151;
    color: white;
    border: none;
    border-radius: 8px;  /* Less rounded corners */
    padding: 0.75rem 2rem;
    font-weight: 500;
    font-family: 'Poppins', sans-serif;
    min-width: 200px;  /* Ensure consistent width */
    height: 45px;      /* Ensure consistent height */
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 14px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(255, 1, 81, 0.1);
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 16px;
    background-color: #FFFFFF; 
}

.stButton > button:active {
    transform: translateY(1px);
    box-shadow: 0 4px 8px rgba(255, 1, 81, 0.2);
}

/* Add a subtle gradient overlay */
.stButton > button::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.1), transparent);
    transform: translateX(-100%);
    transition: transform 0.5s;
}

.stButton > button:hover::before {
    transform: translateX(100%);
}

/* Container for button alignment */
.stButton {
    display: flex;
    justify-content: center;
    margin: 0.5rem 0;
}

/* Modern form inputs */
.stTextInput > div > div > input, .stSelectbox > div > div > div {
    border-radius: 8px;
    border: 2px solid #eee;
    padding: 0.5rem 1rem;
    transition: all 0.3s ease;
}

/* Status messages */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
}

/* Section headers */
h1, h2, h3 {
    color: #FF0151;
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    margin-bottom: 1.5rem;
}

/* Progress and dataframe styling */
.stProgress > div > div > div {
    background-color: #FF0151;
    height: 6px;
    border-radius: 3px;
}

.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
</style>
"""

# Add after imports...

def auto_download_csv(df, prefix=""):
    """Helper function to auto-download CSV files"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{prefix}beatntrack_data_{timestamp}.csv"
    
    # Create copy for saving to handle arrays properly
    df_save = df.copy()
    for col in ["AllImages", "EmailContacts", "PhoneContacts"]:
        if col in df_save.columns:
            df_save[col] = df_save[col].apply(lambda x: "||".join(x) if isinstance(x, list) else str(x))
    
    # Save to StringIO
    output = StringIO()
    df_save.to_csv(output, index=False)
    
    # Create download button
    st.download_button(
        f"Download {prefix.strip()} CSV",
        output.getvalue(),
        file_name=filename,
        mime="text/csv"
    )
    
    # Also save to disk in a 'backups' folder
    os.makedirs("backups", exist_ok=True)
    df_save.to_csv(f"backups/{filename}", index=False)
    print(f"Backup saved to backups/{filename}")

def validate_required_columns(df):
    """Check if DataFrame has minimum required columns"""
    required_cols = [
        "AllImages", "EmailContacts", "PhoneContacts", "ScrapedText",
        "Description", "Error", "Type", "Sub Type", "GigListingURL",
        "Full address", "Address line 1", "Address line 2",
        "City", "County", "Country", "Post code", "Country code",
        "Name", "State"
    ]
    
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}")
        return False
    return True

def initialize_dataframe(df, type_value="", sub_type=""):
    """Initialize DataFrame with required columns and default values"""
    required_cols = [
        "AllImages", "InstagramURL", "FacebookURL", "TwitterURL",
        "LinkedInURL", "YoutubeURL", "TiktokURL", "EmailContacts",
        "PhoneContacts", "ScrapedText", "Description", "Error",
        "Type", "Sub Type", "GigListingURL",
        "Full address", "Address line 1", "Address line 2",
        "City", "County", "Country", "Post code", "Country code",
        "Name", "State"
    ]
    
    # Initialize missing columns
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
            
    # Set Type and Sub Type if provided
    if type_value:
        df["Type"] = type_value
    if sub_type:
        df["Sub Type"] = sub_type
        
    return df

# Load environment variables
load_dotenv()

AZURE_MAPS_KEY = os.getenv("AZURE_MAPS_KEY")
BING_KEY = os.getenv("BING_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_KEY  # Ensure OpenAI key is set

# Hide SSL warnings (optional; not recommended in production)
requests.packages.urllib3.disable_warnings()

# Ensure OpenAI library version is compatible

###################################
# 1. OPENAI CONFIG
###################################

def generate_gpt_description(text):
    """
    Generate a concise and engaging description for a music map listing.
    The description should be around 100 words and highlight the most relevant 
    and interesting details about the venue, artist, or music-related service.
    Avoid including address or location details, as they are displayed elsewhere.
    
    Example: If the text mentions events, history, or unique aspects of the place,
    prioritize those details. Keep it clear, engaging, and informative.

    Returns: A 100-word summary that captures the essence of the listing.
    """
    prompt = (
        "You are generating descriptions for a music map website. "
        "Summarize the following content in around 100 words, focusing on the most interesting "
        "and relevant details about this venue, artist, or music-related service. "
        "Do NOT include addresses, as those will be shown separately. "
        "Highlight key features such as music styles, history, unique offerings, events, or reputation. "
        "Keep it engaging, clear, and informative:\n\n"
        + text
        + "\n\nMusic Map Description:"
    )
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(OpenAI Error: {e})"



#######################################
# 2. HELPER FUNCTIONS
#######################################

def is_valid_contact_text(text):
    """Heuristic check: valid if text contains at least one digit and >3 words."""
    import re
    if text and re.search(r'\d', text) and len(text.split()) > 3:
        return True
    return False

def check_dns(domain):
    try:
        socket.gethostbyname_ex(domain)
        return True
    except socket.gaierror:
        return False

def build_absolute_url(relative_url, base_url):
    if (relative_url.lower().startswith("http") or relative_url.lower().startswith("data:image")):
        return relative_url
    return urljoin(base_url, relative_url)

def try_url_variants(session, base_domain, wait_time=3):
    """
    Enhanced URL fetching with better error handling and multiple attempts
    """
    if base_domain.lower().startswith("www."):
        base_domain = base_domain[4:]

    variants = [
        f"https://www.{base_domain}",
        f"https://{base_domain}",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0"
    }

    last_err = ""
    
    # First try: Regular requests
    for variant in variants:
        try:
            print(f"Trying URL: {variant}")
            # Add a slight delay before request
            time.sleep(wait_time)
            
            resp = session.get(
                variant, 
                headers=headers, 
                timeout=15,  # Increased timeout
                verify=False,
                allow_redirects=True  # Explicitly allow redirects
            )
            
            # Check for various success conditions
            if resp.status_code in [200, 301, 302]:
                print(f"Success with status {resp.status_code} for URL: {variant}")
                return resp, variant, ""
            else:
                print(f"Got status {resp.status_code} for URL: {variant}")
                last_err = f"HTTP {resp.status_code}"
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            print(f"RequestException for URL {variant}: {e}")
            continue

    # Second try: Use cloudscraper if regular requests fail
    try:
        print(f"Attempting with cloudscraper for: {variants[0]}")
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        resp = scraper.get(variants[0], timeout=20)
        if resp.status_code == 200:
            print(f"Cloudscraper success for URL: {variants[0]}")
            return resp, variants[0], ""
    except Exception as e:
        print(f"Cloudscraper error: {str(e)}")
        last_err = str(e)

    # Last resort: External proxy
    try:
        print(f"Using external proxy fallback for URL: {variants[0]}")
        proxy_url = f"https://proxyapp-hjeqhbg2h2c2baay.uksouth-01.azurewebsites.net/proxy?url={variants[0]}"
        resp = requests.get(proxy_url, headers=headers, timeout=15, verify=False)
        if resp.status_code == 200:
            class DummyResponse:
                def __init__(self, text):
                    self.status_code = 200
                    self.text = text
            return DummyResponse(resp.text), variants[0], ""
    except requests.exceptions.RequestException as e:
        last_err = str(e)
        print(f"External Proxy Exception: {e}")
        traceback.print_exc()

    print(f"All attempts failed for URL: {base_domain}")
    return None, "", last_err if last_err else "All attempts failed"


def find_social_links(soup):
    """
    Finds standard social media links (Instagram, Facebook, Twitter/X, LinkedIn, YouTube, TikTok).
    """
    social_links = {
        "instagram_url": None,
        "facebook_url": None,
        "twitter_url": None,
        "linkedin_url": None,
        "youtube_url": None,
        "tiktok_url": None
    }
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href.lower().startswith("http"):
            continue
        lhref = href.lower()
        if "instagram.com" in lhref and "/reel/" not in lhref and social_links["instagram_url"] is None:
            social_links["instagram_url"] = href
        elif "facebook.com" in lhref and social_links["facebook_url"] is None:
            social_links["facebook_url"] = href
        elif ("twitter.com" in lhref or "x.com" in lhref) and social_links["twitter_url"] is None:
            social_links["twitter_url"] = href
        elif "linkedin.com" in lhref and social_links["linkedin_url"] is None:
            social_links["linkedin_url"] = href
        elif "youtube.com" in lhref and social_links["youtube_url"] is None:
            social_links["youtube_url"] = href
        elif "tiktok.com" in lhref and social_links["tiktok_url"] is None:
            social_links["tiktok_url"] = href
    return social_links

def find_emails(text):
    """Enhanced email extraction with more specific patterns"""
    # More comprehensive email patterns
    email_patterns = [
        # Basic email with common boundaries
        r'(?:^|[\s<(\[])([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)(?:$|[\s>)\]])',
        # After label
        r'(?:email|e-?mail|contact|enquiries|info|mail to)[:;\s]*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
        # In mailto: links
        r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
    ]
    
    found_emails = set()
    text = text.replace('\n', ' ')  # Handle line breaks
    
    for pattern in email_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            email = match.group(1) if len(match.groups()) > 0 else match.group(0)
            email = email.strip().lower()
            if '@' in email and '.' in email.split('@')[1]:
                found_emails.add(email)
                print(f"Found email: {email}")
    
    return list(found_emails)

def find_phone_numbers(text):
    """Enhanced phone number extraction with specific UK patterns"""
    uk_patterns = [
        # Common UK formats
        r'(?:tel|phone|t|call|contact|mob)(?:ephone)?[\s:.-]*(?:\+44\s*)?(?:\(0\))?\s*((?:[\d]{4}[\s-]?[\d]{3}[\s-]?[\d]{3})|(?:[\d]{5}[\s-]?[\d]{6}))',
        # Direct number format
        r'(?:\+44|0)(?:\s*\(\s*0?\s*\))?[\s-]*([1-9][\d\s-]{8,})',
        # International format
        r'\+\s*44\s*\(?\s*0?\s*\)?\s*([\d\s-]{10,})',
    ]
    
    formatted_numbers = set()
    text = text.replace('\n', ' ')  # Handle line breaks
    
    for pattern in uk_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            number = match.group(1) if len(match.groups()) > 0 else match.group(0)
            number = re.sub(r'[^\d+]', '', number)  # Clean the number
            
            try:
                if number.startswith('0'):
                    number = '+44' + number[1:]
                elif not number.startswith('+'):
                    number = '+44' + number
                
                # Parse and validate
                parsed = phonenumbers.parse(number, "GB")
                if phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    formatted_numbers.add(formatted)
                    print(f"Found phone: {formatted}")
            except Exception as e:
                print(f"Phone parsing error: {str(e)} for number: {number}")
    
    return list(formatted_numbers)

def try_fetch_image(session, url, proxy_url=None, verify=False):
    """Enhanced image fetching with better validation"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": url
    }
    
    def is_valid_image_url(url):
        """Helper to check if URL likely points to an image"""
        url = url.lower()
        return any(ext in url for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']) and \
               not any(skip in url for skip in ['icon', 'thumb', 'logo', 'favicon', 'avatar', 'small'])
    
    if not is_valid_image_url(url):
        return None
        
    try:
        # Try HEAD first
        try:
            r = session.head(url, headers=headers, timeout=5, verify=False)
            if r.status_code == 200:
                if 'content-length' in r.headers:
                    size = int(r.headers['content-length'])
                    if size > 100000:  # >100KB
                        return (800, 600)
        except:
            pass

        # If HEAD fails, try full GET
        full_url = url if not proxy_url else f"{proxy_url}?url={url}"
        r = session.get(full_url, headers=headers, timeout=10, verify=verify)
        
        if r.status_code == 200:
            content_type = r.headers.get('content-type', '').lower()
            content_length = len(r.content)
            
            # Check content type and size
            if ('image' in content_type and content_length > 100000) or \
               (content_length > 200000):  # >200KB probably an image
                from io import BytesIO
                try:
                    with Image.open(BytesIO(r.content)) as im:
                        im.load()  # Verify image data
                        size = im.size
                        if size[0] >= 500 and size[1] >= 500:
                            return size
                except:
                    # If image loading fails but size is good, accept it
                    if content_length > 200000:
                        return (800, 600)
    except Exception as e:
        print(f"Error checking image {url}: {str(e)}")
    return None

def find_all_images_500(soup, session, base_url, min_width=500, min_height=500, max_count=15):
    """Enhanced image finder that handles dynamic and large images"""
    found = set()
    
    # Extract image URLs
    urls = set()
    html = str(soup)
    
    # More comprehensive patterns
    patterns = [
        r'(?:/cdn/|/_graphics/)[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?',
        r'(?:src|href|content)=["\']([^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?)["\']',
        r'url\(["\']?([^"\'()]+\.(?:jpg|jpeg|png|webp|gif)[^"\'()]*)["\']?\)',
        r'["\'](?:https?:)?//[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?["\']'
    ]
    
    # Extract URLs from patterns
    for pattern in patterns:
        matches = re.finditer(pattern, html, re.IGNORECASE)
        for match in matches:
            url = match.group(1) if match.groups() else match.group(0)
            url = url.strip('"\' ')
            if url and not any(x in url.lower() for x in ['icon', 'thumb', 'logo-', 'favicon']):
                if url.startswith('//'):
                    url = 'https:' + url
                elif not url.startswith('http'):
                    url = urljoin(base_url, url)
                urls.add(url)
    
    # Process URLs with both direct and proxy attempts
    for url in urls:
        print(f"Checking image: {url}")
        size = try_fetch_image(session, url)  # Try direct first
        if not size and 'rakstudios.co.uk' in url:  # Special handling for problematic sites
            proxy_url = "https://proxyapp-hjeqhbg2h2c2baay.uksouth-01.azurewebsites.net/proxy"
            size = try_fetch_image(session, url, proxy_url)
        
        if size:
            found.add(url)
            print(f"Added image to results: {url}")
            if len(found) >= max_count:
                break
    
    return list(found)

def get_homepage_seo_text(soup):
    parts = []
    title_tag = soup.find("title")
    if (title_tag):
        parts.append("Title: " + title_tag.get_text(strip=True))

    desc = soup.find("meta", attrs={"name": "description"})
    if (desc and desc.get("content")):
        parts.append("Meta Description: " + desc["content"].strip())

    keywords = soup.find("meta", attrs={"name": "keywords"})
    if (keywords and keywords.get("content")):
        parts.append("Meta Keywords: " + keywords["content"].strip())

    ogdesc = soup.find("meta", property="og:description")
    if (ogdesc and ogdesc.get("content")):
        parts.append("OG Description: " + ogdesc["content"].strip())

    return "\n".join(parts)

def get_homepage_text(soup, max_len=10000):
    text_content = soup.get_text(separator=" ", strip=True)
    return text_content[:max_len].strip()

def find_about_page_url(soup, base_url):
    for a_tag in soup.find_all("a", href=True, string=True):
        t = a_tag.get_text(separator=" ", strip=True).lower()
        h = a_tag["href"].lower().strip()
        if "about" in t or "about" in h:
            return build_absolute_url(a_tag["href"], base_url)
    return None

def find_contact_page_url(soup, base_url):
    """Enhanced contact page detection with more patterns and fallbacks"""
    contact_keywords = [
        'contact', 'contact-us', 'contactus', 'reach-us', 'reach',
        'connect', 'get-in-touch', 'getintouch', 'enquiry', 'enquiries',
        'help/contact', 'help',
        'about/contact', 'about-us/contact',
        'info', 'information'
    ]
    
    # First look for exact matches in navigation menus
    nav_elements = soup.find_all(['nav', 'header', 'div'], class_=lambda x: x and ('nav' in x.lower() or 'menu' in x.lower()))
    for nav in nav_elements:
        for a_tag in nav.find_all('a', href=True):
            href = a_tag.get('href', '').strip()
            text = a_tag.get_text(separator=' ', strip=True).lower()
            if any(keyword in href.lower() or keyword in text for keyword in contact_keywords):
                return urljoin(base_url, href)
    
    # Then check all links with contact-related classes
    contact_elements = soup.find_all(class_=lambda x: x and ('contact' in x.lower() or 'enquiry' in x.lower()))
    for element in contact_elements:
        a_tag = element.find('a', href=True)
        if a_tag:
            return urljoin(base_url, a_tag.get('href', '').strip())
    
    # Finally, check all links
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '').strip()
        text = a_tag.get_text(separator=' ', strip=True).lower()
        if any(keyword in href.lower() or keyword in text for keyword in contact_keywords):
            return urljoin(base_url, href)
    
    # Fallback: If domain is known for contact page, e.g., prsformusic.com
    if "prsformusic.com" in base_url:
        return urljoin(base_url, "/help/contact-us")
    
    # Fallback: Try the base URL with common contact paths
    domain = base_url.rstrip('/')
    fallback_paths = [
        '/contact', '/contact-us', '/contactus', '/help/contact-us',
        '/help/contact', '/about/contact', '/get-in-touch'
    ]
    for path in fallback_paths:
        candidate = urljoin(domain, path)
        try:
            r = requests.get(candidate, timeout=5)
            if r.status_code == 200:
                return candidate
        except Exception:
            continue
    return None

def get_about_page_text(session, url):
    try:
        r = session.get(url, timeout=5, verify=False)
        if r.status_code == 200:
            s2 = BeautifulSoup(r.text, "html.parser")
            return s2.get_text(separator=" ", strip=True)[:10000]
    except:
        pass
    return ""

def get_dynamic_page_content(url):
    """Use Playwright to get content from dynamic pages"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            print(f"Loading dynamic content from: {url}")
            page.goto(url)
            # Wait for dynamic content to load
            page.wait_for_timeout(3000)  # Wait 3 seconds for animations
            
            # Wait for common contact elements
            selectors = [
                'address', 
                '[class*="contact"]', 
                '[class*="address"]',
                '[id*="contact"]',
                '[class*="info"]'
            ]
            
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=2000)
                except:
                    continue
            
            # Get the full page content
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"Error getting dynamic content: {str(e)}")
        return None

def get_contact_text_selenium(url):
    """Use Selenium to get contact information with explicit waits"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Wait longer for content to load and animations to complete
        wait = WebDriverWait(driver, 10)
        
        # Try multiple selectors that might contain contact info
        selectors = [
            "//div[contains(@class, 'contact')]",
            "//div[contains(@class, 'address')]",
            "//address",
            "//footer",
            "//div[contains(text(), '@') or contains(text(), 'Tel:')]",
            "//p[contains(text(), '@') or contains(text(), 'Tel:')]",
            "//div[contains(text(), 'Phone') or contains(text(), 'Email')]",
            "//*[contains(text(), '+44') or contains(text(), '(0)')]"
        ]
        
        text_parts = []
        for selector in selectors:
            try:
                elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, selector)))
                for element in elements:
                    text = element.text.strip()
                    if text:
                        text_parts.append(text)
                        print(f"Found text via Selenium: {text[:200]}")
            except:
                continue
        
        # Get the full page text as backup
        page_text = driver.find_element(By.TAG_NAME, "body").text
        text_parts.append(page_text)
        
        driver.quit()
        return "\n=====\n".join(text_parts)
        
    except Exception as e:
        print(f"Selenium error: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None

def get_contact_page_text(session, url, base_url):
    """Enhanced contact page text extraction with multiple fallbacks"""
    print(f"\nProcessing contact page: {url}")
    
    # First try: Selenium
    selenium_text = get_contact_text_selenium(url)
    if selenium_text and is_valid_contact_text(selenium_text):
        return selenium_text
    
    # Second try: Regular request
    try:
        r = session.get(url, timeout=10, verify=False)
        if r.status_code == 200:
            request_text = r.text
            if is_valid_contact_text(request_text):
                return request_text
    except Exception as e:
        print(f"Request error: {e}")

    # Fallback: If domain is known, force using its default contact page
    if "prsformusic.com" in base_url:
        forced_url = urljoin(base_url, "/help/contact-us")
        forced_text = get_contact_text_selenium(forced_url)
        extracted_address = quick_extract_address(forced_text or "")
        if extracted_address:
            return extracted_address

    # Fallback: Try common subpage paths
    fallback_paths = ['/help/contact-us', '/contact', '/about/contact']
    for path in fallback_paths:
        fallback_url = base_url.rstrip('/') + path
        print(f"Attempting fallback URL: {fallback_url}")
        try:
            r = session.get(fallback_url, timeout=10, verify=False)
            if r.status_code == 200:
                fallback_text = r.text
                if is_valid_contact_text(fallback_text):
                    return fallback_text
        except Exception as e:
            print(f"Fallback URL error: {e}")
    
    print("No valid contact text found; returning empty string.")
    return ""

def extract_contact_info(text):
    """Extract contact info with improved pattern matching"""
    emails = set()
    phones = set()
    
    if not text:
        return {"emails": [], "phones": []}
    
    # Clean the text
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('(0)', '')  # Remove common UK number noise
    
    # Find emails (case insensitive)
    email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
    found_emails = re.findall(email_pattern, text, re.IGNORECASE)
    for email in found_emails:
        email = email.lower().strip()
        if '@' in email and '.' in email.split('@')[1]:
            emails.add(email)  # Using set to deduplicate
    
    # Find phones
    # First look for labeled phones
    labeled_pattern = r'(?:tel|phone|t|call|contact|mob)(?:ephone)?[\s:.-]*(\+?\d[\d\s\-\(\)\.]+\d)'
    matches = re.finditer(labeled_pattern, text, re.IGNORECASE)
    for match in matches:
        number = match.group(1)
        try:
            cleaned = re.sub(r'[^\d+]', '', number)
            if cleaned.startswith('0'):
                cleaned = '+44' + cleaned[1:]
            elif not cleaned.startswith('+'):
                if len(cleaned) >= 10:
                    cleaned = '+44' + cleaned
            
            parsed = phonenumbers.parse(cleaned, "GB")
            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                phones.add(formatted)  # Using set to deduplicate
        except Exception as e:
            print(f"Phone parsing error: {str(e)} for {number}")
    
    # Then look for any remaining numbers that might be phones
    if not phones:  # Only if we haven't found phones yet
        number_pattern = r'(?:\+44|0)[\d\s\-\(\)\.]{9,}'
        matches = re.finditer(number_pattern, text)
        for match in matches:
            number = match.group(0)
            try:
                cleaned = re.sub(r'[^\d+]', '', number)
                if cleaned.startswith('0'):
                    cleaned = '+44' + cleaned[1:]
                
                parsed = phonenumbers.parse(cleaned, "GB")
                if phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    phones.add(formatted)
                    print(f"Found phone: {formatted}")
            except Exception as e:
                print(f"Phone parsing error: {str(e)} for {number}")
    
    return {
        "emails": sorted(list(emails)),
        "phones": sorted(list(phones))
    }

def extract_footer_content(soup):
    """Extract all footer content with multiple fallback methods"""
    footer_text = []
    
    # Method 1: Standard footer tag
    footer = soup.find('footer')
    if footer:
        footer_text.append(footer.get_text(separator=' ', strip=True))
    
    # Method 2: Elements with footer-related classes
    footer_classes = [
        '[class*="footer"]', '[id*="footer"]',
        '[class*="bottom"]', '[class*="btm"]',
        '.site-info', '.contact-info'
    ]
    
    for selector in footer_classes:
        elements = soup.select(selector)
        for elem in elements:
            footer_text.append(elem.get_text(separator=' ', strip=True))
    
    return ' '.join(footer_text)

def extract_abbey_road_address(text):
    """Extract Abbey Road Studios specific address format"""
    patterns = [
        # Main Abbey Road pattern
        r"Abbey Road Studios\s*\|\s*3 Abbey Road\s*\|\s*St\. John's Wood\s*London\s*NW8\s*9AY\s*\|\s*tel:\s*\+44\s*\(0\)20\s*7266\s*7000",
        # Registered office pattern
        r"Registered office:\s*4 Pancras Square,\s*Kings Cross,\s*London\s*N1C\s*4AG",
        # Fallback pattern
        r"(?:Abbey Road Studios|3 Abbey Road).*?(?:London\s+NW8\s+9AY)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            address = match.group(0).strip()
            if "tel:" in address.lower():
                address, phone = address.split("tel:")
                return {
                    "address": address.strip(),
                    "phone": phone.strip()
                }
            return {"address": address, "phone": ""}
    return None


#############################################
# 3. Improved GPT-based Address Extraction
#############################################

import json  # Ensure JSON is imported for parsing GPT responses

# Regex pattern to detect potential UK-style addresses before sending to GPT
ADDRESS_REGEX = re.compile(
    r"\b(?:\d{1,4})?\s*(?:[A-Za-z0-9.,\-'\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Close|Cl|Crescent|Drive|Dr|Terrace|Court|Place|Way|Hill|Gardens|Square|Mews|Gate|Walk|Rise|Vale|View|Grove|Parade|Broadway|End|Row|Bypass|Highway|Boulevard|Hwy|Pkwy))"
    r"\s*,?\s*(?:[A-Za-z\s]+)?\s*,?\s*(?:[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})\b",
    re.IGNORECASE
)

def extract_potential_address(text, soup=None):
    """Enhanced address pattern extraction with footer content and improved patterns"""
    # First get footer content if soup is provided
    footer_text = ""
    if soup:
        footer = soup.find('footer')
        if footer:
            footer_text += footer.get_text(separator=' ', strip=True) + "\n"
        
        # Get elements with footer-related classes
        footer_selectors = ['footer', '[class*="footer"]', '[class*="bottom"]', 
                          '.contact-info', 'address']
        for selector in footer_selectors:
            elements = soup.select(selector)
            for elem in elements:
                footer_text += elem.get_text(separator=' ', strip=True) + "\n"
    
    if footer_text:
        print(f"DEBUG: Found footer text: {footer_text[:200]}...")
        text = f"{text}\n{footer_text}"  # Combine main text with footer
    
    # Enhanced address patterns
    patterns = [
        # Pipe-separated format (Abbey Road style)
        r"([A-Za-z0-9\s]+\|[^|]+\|[^|]+(?:London|Manchester|Birmingham)[^|]*[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})",
        
        # Registered office format
        r"(?:Registered\s+(?:Office|Address)):\s*([^\.]+?(?:[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}))",
        
        # Standard UK address with postcode
        r"([A-Za-z0-9\s,\.]+(?:Street|St|Road|Rd|Lane|Ln|Avenue|Ave|Way|Close|Cl)[^,]*,[^,]+,[^,]*[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})",
        
        # Address with building name
        r"([A-Za-z0-9\s\-\']+(?:Studios|House|Building|Centre|Center),?[^,]*,[^,]+,[^,]*[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})",
        
        # Original patterns
        r"(?:[A-Za-z0-9\s,.'-]+)?(?:[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2})(?:[A-Za-z0-9\s,.'-]+)?",
        r"\b\d+[\s,]+[A-Za-z0-9\s,.-]+(Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Close|Cl|Drive|Dr|Way|Court|Ct)[A-Za-z0-9\s,.-]+"
    ]
    
    found_texts = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Get context around match
            matched_text = match.group(1) if len(match.groups()) > 0 else match.group(0)
            found_texts.append(matched_text.strip())
            print(f"DEBUG: Found address match: {matched_text}")
    
    # Filter out likely false positives (require at least 4 words)
    filtered = [t for t in found_texts if len(t.split()) >= 4]
    # If no filtered match, fallback to original text; otherwise return filtered matches
    return "\n".join(sorted(set(filtered))) if filtered else text

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
1. If there are multiple address lines, combine the venue/building name with the street address in Address line 1
2. Use Address line 2 for additional location details (area, district, floor, etc.)
3. Make sure to capture the full postcode and city
4. For UK addresses, always use "GB" as the country code, not "UK"
5. Ensure all components are properly identified and none are missed

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

def extract_address_fields_gpt(text, soup=None):
    """Enhanced address extraction with footer content and fallback mechanism"""
    # First try with combined content including footer
    text_to_process = extract_potential_address(text, soup)
    print(f"DEBUG: Processing text for address extraction: {text_to_process[:200]}...")
    
    # Try GPT extraction
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": ADDRESS_PROMPT + text_to_process}
            ],
            max_tokens=500,
            temperature=0.0,
        )
        
        raw_json = response.choices[0].message.content.strip()
        result = json.loads(raw_json) if raw_json else {}
        
        if result and result.get("Full address"):
            print(f"DEBUG: Successfully extracted address via GPT: {result}")
            return result
            
        # Fallback: Look for postcode and try again with context
        postcode_match = re.search(r'[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}', text_to_process)
        if postcode_match:
            print("DEBUG: Using postcode fallback...")
            start = max(0, postcode_match.start() - 150)
            end = min(len(text_to_process), postcode_match.end() + 150)
            fallback_text = text_to_process[start:end]
            
            fallback_response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": ADDRESS_PROMPT + fallback_text}
                ],
                max_tokens=500,
                temperature=0.0,
            )
            
            fallback_json = fallback_response.choices[0].message.content.strip()
            result = json.loads(fallback_json) if fallback_json else {}
            
            if result and result.get("Full address"):
                print(f"DEBUG: Fallback extraction successful: {result}")
                return result
                
    except Exception as e:
        print(f"DEBUG: Address extraction error: {str(e)}")
    
    # Return empty structure if all attempts fail
    return {
        "Full address": "",
        "Address line 1": "",
        "Address line 2": "",
        "City": "",
        "County": "",
        "Country": "",
        "Post code": "",
        "Country code": ""
    }

NAME_PROMPT = """You have a short site or listing description. 
Try to guess the name of the site or listing from the text. 
Return just the name, or an empty string if not found.

Text:
"""

def extract_name_gpt(text):
    """
    If name is missing, attempt to guess a name from the Description using ChatGPT.
    Return a single string (the name).
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
        name_guess = response.choices[0].message.content.strip()
        return name_guess
    except:
        return ""


###################################
# 4. Additional GPT-based City/Country extraction
###################################
CITY_COUNTRY_PROMPT = """Based on the text below, try to extract city and country if they appear. 
Return JSON with keys: "City", "Country". If you cannot find them, leave them empty.

Text:
"""

def extract_city_country_gpt(text):
    # First attempt with GeoText
    places = GeoText(text)
    city = places.cities[0] if places.cities else ""
    country = places.countries[0] if places.countries else ""
    if city or country:
        return {"City": city, "Country": country}
    
    # Fallback to GPT if not found
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
        data = {}
        try:
            data = json.loads(raw_json)
        except:
            return {}
        return data
    except:
        return {}

###################################
# 4b. Fix country code logic
###################################
def fix_country_code(row):
    """
    If 'Country code' is missing or incorrect, try to fix it based on row['Country'].
    Preserve existing valid country codes.
    """
    country_str = (row['Country'] if pd.notnull(row['Country']) else "").strip().lower()
    ccode_str = (row['Country code'] if pd.notnull(row['Country code']) else "").strip().upper()

    # If there's already a valid country code that isn't "UK", keep it
    if ccode_str and ccode_str != "UK":
        return ccode_str

    # Otherwise, determine the correct code
    if country_str in ("united kingdom", "uk", "great britain", "england", "scotland", "wales"):
        return "GB"
    elif country_str in ("united states", "usa", "us", "america"):
        return "US"
    # Add more country mappings as needed
    return ccode_str or ""


###################################
# 5. "combine_into_single_address" 
###################################
def combine_into_single_address(row):
    """
    Combine subfields for the row into a single 'Full address' line.
    Specifically: [Address line 1, Address line 2, City, County, Post code, Country].
    """
    parts = []
    for field in ["Address line 1","Address line 2","City","County","Post code","Country"]:
        val = str(row.get(field,"")).strip()
        if val:
            parts.append(val)
    return ", ".join(parts)


###################################
# 6. STREAMLIT UI
###################################

# Set page config at the very top of the UI section
st.set_page_config(
    page_title="Beat N Track Data Finder",
    page_icon="🎵",
    layout="wide"
)

# Apply custom styles
st.markdown(CUSTOM_STYLES, unsafe_allow_html=True)

# Header section with logo
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(
        "https://f2516c96d9c39f54193b4f5177484359.cdn.bubble.io/f1724720784592x708213008252116400/BNT_LOGOs%20%281080%20x%201080%20px%29%20%281%29.png",
        width=150
    )

st.markdown("""
    <div style='text-align: center; animation: fadeIn 1s ease-in;'>
        <h1>Beat N Track Data Finder</h1>
    </div>
""", unsafe_allow_html=True)

# Feature cards
st.markdown("""
    <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; margin: 2rem 0;'>
        <div class='css-1r6slb0'>
            <h3>📄 Upload CSV</h3>
            <p>Upload your CSV file with URLs and optional fields</p>
        </div>
        <div class='css-1r6slb0'>
            <h3>🔍 Scrape Data</h3>
            <p>Automatically extract contact info, images, and more</p>
        </div>
        <div class='css-1r6slb0'>
            <h3>🤖 AI Processing</h3>
            <p>Smart data extraction using ChatGPT</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# Rest of the existing UI code remains unchanged
# ... existing input fields and processing logic ...

# Additional optional user inputs:
country_dropdown = ["", "United States", "United Kingdom", "Canada", "Australia", "Other"]
selected_country = st.selectbox("Select a Country (optional)", country_dropdown)

selected_state = ""
if selected_country == "United States":
    selected_state = st.text_input("State (optional; only if US)")

selected_city = st.text_input("City (optional)")

# For Venues: we look for gig listing synonyms
gig_synonyms = [
    "whatson","what-s-on","events","event-listings","eventcalendar","event-calendar","events-upcoming","event-schedule",
    "gigs","gig-listings","gig-schedule","gig-guide","lineup","concerts","concert-guide","live-events","live-shows","live-music",
    "live-music-calendar","music-calendar","music-events","music-schedule","venue-calendar","venue-events","whats-happening",
    "happening-now","coming-soon","special-events","on-stage","agenda","diary","live-diary","all-events","all-gigs","full-schedule",
    "full-lineup","show-guide","shows","shows-list","upcoming","upcoming-events","upcoming-gigs","upcoming-shows",
    "dates","dates-and-tickets","tour-dates","tickets","ticket-info","performances","performance-schedule","schedule-of-events",
    "program","programme","artist-schedule","music-events","music-schedule","venue-events","calendar","schedule"
]

type_options = ["Artists", "Venues", "Services", "Other"]
selected_type = st.selectbox("Type (required)", type_options, index=2)  # default=Services

custom_type = ""
if selected_type == "Other":
    custom_type = st.text_input("Custom Type (required)", "")

sub_type_input = st.text_input("Sub Type (optional)")

# CSV Upload Section
st.subheader("Step 1: Upload Business URLs CSV")
uploaded_file = st.file_uploader("Upload CSV (with optional address or name columns)", type=["csv"])

def quick_extract_contact_info(text):
    """Fast initial pass to find contact information with extended regex patterns"""
    emails = set()
    phones = set()
    # Basic email extraction
    quick_email = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    emails.update(re.findall(quick_email, text, re.IGNORECASE))
    # Extended phone pattern capturing numbers with and without labels
    quick_phone = r'(?:Tel|T|Phone|Call|Mob)?\s*[:.]?\s*(\+?\d[\d\s().-]{7,}\d)'
    for match in re.finditer(quick_phone, text, re.IGNORECASE):
        phone = match.group(1).strip()
        if len(re.sub(r'\D', '', phone)) >= 9:
            phones.add(phone)
    return {"emails": list(emails), "phones": list(phones)}

def quick_extract_address(text):
    """Fast initial pass to find a multi-line UK address block with context"""
    postcode_re = re.compile(r'\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b', re.IGNORECASE)
    street_keywords = [' street', ' road', ' ave', ' avenue', 'lane', 'drive', 'court']
    lines = text.splitlines()
    address_blocks = []
    for i, line in enumerate(lines):
        if postcode_re.search(line) and any(kw in line.lower() for kw in street_keywords):
            block = [line.strip()]
            # Include previous line if short (might be a building name)
            if i > 0 and len(lines[i-1].split()) <= 6:
                block.insert(0, lines[i-1].strip())
            # Include next line if it likely adds extra address detail
            if i < len(lines) - 1 and len(lines[i+1].split()) <= 10:
                block.append(lines[i+1].strip())
            address_blocks.append(" ".join(block))
    return "\n".join(address_blocks) if address_blocks else None

def quick_extract_images(soup, session, base_url):
    """Fast initial pass to find large images"""
    found = []
    # Look for image tags with src containing common high-res indicators
    for img in soup.find_all('img', src=True):
        src = img.get('src', '')
        # Skip small icons and thumbnails
        if any(x in src.lower() for x in ['icon', 'thumb', 'logo', 'small']):
            continue
        try:
            full_url = build_absolute_url(src, base_url)
            r = session.head(full_url, timeout=3)  # Fast head request
            if r.status_code == 200 and 'content-length' in r.headers:
                # If image is larger than 50KB, it might be worth checking
                if int(r.headers['content-length']) > 50000:
                    found.append(full_url)
        except:
            continue
        if len(found) >= 15:  # Max images limit
            break
    return found

def process_row(i, row, df, s, final_type, gig_synonyms):
    """Modified process_row with better footer content handling"""
    url = str(row.get("URL", "")).strip()
    df.at[i, "Error"] = ""

    if not url:
        df.at[i, "Error"] = "No URL in row"
        return

    domain = url.replace("http://", "").replace("https://", "").strip("/")
    print(f"🔄 Processing row {i + 1}: {domain}")

    try:
        resp, final_url, err = try_url_variants(s, domain)
        if not resp or resp.status_code != 200:
            df.at[i, "Error"] = err or f"HTTP {resp.status_code if resp else 'error'}"
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Get footer content first
        footer_content = ""
        footer = soup.find('footer')
        if footer:
            footer_content += footer.get_text(separator=' ', strip=True) + "\n"
        
        # Get content from footer-like elements
        footer_selectors = ['footer', '[class*="footer"]', '[class*="bottom"]', 
                          '.contact-info', 'address', '.site-info']
        for selector in footer_selectors:
            elements = soup.select(selector)
            for elem in elements:
                footer_content += elem.get_text(separator=' ', strip=True) + "\n"
                
        # Get main content and combine with footer
        main_content = soup.get_text(separator=" ", strip=True)
        combined_text = f"{main_content}\n{footer_content}"
        print(f"DEBUG: Footer content length: {len(footer_content)}")
        
        # Look for contact info in combined text
        contact_info = quick_extract_contact_info(combined_text)
        df.at[i, "EmailContacts"] = sorted(list(set(contact_info["emails"])))  # Deduplicate
        df.at[i, "PhoneContacts"] = sorted(list(set(contact_info["phones"])))  # Deduplicate
        
        # Try address extraction with combined text and footer-specific elements
        try:
            address_data = extract_address_fields_gpt(combined_text, soup)
            if address_data and "Full address" in address_data:
                for field in ["Full address", "Address line 1", "Address line 2", 
                            "City", "County", "Country", "Post code", "Country code"]:
                    if field in address_data:
                        df.at[i, field] = address_data[field]
        except Exception as e:
            print(f"Address extraction failed: {e}")
            
        # Continue with other extractions...
        # Always do thorough image search regardless of quick pass success
        images = set()  # Use set to avoid duplicates
        
        # 1. Quick pass first (might catch some obvious ones)
        quick_images = quick_extract_images(soup, s, final_url)
        if quick_images:
            images.update(quick_images)
            
        # 2. Always do thorough search
        thorough_images = find_all_images_500(soup, s, final_url, max_count=20)
        if thorough_images:
            images.update(thorough_images)
            
        # 3. Try proxy for all unique image URLs found
        proxy_url = "https://proxyapp-hjeqhbg2h2c2baay.uksouth-01.azurewebsites.net/proxy"
        proxy_images = []
        for img_url in images:
            size = try_fetch_image(s, img_url, proxy_url)  # Changed session to s
            if size:
                proxy_images.append(img_url)
                
        # Store final deduplicated image list
        df.at[i, "AllImages"] = sorted(list(set(images).union(proxy_images)))
        
        # Log results
        print(f"Images found for {domain}:")
        print(f"- Quick pass: {len(quick_images)}")
        print(f"- Thorough pass: {len(thorough_images)}")
        print(f"- Proxy verified: {len(proxy_images)}")
        print(f"- Total unique: {len(df.at[i, 'AllImages'])}")
        
        # Rest of quick pass for contact info
        contact_info = quick_extract_contact_info(main_content)
        address_text = quick_extract_address(main_content)
        has_complete_info = bool(contact_info["emails"] and contact_info["phones"] and address_text)
        
        # If quick pass found everything, update and return early
        if has_complete_info:
            print(f"Quick pass successful for {domain}")
            df.at[i, "EmailContacts"] = sorted(list(set(contact_info["emails"])))  # Deduplicate
            df.at[i, "PhoneContacts"] = sorted(list(set(contact_info["phones"])))  # Deduplicate
            # Try quick GPT address extraction
            if address_text:
                try:
                    address_data = extract_address_fields_gpt(address_text, soup)
                    if address_data and "Full address" in address_data:
                        for field in ["Full address", "Address line 1", "Address line 2", 
                                    "City", "County", "Country", "Post code", "Country code"]:
                            if field in address_data:
                                df.at[i, field] = address_data[field]
                except Exception as e:
                    print(f"Quick address extraction failed: {e}")
        
        # If quick pass didn't find everything, proceed with intensive methods
        if not has_complete_info:
            print(f"Quick pass incomplete for {domain}, trying intensive methods...")
            # Get contact page
            c_url = find_contact_page_url(soup, final_url)
            if c_url:
                c_text = get_contact_page_text(s, c_url, final_url)
                if c_text:
                    # Try intensive extraction methods
                    intensive_contacts = extract_contact_info(c_text)
                    contact_info["emails"].extend(intensive_contacts["emails"])
                    contact_info["phones"].extend(intensive_contacts["phones"])
                    
                    # Update if we found new information
                    if intensive_contacts["emails"] or intensive_contacts["phones"]:
                        df.at[i, "EmailContacts"] = sorted(list(set(
                            contact_info["emails"] + intensive_contacts["emails"]
                        )))
                        df.at[i, "PhoneContacts"] = sorted(list(set(
                            contact_info["phones"] + intensive_contacts["phones"]
                        )))
                    
                    # Try intensive address extraction if needed
                    if not address_text:
                        try:
                            address_data = extract_address_fields_gpt(c_text, soup)
                            if address_data and "Full address" in address_data:
                                for field in ["Full address", "Address line 1", "Address line 2", 
                                            "City", "County", "Country", "Post code", "Country code"]:
                                    if field in address_data:
                                        df.at[i, field] = address_data[field]
                        except Exception as e:
                            print(f"Intensive address extraction failed: {e}")
        
        # Always get social links as they're quick
        social = find_social_links(soup)
        df.at[i, "InstagramURL"] = social["instagram_url"] or ""
        df.at[i, "FacebookURL"] = social["facebook_url"] or ""
        df.at[i, "TwitterURL"] = social["twitter_url"] or ""
        df.at[i, "LinkedInURL"] = social["linkedin_url"] or ""
        df.at[i, "YoutubeURL"] = social["youtube_url"] or ""
        df.at[i, "TiktokURL"] = social["tiktok_url"] or ""
        
        # Store scraped text for later use if needed
        df.at[i, "ScrapedText"] = main_content

        # When storing results, ensure images are preserved
        if isinstance(df.at[i, "AllImages"], list):
            print(f"Found {len(df.at[i, 'AllImages'])} images for {domain}")

    except Exception as e:
        df.at[i, "Error"] = f"Processing error: {str(e)}"
        print(f"⚠️ Error processing row {i + 1}: {e}")

def cleanup_address_lines(df):
    """Clean up address lines by properly splitting multi-line addresses"""
    for i, row in df.iterrows():
        addr1 = str(row['Address line 1']).strip()
        addr2 = str(row['Address line 2']).strip()
        
        # Only process if Address line 1 has a comma and Address line 2 is empty
        if ',' in addr1 and not addr2:
            parts = [p.strip() for p in addr1.split(',')]
            if len(parts) >= 2:
                # Keep all parts except the last one in Address line 1
                df.at[i, 'Address line 1'] = ', '.join(parts[:-1])
                # Put the last part in Address line 2
                df.at[i, 'Address line 2'] = parts[-1]
                print(f"Split address for row {i}:")
                print(f"Line 1: {df.at[i, 'Address line 1']}")
                print(f"Line 2: {df.at[i, 'Address line 2']}")
    
    return df

# Update the display conversion to handle image arrays properly
def ensure_string_format(value):
    """Improved string conversion for arrays"""
    if isinstance(value, list):
        if all(isinstance(x, str) for x in value):  # For lists of URLs
            return "||".join(value)  # Use a distinctive separator
        return ", ".join(map(str, value))
    return str(value) if pd.notnull(value) else ""

EXPECTED_COLUMNS = {
    "URL": ["url", "website", "web", "link", "address"],
    "Name": ["name", "business_name", "company", "title"],
    "Type": ["type", "category", "business_type"],
    "Sub Type": ["sub_type", "subcategory", "sub"],
    "Description": ["description", "desc", "about", "details"],
    "ScrapedText": ["scraped_text", "raw_text", "content", "page_text", "text_content"],  # Added this line
    "Address line 1": ["address1", "address_1", "street", "address_line_1"],
    "Address line 2": ["address2", "address_2", "address_line_2"],
    "City": ["city", "town", "municipality"],
    "County": ["county", "region", "province", "state"],
    "Country": ["country", "nation"],
    "Post code": ["postcode", "zip", "zip_code", "postal_code", "postal"],
    "Country code": ["country_code", "countrycode", "iso_code"],
    "State": ["state", "province", "region"],
}

def guess_column_mapping(df_columns):
    """Guess the mapping between uploaded columns and expected columns"""
    mapping = {}
    df_columns_lower = [col.lower().strip() for col in df_columns]
    
    for expected_col, alternatives in EXPECTED_COLUMNS.items():
        # Check for exact match first
        if expected_col.lower() in df_columns_lower:
            mapping[expected_col] = df_columns[df_columns_lower.index(expected_col.lower())]
            continue
            
        # Check alternatives
        for alt in alternatives:
            if alt in df_columns_lower:
                mapping[expected_col] = df_columns[df_columns_lower.index(alt)]
                break
    
    return mapping

if uploaded_file is not None:
    file_text = uploaded_file.read().decode("utf-8", errors="replace")
    f = StringIO(file_text)
    df_original = pd.read_csv(f)
    
    # Handle column mapping in session state
    if "column_mapping_accepted" not in st.session_state:
        st.session_state.column_mapping_accepted = False
    
    if not st.session_state.column_mapping_accepted:
        # Get initial column mapping
        if "column_mapping" not in st.session_state:
            st.session_state.column_mapping = guess_column_mapping(df_original.columns)
        
        # Create UI for unmapped columns
        st.subheader("Column Mapping")
        st.write("Please verify or correct the column mappings below:")
        
        # Create two columns layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("##### Required Fields")
            # Show dropdown for URL (required) - Fixed index handling
            url_col = st.session_state.column_mapping.get("URL", "")
            url_options = [""] + list(df_original.columns)
            url_index = url_options.index(url_col) if url_col in url_options else 0
            
            url_selected = st.selectbox(
                "URL field",
                options=url_options,
                index=url_index,
                key="url_mapping"
            )
            if url_selected:
                st.session_state.column_mapping["URL"] = url_selected
        
        with col2:
            st.write("##### Optional Fields")
            # Show dropdowns for other fields - Fixed index handling
            for expected_col in EXPECTED_COLUMNS.keys():
                if expected_col != "URL":
                    current_value = st.session_state.column_mapping.get(expected_col, "")
                    options = [""] + list(df_original.columns)
                    index = options.index(current_value) if current_value in options else 0
                    
                    selected = st.selectbox(
                        f"{expected_col} field",
                        options=options,
                        index=index,
                        key=f"mapping_{expected_col}"
                    )
                    if selected:
                        st.session_state.column_mapping[expected_col] = selected
        
        # Add Accept button
        if st.button("Accept Mapping"):
            # Validate URL mapping
            if "URL" not in st.session_state.column_mapping or not st.session_state.column_mapping["URL"]:
                st.error("URL field mapping is required")
            else:
                st.session_state.column_mapping_accepted = True
                st.session_state.df_original = df_original  # Store the original DataFrame
                st.rerun()

    # Show Process button only after mapping is accepted
    if st.session_state.column_mapping_accepted:
        if st.button("Process CSV"):
            # Create new DataFrame with mapped columns
            df = pd.DataFrame()
            
            # Copy mapped columns to new DataFrame
            for expected_col, source_col in st.session_state.column_mapping.items():
                if source_col in st.session_state.df_original.columns:
                    df[expected_col] = st.session_state.df_original[source_col]
            
            # Initialize remaining required columns
            required_cols = [
                "AllImages", "InstagramURL", "FacebookURL", "TwitterURL",
                "LinkedInURL", "YoutubeURL", "TiktokURL", "EmailContacts",
                "PhoneContacts", "ScrapedText", "Description", "Error",
                "Type", "Sub Type", "GigListingURL",
                "Full address", "Address line 1", "Address line 2",
                "City", "County", "Country", "Post code", "Country code",
                "Name", "State"
            ]
            
            for col in required_cols:
                if col not in df.columns:
                    df[col] = ""
            
            # Fill Type / Sub Type
            final_type = selected_type
            if selected_type == "Other":
                if not custom_type.strip():
                    st.error("You selected 'Other' but did not provide a custom type.")
                    st.stop()
                else:
                    final_type = custom_type.strip()
                    
            final_sub_type = sub_type_input.strip()
            
            for i in range(len(df)):
                df.at[i, "Type"] = final_type
                df.at[i, "Sub Type"] = final_sub_type
                df.at[i, "GigListingURL"] = ""

            # Apply optional country/city/state to all rows
            if selected_country.strip():
                for i in range(len(df)):
                    df.at[i, "Country"] = selected_country
                    if selected_country.lower() in ("united kingdom", "uk", "great britain"):
                        df.at[i, "Country code"] = "GB"
                    elif selected_country.lower() in ("united states", "usa", "us"):
                        df.at[i, "Country code"] = "US"
                    else:
                        df.at[i, "Country code"] = ""

                if selected_country == "United States" and selected_state.strip():
                    for i in range(len(df)):
                        df.at[i, "State"] = selected_state.strip()

            if selected_city.strip():
                for i in range(len(df)):
                    df.at[i, "City"] = selected_city.strip()

            # Set up requests session
            s = requests.Session()
            adapt = HTTPAdapter(max_retries=1)
            s.mount("http://", adapt)
            s.mount("https://", adapt)

            # Process rows
            total = len(df)
            pbar = st.progress(0)
            stat_area = st.empty()
            table_area = st.empty()

            for i, row in df.iterrows():
                try:
                    process_row(i, row, df, s, final_type, gig_synonyms)
                except Exception as e:
                    df.at[i, "Error"] = f"Processing error: {e}"
                    print(f"⚠️ Error processing row {i + 1}: {e}")

                time.sleep(1)
                
                # Update progress and display
                display_df = df.copy()
                for col in ["AllImages", "EmailContacts", "PhoneContacts"]:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(ensure_string_format)

                pbar.progress(int(((i + 1) / total) * 100))
                stat_area.text(f"Processing row {i + 1}/{total}...")
                table_area.dataframe(display_df, use_container_width=True)

            # Final cleanup and storage
            df = cleanup_address_lines(df)
            st.session_state["df"] = df
            
            # Show final results
            st.success("Processing complete!")
            st.dataframe(df, use_container_width=True)
            
            # Create download buttons
            out_buf = StringIO()
            df.to_csv(out_buf, index=False)
            st.download_button(
                "Download CSV",
                out_buf.getvalue(),
                file_name="final.csv",
                mime="text/csv"
            )
            
            auto_download_csv(df, "scraped_")

# ...rest of existing code...

###################################
# GPT Summaries Button
###################################
if st.button("Add Descriptions"):
    if st.session_state["df"] is None:
        st.warning("No data to summarize or fill. Please scrape first.")
    else:
        st.info("Generating GPT summaries + filling City / Country from ScrapedText if missing...")

        df = st.session_state["df"].copy()
        length = len(df)
        bar = st.progress(0)

        for i, row in df.iterrows():
            if not row.get("Description", "").strip():  # Only generate if Description is empty
                txt = str(row.get("ScrapedText", "")).strip()
                if txt:
                    desc = generate_gpt_description(txt)
                    df.at[i, "Description"] = desc  # Store only if there's new data
                    
            # Fill missing city/country from ScrapedText
            city_missing = not row.get("City", "").strip()
            country_missing = not row.get("Country", "").strip()
            if (city_missing or country_missing) and txt:
                loc_info = extract_city_country_gpt(txt)
                if loc_info:
                    if city_missing and loc_info.get("City", "").strip():
                        df.at[i, "City"] = loc_info["City"].strip()
                    if country_missing and loc_info.get("Country", "").strip():
                        df.at[i, "Country"] = loc_info["Country"].strip()
                        df.at[i, "Country code"] = fix_country_code(df.loc[i])  # Fix country code too

            # Fill missing city/country from ScrapedText
            city_missing = not row.get("City", "").strip()
            country_missing = not row.get("Country", "").strip()
            if (city_missing or country_missing) and txt:
                loc_info = extract_city_country_gpt(txt)
                if loc_info:
                    if city_missing and loc_info.get("City", "").strip():
                        df.at[i, "City"] = loc_info["City"].strip()
                    if country_missing and loc_info.get("Country", "").strip():
                        df.at[i, "Country"] = loc_info["Country"].strip()
                        df.at[i, "Country code"] = fix_country_code(df.loc[i])  # Fix country code too

            bar.progress(int(((i + 1) / length) * 100))

        st.session_state["df"] = df
        st.success("AI data finder complete. Summaries + City/Country fix done.")

        df_display_2 = df.copy()
        for col in ["AllImages", "EmailContacts", "PhoneContacts"]:
            if col in df_display_2.columns:
                df_display_2[col] = df_display_2[col].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))

        st.dataframe(df_display_2, use_container_width=True)

        out2 = StringIO()
        df_for_csv_2 = df.copy()
        for col in ["AllImages", "EmailContacts", "PhoneContacts"]:
            if col in df_for_csv_2.columns:
                df_for_csv_2[col] = df_for_csv_2[col].apply(lambda x: str(x) if isinstance(x, list) else x)

        df_for_csv_2.to_csv(out2, index=False)
        st.download_button(
            "Download Summarized CSV",
            out2.getvalue(),
            file_name="summarized.csv",
            mime="text/csv"
        )

        auto_download_csv(df, "gpt_")  # Add this line


###################################
# 6. BUBBLE INTEGRATION
###################################
def bubble_initialize_button():
    """
    Send sample JSON to Bubble's 'initialize' endpoint.
    We'll send up to 5 rows from st.session_state['df'] as sample data.
    """
    if st.session_state["df"] is None:
        st.warning("No data to summarize or fill. Please scrape first.")
        return

    df = st.session_state["df"].copy()
    sample = df.head(5).to_dict(orient="records")

    init_url = "https://majorlabl.bubbleapps.io/version-test/api/1.1/wf/bntdata/initialize"
    st.info(f"Sending up to 5 sample rows to {init_url} for Bubble initialization...")

    try:
        resp = requests.post(init_url, json=sample, timeout=10)
        if resp.status_code == 200:
            st.success("Bubble initialization success! Check your Bubble workflow to confirm.")
        else:
            st.error(f"Bubble returned {resp.status_code}: {resp.text}")
    except requests.RequestException as e:
        st.error(f"Error contacting Bubble initialize endpoint: {e}")

def bubble_send_final_button():
    """Enhanced Bubble integration that properly handles arrays"""
    if st.session_state["df"] is None:
        st.warning("No data to summarize or fill. Please scrape first.")
        return

    df = st.session_state["df"].copy()
    
    # Ensure arrays are properly formatted for Bubble
    for i, row in df.iterrows():
        # Convert AllImages to proper array if it's a string
        if isinstance(row['AllImages'], str):
            if '||' in row['AllImages']:  # Our custom separator
                df.at[i, 'AllImages'] = row['AllImages'].split('||')
            elif ',' in row['AllImages']:  # Comma separator
                df.at[i, 'AllImages'] = [url.strip() for url in row['AllImages'].split(',')]
            else:
                df.at[i, 'AllImages'] = [row['AllImages']] if row['AllImages'] else []
        
        # Ensure it's a list
        if not isinstance(row['AllImages'], list):
            df.at[i, 'AllImages'] = []

    records = df.to_dict(orient="records")

    bubble_url = "https://beatntrack.world/api/1.1/wf/bntdata"
    st.info(f"Sending all rows to {bubble_url} ...")

    try:
        resp = requests.post(bubble_url, json=records, timeout=20)
        if resp.status_code == 200:
            st.success("Data successfully sent to Bubble production endpoint!")
        else:
            st.error(f"Bubble returned {resp.status_code}: {resp.text}")
    except requests.RequestException as e:
        st.error(f"Error contacting Bubble production endpoint: {e}")

st.subheader("Bubble Integration")
col1, col2 = st.columns(2)
with col1:
    if st.button("Initialize Bubble"):
        bubble_initialize_button()

with col2:
    if st.button("Send to Bubble"):
        bubble_send_final_button()