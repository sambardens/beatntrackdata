# scraper.py

import time
import re
import socket
import requests
import traceback
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import cloudscraper
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from playwright.sync_api import sync_playwright
from PIL import Image
import json
import phonenumbers
from geotext import GeoText
import pandas as pd
import openai  # Ensure openai is imported
from io import BytesIO
from typing import List, Tuple
from regex import get_patterns_for_country   # new import
from fallback import extensive_fallback_scrape  # new import

########################################################################
# Global Constants / Prompts
########################################################################

# Define the ADDRESS_PROMPT BEFORE any function that uses it.
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

########################################################################
# URL Helpers
########################################################################

def build_absolute_url(relative_url, base_url):
    """Consistent URL building"""
    if relative_url.lower().startswith(("http", "data:image")):
        return relative_url
    return urljoin(base_url, relative_url)

def try_url_variants(session, base_domain, wait_time=3):
    """Enhanced URL fetching with more robust fallbacks"""
    if base_domain.lower().startswith("www."):
        base_domain = base_domain[4:]
        
    variants = [
        f"https://www.{base_domain}",
        f"https://{base_domain}",
        f"http://www.{base_domain}",
        f"http://{base_domain}",
        f"https://www.{base_domain}/home",  # Common alternates
        f"https://{base_domain}/index",
        f"https://www.{base_domain}/en"     # Language-specific
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
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    last_err = ""
    
    # Regular request attempts
    for variant in variants:
        try:
            print(f"Trying URL: {variant}")
            time.sleep(wait_time)
            resp = session.get(variant, headers=headers, timeout=15, verify=False, allow_redirects=True)
            if resp.status_code in [200, 301, 302]:
                print(f"Success with status {resp.status_code} for URL: {variant}")
                return resp, variant, ""
            last_err = f"HTTP {resp.status_code}"
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            continue
    
    # Cloudscraper attempt with custom browser config
    try:
        print(f"Attempting with cloudscraper for: {variants[0]}")
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'desktop': True
            },
            delay=10
        )
        resp = scraper.get(variants[0], timeout=20)
        if resp.status_code == 200:
            return resp, variants[0], ""
    except Exception as e:
        last_err = str(e)
    
    # External proxy attempt with retry
    for _ in range(2):  # Try proxy twice
        try:
            proxy_url = f"https://proxyapp-hjeqhbg2h2c2baay.uksouth-01.azurewebsites.net/proxy?url={variants[0]}"
            resp = requests.get(proxy_url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                return DummyResponse(resp.text), variants[0], ""
        except Exception as e:
            print(f"External Proxy Exception: {e}")
            traceback.print_exc()
            last_err = str(e)
            time.sleep(2)  # Wait before retry
            continue
    
    return None, "", last_err if last_err else "All attempts failed"

########################################################################
# Dynamic Content and Selenium Extraction
########################################################################

def get_dynamic_page_content(url):
    """
    Use Playwright to get content from dynamic pages.
    Returns the full HTML content.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            print(f"Loading dynamic content from: {url}")
            page.goto(url)
            page.wait_for_timeout(3000)  # Wait 3 seconds for animations
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"Error getting dynamic content: {e}")
        return None

def get_contact_text_selenium(url):
    """
    Use Selenium to extract contact information from a page.
    Waits for common elements (contact, address, footer) and returns the combined text.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        selectors = [
            "//div[contains(@class, 'contact')]",
            "//address",
            "//footer",
            "//*[contains(text(), '+44') or contains(text(), '(0)')]"
        ]
        text_parts = []
        for selector in selectors:
            try:
                elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, selector)))
                for element in elements:
                    text_parts.append(element.text.strip())
            except Exception:
                continue
        page_text = driver.find_element(By.TAG_NAME, "body").text
        text_parts.append(page_text)
        driver.quit()
        return "\n=====\n".join(text_parts)
    except Exception as e:
        print(f"Selenium error: {e}")
        if 'driver' in locals():
            driver.quit()
        return None

