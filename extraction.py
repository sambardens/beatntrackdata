# extraction.py

import re
import phonenumbers
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests

###############################
# URL Helper (used by some functions)
###############################

def build_absolute_url(relative_url, base_url):
    """Return an absolute URL based on a relative URL and a base URL."""
    if relative_url.lower().startswith("http") or relative_url.lower().startswith("data:image"):
        # If already an absolute URL or data URI, return as is
        return relative_url
    return urljoin(base_url, relative_url)

###############################
# Email and Phone Extraction
###############################

def find_emails(text):
    """
    Extract email addresses using several regex patterns.
    Returns a list of deduplicated email addresses.
    """
    email_patterns = [
        r'(?:^|[\s<(\[])([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)(?:$|[\s>)\]])',
        r'(?:email|e-?mail|contact)[:;\s]*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
        r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
    ]
    found_emails = set()
    text = text.replace('\n', ' ')
    for pattern in email_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            email = match.group(1).strip().lower()
            if '@' in email and '.' in email.split('@')[1]:
                found_emails.add(email)
    return list(found_emails)

def find_phone_numbers(text):
    """
    Extract UK phone numbers using regex patterns and validate them with phonenumbers.
    Returns a list of deduplicated, formatted phone numbers.
    """
    uk_patterns = [
        r'(?:tel|phone)[\s:.-]*(\+?\d[\d\s\-()]+)',
    ]
    formatted_numbers = set()
    text = text.replace('\n', ' ')
    for pattern in uk_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            number = re.sub(r'[^\d+]', '', match.group(1))
            try:
                if number.startswith('0'):
                    number = '+44' + number[1:]
                parsed = phonenumbers.parse(number, "GB")
                if phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    formatted_numbers.add(formatted)
            except Exception as e:
                print(f"Phone parsing error: {e}")
    return list(formatted_numbers)

def extract_contact_info(text):
    """
    Extracts email addresses and phone numbers from a given text.
    Returns a dictionary with keys 'emails' and 'phones'.
    """
    emails = find_emails(text)
    phones = find_phone_numbers(text)
    return {"emails": emails, "phones": phones}

###############################
# Footer Extraction
###############################

def extract_footer_content(soup):
    """
    Extracts footer content from a BeautifulSoup object using the <footer> tag
    and common footer-related selectors.
    """
    footer_text = []
    footer = soup.find('footer')
    if footer:
        footer_text.append(footer.get_text(separator=' ', strip=True))
    for selector in ['[class*="footer"]', '[class*="bottom"]', '.site-info', '.contact-info']:
        for elem in soup.select(selector):
            footer_text.append(elem.get_text(separator=' ', strip=True))
    return ' '.join(footer_text)

###############################
# Homepage SEO and Text Extraction
###############################

def get_homepage_seo_text(soup):
    """
    Extracts SEO-related text from a page (title, meta description, keywords, OG description).
    Returns a newline-separated string.
    """
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
    """
    Extracts all visible text from a BeautifulSoup object.
    Limits the length to max_len characters.
    """
    text_content = soup.get_text(separator=" ", strip=True)
    return text_content[:max_len].strip()

###############################
# About and Contact Page URL Extraction
###############################

def find_about_page_url(soup, base_url):
    """
    Attempts to find the URL for the 'About' page by searching for links
    that contain the word "about".
    """
    for a_tag in soup.find_all("a", href=True, string=True):
        t = a_tag.get_text(separator=" ", strip=True).lower()
        h = a_tag["href"].lower().strip()
        if "about" in t or "about" in h:
            return build_absolute_url(a_tag["href"], base_url)
    return None

def find_contact_page_url(soup, base_url):
    """
    Enhanced contact page detection that returns multiple potential pages.
    """
    # Expanded keyword list
    contact_keywords = [
        'contact', 'contact-us', 'contactus',
        'address', 'location', 'directions',
        'visit', 'visiting', 'find-us', 'findus',
        'reach-us', 'reach', 'get-here',
        'where', 'travel', 'getting-here',
        'about/contact', 'help/contact'
    ]
    
    candidates = []
    
    # Look for links containing our keywords
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '').strip().lower()
        text = a_tag.get_text(separator=' ', strip=True).lower()
        
        # Skip obvious non-contact pages
        if any(x in href for x in ['.jpg', '.png', '.pdf', 'login', 'signup', 'cart']):
            continue
            
        # Score URLs based on relevance
        score = 0
        for keyword in contact_keywords:
            if keyword in href:
                score += 3
            if keyword in text:
                score += 2
                
        if score > 0:
            full_url = build_absolute_url(href, base_url)
            candidates.append((full_url, score))
    
    # Sort candidates by score
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Return the best matching URL if found
    if candidates:
        return candidates[0][0]
    
    # Add fallback paths
    domain = base_url.rstrip('/')
    for path in ['/contact-us', '/contact', '/visit', '/directions', '/find-us']:
        full_url = build_absolute_url(path, base_url)
        try:
            r = requests.get(full_url, timeout=5)
            if r.status_code == 200:
                return full_url
        except Exception:
            continue
            
    return None