########################################################################
# Image and Social Extraction
########################################################################

def try_fetch_image(session, url, proxy_url=None, verify=False):
    """
    Enhanced image fetching with better validation.
    First attempts a HEAD request; if that fails, a full GET.
    Returns a tuple (width, height) if the image is valid.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": url
    }
    def is_valid_image_url(url):
        url = url.lower()
        return any(ext in url for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']) and not any(skip in url for skip in ['icon', 'thumb', 'logo', 'favicon', 'avatar', 'small'])
    if not is_valid_image_url(url):
        return None
    try:
        try:
            r = session.head(url, headers=headers, timeout=5, verify=False)
            if r.status_code == 200 and 'content-length' in r.headers:
                size = int(r.headers['content-length'])
                if size > 100000:  # >100KB
                    return (800, 600)
        except:
            pass
        full_url = url if not proxy_url else f"{proxy_url}?url={url}"
        r = session.get(full_url, headers=headers, timeout=10, verify=verify)
        if r.status_code == 200:
            content_type = r.headers.get('content-type', '').lower()
            content_length = len(r.content)
            if ('image' in content_type and content_length > 100000) or (content_length > 200000):
                from io import BytesIO
                try:
                    with Image.open(BytesIO(r.content)) as im:
                        im.load()
                        size = im.size
                        if size[0] >= 500 and size[1] >= 500:
                            return size
                except:
                    if content_length > 200000:
                        return (800, 600)
    except Exception as e:
        print(f"Error checking image {url}: {str(e)}")
    return None

def find_all_images_500(soup, session, base_url, min_width=500, min_height=500, max_count=15):
    """Enhanced image finding with better validation and proxy support"""
    found = set()
    seen_urls = set()
    html = str(soup)
    
    # Comprehensive patterns for finding images
    patterns = [
        r'(?:/cdn/|/_graphics/)[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?',
        r'(?:src|href|content)=["\']([^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?)["\']',
        r'url\(["\']?([^"\'()]+\.(?:jpg|jpeg|png|webp|gif)[^"\'()]*)["\']?\)',
        r'["\'](?:https?:)?//[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'>\s]*)?["\']'
    ]
    
    # Extract and validate URLs
    for pattern in patterns:
        if len(found) >= max_count:
            break
        
        matches = re.finditer(pattern, html, re.IGNORECASE)
        for match in matches:
            url = match.group(1) if match.groups() else match.group(0).strip('"\'')
            if url and not any(x in url.lower() for x in ['icon', 'thumb', 'logo-']):
                if url.startswith('//'):
                    url = 'https:' + url
                elif not url.startswith('http'):
                    url = urljoin(base_url, url)
                
                if url not in seen_urls:
                    seen_urls.add(url)
                    # Try direct fetch first
                    size = try_fetch_image(session, url)
                    if not size:
                        # Try proxy for problematic sites
                        proxy_url = "https://proxyapp-hjeqhbg2h2c2baay.uksouth-01.azurewebsites.net/proxy"
                        size = try_fetch_image(session, url, proxy_url)
                    
                    if size:
                        found.add(url)
                        if len(found) >= max_count:
                            break
    
    return list(found)

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

def find_social_links(soup):
    """Enhanced social media detection with more variations"""
    social_links = {
        "instagram_url": None,
        "facebook_url": None,
        "twitter_url": None,
        "linkedin_url": None,
        "youtube_url": None,
        "tiktok_url": None
    }
    
    # Search both a tags and meta tags
    for element in soup.find_all(['a', 'meta', 'link']):
        href = element.get('href') or element.get('content') or ''
        href = href.strip()
        
        if not href.lower().startswith(("http", "https", "//")):
            continue
            
        href = href if href.startswith("http") else f"https:{href}" if href.startswith("//") else href
        lhref = href.lower()
        
        # Enhanced Instagram detection (includes shortened links)
        if (any(x in lhref for x in ["instagram.com", "instagr.am"]) and 
            not any(x in lhref for x in ["/reel/", "/story/", "/p/"]) and 
            not social_links["instagram_url"]):
            social_links["instagram_url"] = href
            print(f"Found Instagram: {href}")
            
        # Enhanced Facebook detection (includes different subdomains)
        elif (any(x in lhref for x in ["facebook.com", "fb.com", "fb.me"]) and 
              not any(x in lhref for x in ["/photos/", "/events/"]) and 
              not social_links["facebook_url"]):
            social_links["facebook_url"] = href
            print(f"Found Facebook: {href}")
            
        # Enhanced Twitter/X detection
        elif (any(x in lhref for x in ["twitter.com", "x.com", "t.co"]) and 
              not any(x in lhref for x in ["/status/", "/moments/"]) and 
              not social_links["twitter_url"]):
            social_links["twitter_url"] = href
            print(f"Found Twitter: {href}")
            
        # Enhanced LinkedIn detection
        elif ("linkedin.com" in lhref and 
              not "/jobs/" in lhref and 
              not social_links["linkedin_url"]):
            social_links["linkedin_url"] = href
            print(f"Found LinkedIn: {href}")
            
        # Enhanced YouTube (includes shortened links)
        elif (any(x in lhref for x in ["youtube.com", "youtu.be"]) and 
              not "/watch?" in lhref and 
              not social_links["youtube_url"]):
            social_links["youtube_url"] = href
            print(f"Found YouTube: {href}")
            
        # Enhanced TikTok detection
        elif ("tiktok.com" in lhref and 
              not "/video/" in lhref and 
              not social_links["tiktok_url"]):
            social_links["tiktok_url"] = href
            print(f"Found TikTok: {href}")
    
    return social_links

########################################################################
# Quick Extraction Helpers
########################################################################

def extract_emails_from_text(text: str, soup: BeautifulSoup = None) -> List[str]:
    """Enhanced email extraction from text and HTML"""
    emails = set()
    
    # If we have soup, look for obfuscated emails first
    if soup:
        # Check for mailto links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').strip()
                if '@' in email:
                    emails.add(email)
        
        # Check for email-related elements
        email_elements = soup.find_all(['span', 'div', 'p'], class_=lambda x: x and 'email' in x.lower())
        for element in email_elements:
            text += ' ' + element.get_text()
    
    # Clean text
    text = text.replace('email hidden; JavaScript is required', '')
    
    # Extract using patterns
    email_patterns = [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'([a-zA-Z0-9._%+-]+)\s*(?:\[at\]|\(at\)|@|\bat\b)\s*([a-zA-Z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\bdot\b)\s*([a-zA-Z]{2,})',
        r'(?:email|e-mail|contact|enquiries|info)[:;\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    ]
    
    for pattern in email_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if '[at]' in pattern or '(at)' in pattern:
                email = f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
            else:
                email = match.group(1) if len(match.groups()) > 0 else match.group(0)
            emails.add(email.lower())
    
    return list(emails)

def clean_phone_number(number: str, country_code: str = "GB") -> str:
    """Clean and standardize phone number format"""
    try:
        # Remove common non-digit artifacts
        cleaned = re.sub(r'\s+|\(0\)|\(|\)|-|\.|–', '', number)
        
        # Handle UK numbers
        if country_code == "GB":
            if cleaned.startswith("0"):
                cleaned = "+44" + cleaned[1:]
            elif not cleaned.startswith("+"):
                if len(cleaned) >= 10:
                    cleaned = "+44" + cleaned
        
        # Parse and validate
        parsed = phonenumbers.parse(cleaned, country_code)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except Exception as e:
        print(f"Phone cleaning error: {str(e)} for {number}")
    return ""

def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone numbers from text with improved formatting"""
    phones = set()
    
    # Enhanced UK phone patterns
    phone_patterns = [
        r'(?:Tel|T|Phone|Call|Mob)(?:ephone)?[\s:.-]*(?:\+44\s*)?(?:\(0\))?\s*((?:[\d]{4}[\s-]?[\d]{3}[\s-]?[\d]{3})|(?:[\d]{5}[\s-]?[\d]{6}))',
        r'(?:\+44|0)(?:\s*\(\s*0?\s*\))?[\s-]*([1-9][\d\s-]{8,})',
        r'\+\s*44\s*\(?\s*0?\s*\)?\s*([\d\s-]{10,})',
        r'(?:telephone|mobile|landline|fax)[\s:]*(\+?44\s*\(?\s*0?\s*\)?\s*[\d\s-]{10,})',
        r'(?:\+44|0)[-\s]*(\d{2,5}[-\s]*\d{6,})',
        # Additional pattern for international format
        r'\+[1-9][0-9\s-]{10,}'
    ]
    
    for pattern in phone_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            number = match.group(1) if len(match.groups()) > 0 else match.group(0)
            clean_number = clean_phone_number(number)
            if clean_number:
                phones.add(clean_number)
                print(f"Found phone: {clean_number}")
    
    return list(phones)

def quick_extract_contact_info(soup: BeautifulSoup, text: str) -> Tuple[List[str], List[str]]:
    """Extract contact information from webpage"""
    # Get emails using enhanced extraction
    emails = extract_emails_from_text(text, soup)
    
    # Get phone numbers
    phones = extract_phone_numbers(text)
    
    # Additional email extraction from common locations
    contact_sections = soup.find_all(['div', 'section'], class_=lambda x: x and 'contact' in x.lower())
    for section in contact_sections:
        section_emails = extract_emails_from_text(section.get_text(), section)
        emails.extend(section_emails)
    
    # Clean and validate emails
    valid_emails = []
    for email in emails:
        email = email.lower().strip()
        if '@' in email and '.' in email.split('@')[1]:
            if not any(invalid in email for invalid in ['example.com', 'domain.com', 'yourdomain']):
                valid_emails.append(email)
    
    return list(set(valid_emails)), list(set(phones))

def quick_extract_address(text, country="UK"):
    """
    Enhanced quick_extract_address function using country-specific regex patterns.
    """
    # Split text into segments
    segments = text.splitlines()
    
    # Retrieve regex patterns for the given country
    patterns = get_patterns_for_country(country)
    phone_pattern = patterns.get("phone", "")
    postcode_pattern = patterns.get("postcode", "")
    extra_address_pattern = patterns.get("extra_address_pattern", "")
    print(f"Debug: For country '{country}', phone_pattern: {phone_pattern}, postcode_pattern: {postcode_pattern}")

    if extra_address_pattern:
        match = re.search(extra_address_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

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
            block_segments.append(segment.strip())
            # Append next segment if exists
            if i < len(segments)-1:
                next_seg = segments[i + 1].strip()
                if next_seg:
                    block_segments.append(next_seg)
            candidate = ", ".join(block_segments)
            candidate_blocks.append((candidate, country))
    
    # Example candidate filtering using the patterns:
    def is_valid_candidate(candidate, ctry):
        candidate_lower = candidate.lower()
        has_digit = bool(re.search(r'\d+', candidate))
        if ctry.upper() in ("UK", "GB"):
            has_keyword = bool(address_keyword_regex.search(candidate_lower))
            return has_digit and has_keyword
        elif ctry.upper() in ("US", "USA", "UNITED STATES"):
            return has_digit and ("," in candidate)
        else:
            return has_digit
    
    valid_candidates = [c for c, ctry in candidate_blocks if is_valid_candidate(c, ctry)]
    
    if valid_candidates:
        best_candidate = max(valid_candidates, key=lambda b: len(b.split()))
        return best_candidate
    elif candidate_blocks:
        best_candidate = max(candidate_blocks, key=lambda t: len(t[0].split()))[0]
        return best_candidate
    return None

########################################################################
# Text and SEO Extraction
########################################################################

def get_homepage_seo_text(soup):
    parts = []
    title_tag = soup.find("title")
    if title_tag:
        parts.append("Title: " + title_tag.get_text(strip=True))
    desc = soup.find("meta", attrs={"name": "description"})
    if desc and desc.get("content"):
        parts.append("Meta Description: " + desc["content"].strip())
    keywords = soup.find("meta", attrs={"name": "keywords"})
    if keywords and keywords.get("content"):
        parts.append("Meta Keywords: " + keywords["content"].strip())
    ogdesc = soup.find("meta", property="og:description")
    if ogdesc and ogdesc.get("content"):
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
    """
    Enhanced contact page detection using various keywords and fallback methods.
    """
    contact_keywords = [
        'contact', 'contact-us', 'contactus', 'reach-us', 'reach',
        'connect', 'get-in-touch', 'getintouch', 'enquiry', 'enquiries',
        'help/contact', 'help',
        'about/contact', 'about-us/contact',
        'info', 'information'
    ]
    nav_elements = soup.find_all(['nav', 'header', 'div'], class_=lambda x: x and ('nav' in x.lower() or 'menu' in x.lower()))
    for nav in nav_elements:
        for a_tag in nav.find_all('a', href=True):
            href = a_tag.get('href', '').strip()
            text = a_tag.get_text(separator=' ', strip=True).lower()
            if any(keyword in href.lower() or keyword in text for keyword in contact_keywords):
                return urljoin(base_url, href)
    contact_elements = soup.find_all(class_=lambda x: x and ('contact' in x.lower() or 'enquiry' in x.lower()))
    for element in contact_elements:
        a_tag = element.find('a', href=True)
        if a_tag:
            return urljoin(base_url, a_tag.get('href', '').strip())
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '').strip()
        text = a_tag.get_text(separator=' ', strip=True).lower()
        if any(keyword in href.lower() or text for keyword in contact_keywords):
            return urljoin(base_url, href)
    if "prsformusic.com" in base_url or "prsmusic.com" in base_url:
        fallback_paths = [
            '/help/contact-us', '/contact', '/about/contact'
        ]
        for path in fallback_paths:
            candidate = urljoin(base_url, path)
            try:
                r = requests.get(candidate, timeout=5)
                if r.status_code == 200:
                    return candidate
            except Exception:
                continue
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