def find_all_contact_pages(soup, base_url):
    """
    Find all pages that might contain contact/address information.
    Returns a list of URLs to check.
    """
    contact_pages = set()
    contact_keywords = [
        'contact', 'address', 'location', 'directions', 'find-us', 'findus',
        'visit', 'where', 'about', 'info', 'reach'
    ]
    
    # Find all links in the page
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '').strip().lower()
        text = a_tag.get_text(separator=' ', strip=True).lower()
        
        # Skip obvious non-contact pages
        if any(x in href for x in ['.jpg', '.png', '.pdf', 'login', 'signup', 'cart']):
            continue
            
        # Check both href and text for contact keywords
        if any(keyword in href or keyword in text for keyword in contact_keywords):
            full_url = build_absolute_url(href, base_url)
            contact_pages.add(full_url)
    
    # Add common fallback paths
    domain = base_url.rstrip('/')
    fallback_paths = [
        '/contact', '/contact-us', '/directions',
        '/visit', '/find-us', '/location',
        '/about/contact', '/help/contact',
        '/address', '/venues/contact'
    ]
    
    for path in fallback_paths:
        contact_pages.add(build_absolute_url(path, base_url))
    
    return sorted(list(contact_pages))

def scrape_all_contact_pages(session, urls, base_url):
    """Visit each potential contact page and extract information."""
    all_text = []
    
    # Special handling for PRS Music
    if any(domain in base_url.lower() for domain in ["prsformusic.com", "prs.co.uk", "prsmusic.com"]):
        # Force scraping of help/contact-us page
        base_domain = base_url.split('/')[2]
        contact_url = f"https://{base_domain}/help/contact-us"
        try:
            print(f"Scraping forced PRS contact URL: {contact_url}")
            r = session.get(contact_url, timeout=10, verify=False)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Look specifically for address section
                address_elements = soup.find_all(['div', 'section', 'p'], 
                    string=lambda text: text and any(x in text.lower() for x in 
                        ['streatham high road', '41 streatham', 'london sw16']))
                
                if address_elements:
                    for elem in address_elements:
                        all_text.append(elem.get_text(separator=' ', strip=True))
                    print(f"Found PRS address in forced contact page")
                    return "\n".join(all_text)
                    
        except Exception as e:
            print(f"Error scraping PRS contact page: {e}")
    
    # Regular scraping for other sites
    for url in urls:
        try:
            print(f"Checking potential contact page: {url}")
            r = session.get(url, timeout=10, verify=False)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
                all_text.append(text)
                
                # If we find what looks like an address, prioritize this page
                if re.search(r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}', text):  # UK postcode
                    print(f"Found address in: {url}")
                    return text
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    
    # Return combined text from all pages if no clear address was found
    return "\n=====\n".join(all_text)

###############################
# Special and Quick Extraction
###############################

def extract_abbey_road_address(text):
    """
    Attempts to extract an address specific to Abbey Road Studios.
    Returns a dictionary with keys 'address' and 'phone' or None if not found.
    """
    patterns = [
        r"Abbey Road Studios\s*\|\s*3 Abbey Road\s*\|\s*St\. John's Wood\s*London\s*NW8\s*9AY\s*\|\s*tel:\s*\+44\s*\(0\)20\s*7266\s*7000",
        r"Registered office:\s*4 Pancras Square,\s*Kings Cross,\s*London\s*N1C\s*4AG",
        r"(?:Abbey Road Studios|3 Abbey Road).*?(?:London\s+NW8\s+9AY)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            address = match.group(0).strip()
            phone = ""
            if "tel:" in address.lower():
                # Simple extraction: get text following 'tel:'
                m = re.search(r"tel:\s*([\+\d\s()-]+)", address, re.IGNORECASE)
                if m:
                    phone = m.group(1).strip()
            return {"address": address, "phone": phone}
    return None

def quick_extract_address(text):
    """
    Fast initial pass to find a multi-line UK address block with context.
    Returns the extracted address string or None if not found.
    """
    postcode_re = re.compile(r'\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b', re.IGNORECASE)
    street_keywords = [' street', ' road', ' ave', ' avenue', ' lane', ' drive', ' court']
    lines = text.splitlines()
    address_blocks = []
    for i, line in enumerate(lines):
        if postcode_re.search(line) and any(kw in line.lower() for kw in street_keywords):
            block = [line.strip()]
            if i > 0 and len(lines[i-1].split()) <= 6:
                block.insert(0, lines[i-1].strip())
            address_blocks.append(" ".join(block))
    return "\n".join(address_blocks) if address_blocks else None