def find_all_contact_pages(soup, base_url):
    """Find all potential contact page URLs in the soup"""
    contact_urls = set()
    contact_keywords = ['contact', 'get-in-touch', 'reach-us', 'enquiry', 'enquiries']
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').lower()
        text = a.get_text(strip=True).lower()
        if any(keyword in href or text for keyword in contact_keywords):
            full_url = urljoin(base_url, a['href'])
            contact_urls.add(full_url)
    
    return list(contact_urls)

def scrape_all_contact_pages(session, urls, base_url):
    """Scrape text content from all contact pages"""
    combined_texts = []
    
    for url in urls:
        try:
            r = session.get(url, timeout=10, verify=False)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                
                # Look for contact-specific elements
                contact_elements = soup.find_all(['div', 'section', 'article'], 
                    class_=lambda x: x and ('contact' in x.lower() or 'address' in x.lower()))
                
                for element in contact_elements:
                    text = element.get_text(separator=' ', strip=True)
                    if text:
                        combined_texts.append(text)
                
                # Also get the main content if specific elements weren't found
                if not combined_texts:
                    main_content = soup.find('main') or soup.find('article') or soup.find('body')
                    if main_content:
                        combined_texts.append(main_content.get_text(separator=' ', strip=True))
                        
        except Exception as e:
            print(f"Error scraping contact page {url}: {e}")
            continue
            
    return ' '.join(combined_texts) if combined_texts else None

def get_contact_page_text(session, url, base_url):
    """Enhanced contact page text extraction with better priorities and retries"""
    print(f"\nProcessing contact page: {url}")
    
    # Prioritized list of pages to check for specific sites
    priority_paths = {
        "prsformusic.com": [
            "/about-us/corporate-information",  # Corporate info first
            "/about-us",  # About page often has address
            "/contact-us",  # Standard contact
            "/help/contact-us",  # Help contact
            "/about/contact",  # Alternative contact
        ],
        "default": [
            "/contact",
            "/contact-us",
            "/about-us",
            "/about/contact",
            "/help/contact-us"
        ]
    }

    # Known address patterns for specific sites
    address_patterns = {
        "prsformusic.com": [
            r"(?:41|forty[ -]one)\s*streatham\s*high\s*road",
            r"streatham,?\s*london\s*sw16",
            r"pancras\s*square",
            r"kings?\s*cross",
            r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}"  # UK postcode
        ]
    }

    def check_page_for_address(page_url, patterns):
        """Helper to check a single page for address patterns"""
        try:
            r = session.get(page_url, timeout=10, verify=False)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # First check specific sections
                for section in ['address', 'location', 'contact-details', 'vcard']:
                    elements = soup.find_all(class_=lambda x: x and section in x.lower())
                    for elem in elements:
                        text = elem.get_text(separator=' ', strip=True)
                        if any(re.search(pattern, text, re.I) for pattern in patterns):
                            print(f"Found address in {section} section: {text}")
                            return text

                # Then check general page content
                text = soup.get_text(separator=' ', strip=True)
                if any(re.search(pattern, text, re.I) for pattern in patterns):
                    print(f"Found address in page content")
                    return text
        except Exception as e:
            print(f"Error checking {page_url}: {e}")
        return None

    # Get domain-specific settings
    domain = base_url.split('/')[2].lower()
    base_domain = re.sub(r'^www\.', '', domain)
    paths = priority_paths.get(base_domain, priority_paths["default"])
    patterns = address_patterns.get(base_domain, [r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}"])

    # Try each priority path
    for path in paths:
        full_url = urljoin(base_url, path)
        print(f"Checking priority path: {full_url}")
        result = check_page_for_address(full_url, patterns)
        if result:
            return result

    # Fallback to footer content if no address found
    try:
        r = session.get(base_url, timeout=10, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            footer = soup.find('footer')
            if footer:
                text = footer.get_text(separator=' ', strip=True)
                if any(re.search(pattern, text, re.I) for pattern in patterns):
                    print("Found address in footer")
                    return text
    except Exception as e:
        print(f"Error checking footer: {e}")

    return None

########################################################################
# Contact Info Extraction
########################################################################

def is_valid_contact_text(text):
    """Heuristic check: valid if text contains at least one digit and more than 3 words."""
    if text and re.search(r'\d', text) and len(text.split()) > 3:
        return True
    return False

def extract_contact_info(text):
    """Enhanced contact info extraction with improved UK patterns"""
    emails = set()
    phones = set()
    
    # More comprehensive email patterns including hidden/obfuscated
    email_patterns = [
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
        r'(?:email|e-mail|contact|enquiries|info)[:;\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
        r'(?:^|[\s<(\[])([a-zA-Z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+)(?:$|[\s>)\]])',
        r'data-email=["\']([^"\']+)["\']',  # Hidden in data attributes
        r'class=["\']email["\'][^>]*>([^<]+)'  # Common email class pattern
    ]
    
    # Enhanced UK phone patterns with more variants
    phone_patterns = [
        r'(?:Tel|T|Phone|Call|Mob)(?:ephone)?[\s:.-]*(?:\+44\s*)?(?:\(0\))?\s*((?:[\d]{4}[\s-]?[\d]{3}[\s-]?[\d]{3})|(?:[\d]{5}[\s-]?[\d]{6}))',
        r'(?:\+44|0)(?:\s*\(\s*0?\s*\))?[\s-]*([1-9][\d\s-]{8,})',
        r'\+\s*44\s*\(?\s*0?\s*\)?\s*([\d\s-]{10,})',
        r'(?:telephone|mobile|landline|fax)[\s:]*(\+?44\s*\(?\s*0?\s*\)?\s*[\d\s-]{10,})',  # Additional labels
        r'(?:\+44|0)[-\s]*(\d{2,5}[-\s]*\d{6,})'  # Area code format
    ]
    
    # Clean text
    text = text.replace('\n', ' ').replace('(0)', '')
    text = re.sub(r'\s+', ' ', text)
    
    # Process emails
    for pattern in email_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            email = match.group(1) if len(match.groups()) > 0 else match.group(0)
            email = email.lower().strip()
            if '@' in email and '.' in email.split('@')[1]:
                emails.add(email)
                print(f"Found email: {email}")

    # Process phones with improved formatting
    phone_matches = extract_phone_numbers(text)
    phones.update(phone_matches)

    return {
        "emails": sorted(list(emails)),
        "phones": sorted(list(phones))
    }

########################################################################
# Footer and Special Address Extraction
########################################################################

def extract_footer_content(soup):
    """
    Extracts all footer content using multiple selectors and fallback methods.
    Returns the combined text from all footer-like elements.
    """
    footer_text = []
    
    # Method 1: Standard footer tag
    footer = soup.find('footer')
    if (footer):
        footer_text.append(footer.get_text(separator=' ', strip=True))
    
    # Method 2: Elements with footer-like classes or IDs
    footer_selectors = [
        # Direct footer selectors
        '[class*="footer"]', '[id*="footer"]',
        
        # Bottom area selectors
        '[class*="bottom"]', '[class*="btm"]',
        
        # Common info containers
        '.site-info', '.contact-info', '.info-section',
        '[class*="contact"]', '[class*="address"]',
        
        # Common footer alternatives
        'address', '.copyright', '.site-bottom',
        '[class*="base"]', '[class*="legal"]',
        
        # Social and contact sections
        '[class*="social"]', '[class*="connect"]',
        '.contact-details', '.business-info'
    ]
    
    # Process each selector
    for selector in footer_selectors:
        try:
            elements = soup.select(selector)
            for elem in elements:
                # Get text content
                text = elem.get_text(separator=' ', strip=True)
                if text and len(text) > 20:  # Minimum content length
                    footer_text.append(text)
                    
                # Also check for data attributes that might contain contact info
                for attr in ['data-address', 'data-contact', 'data-location']:
                    if elem.has_attr(attr):
                        footer_text.append(elem[attr].strip())
        except Exception as e:
            print(f"Error processing selector {selector}: {e}")
            continue
    
    # Clean and combine all found text
    combined = ' '.join(footer_text)
    # Remove excessive whitespace
    combined = re.sub(r'\s+', ' ', combined)
    
    print(f"DEBUG: Found footer content length: {len(combined)}")
    return combined

def extract_abbey_road_address(text):
    """
    Attempts to extract a specific address format for Abbey Road Studios.
    Returns a dictionary with 'address' and 'phone', or None if not found.
    """
    patterns = [
        r"Abbey Road Studios\s*\|\s*3 Abbey Road\s*\|\s*St\. John's Wood\s*London\s*NW8\s*9AY\s*\|\s*tel:\s*\+44\s*\(0\)20\s*7266\s*7000",
        r"Registered office:\s*4 Pancras Square,\s*Kings Cross,\s*London\s*N1C\s*4AG",
        r"(?:Abbey Road Studios|3 Abbey Road).*?(?:London\s+NW8\s+9AY)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            address = match.group(0).strip()
            if "tel:" in address.lower():
                address, phone = address.split("tel:")
                return {"address": address.strip(), "phone": phone.strip()}
            return {"address": address, "phone": ""}
    return None

########################################################################
# GPT-Assisted Address Extraction
########################################################################

def extract_potential_address(text, soup=None):
    """
    Uses enhanced regex patterns (and footer content if available) to extract candidate addresses.
    """
    footer_text = ""
    if soup:
        footer = soup.find('footer')
        if footer:
            footer_text += footer.get_text(separator=' ', strip=True) + "\n"
        footer_selectors = ['footer', '[class*="footer"]', '[class*="bottom"]', '.contact-info', 'address']
        for selector in footer_selectors:
            elements = soup.select(selector)
            for elem in elements:
                footer_text += elem.get_text(separator=' ', strip=True) + "\n"
    if footer_text:
        print(f"DEBUG: Found footer text: {footer_text[:200]}...")
        text = f"{text}\n{footer_text}"
    patterns = [
        r"([A-Za-z0-9\s]+\|[^|]+\|[^|]+(?:London|Manchester|Birmingham)[^|]*[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})",
        r"(?:Registered\s+(?:Office|Address)):\s*([^\.]+?(?:[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}))",
        r"([A-Za-z0-9\s,\.]+(?:Street|St|Road|Rd|Lane|Ln|Avenue|Ave|Way|Close|Cl)[^,]*,[^,]+,[^,]*[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})",
        r"([A-Za-z0-9\s\-\']+(?:Studios|House|Building|Centre|Center),?[^,]*,[^,]+,[^,]*[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2})",
        r"(?:[A-Za-z0-9\s,.'-]+)?(?:[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][A-Z]{2})(?:[A-Za-z0-9\s,.'-]+)?",
        r"\b\d+[\s,]+[A-Za-z0-9\s,.-]+(Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Close|Cl|Drive|Dr|Way|Court|Ct)[A-Za-z0-9\s,.-]+"
    ]
    found_texts = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            matched_text = match.group(1) if len(match.groups()) > 0 else match.group(0)
            found_texts.append(matched_text.strip())
            print(f"DEBUG: Found address match: {matched_text}")
    filtered = [t for t in found_texts if len(t.split()) >= 4]
    return "\n".join(sorted(set(filtered))) if filtered else text

def extract_address_fields_gpt(text, soup=None):
    """
    Uses ChatGPT (via the OpenAI API) to parse out a structured address.
    Combines the potential address (including footer content) with GPT extraction.
    Falls back to a postcode-based subsegment if needed.
    """
    text_to_process = extract_potential_address(text, soup)
    print(f"DEBUG: Processing text for address extraction: {text_to_process[:200]}...")
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

def extract_name_gpt(text):
    """
    Uses ChatGPT to guess a name from a short description.
    Returns the guessed name as a string.
    """
    NAME_PROMPT = """You have a short site or listing description. 
Try to guess the name of the site or listing from the text. 
Return just the name, or an empty string if not found.

Text:
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

########################################################################
# Additional GPT-based City/Country Extraction and Helpers
########################################################################

def extract_city_country_gpt(text):
    """
    First attempts extraction using GeoText.
    If not found, falls back to GPT.
    """
    CITY_COUNTRY_PROMPT = """Based on the text below, try to extract city and country if they appear. 
Return JSON with keys: "City", "Country". If you cannot find them, leave them empty.

Text:
"""
    places = GeoText(text)
    city = places.cities[0] if places.cities else ""
    country = places.countries[0] if places.countries else ""
    if city or country:
        return {"City": city, "Country": country}
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

def combine_into_single_address(row):
    """
    Combines address subfields into a single 'Full address' string.
    """
    parts = []
    for field in ["Address line 1", "Address line 2", "City", "County", "Post code", "Country"]:
        val = str(row.get(field, "")).strip()
        if val:
            parts.append(val)
    return ", ".join(parts)

# Add DummyResponse class for proxy fallback
class DummyResponse:
    def __init__(self, text):
        self.status_code = 200
        self.text = text