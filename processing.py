# processing.py

import time
import re
import pandas as pd
from urllib.parse import urljoin
from io import StringIO
import os
import streamlit as st
from bs4 import BeautifulSoup

# Import functions from other modules.
# (Make sure these modules exist and export the functions listed below.)
from scraper import (
    try_url_variants,
    quick_extract_contact_info,
    quick_extract_address,
    quick_extract_images,
    find_all_images_500,
    try_fetch_image,
    find_social_links,
    find_contact_page_url,
    get_contact_page_text,
    build_absolute_url,
    extract_contact_info,  # Added this
    extract_footer_content,  # Added this
    extract_address_fields_gpt  # Added this
)
from extraction import extract_contact_info
from gpt_helpers import extract_address_fields_gpt

# ---------------------------
# Utility Functions
# ---------------------------

def auto_download_csv(df, prefix=""):
    # Minimal implementation: do nothing (or optionally save to disk)
    return

def cleanup_address_lines(df):
    # Minimal implementation: return the DataFrame unchanged
    return df

def ensure_string_format(value):
    # Minimal implementation: always return a string
    return str(value)

def guess_column_mapping(df_columns):
    # Minimal implementation: map "URL" to the first column if available
    mapping = {"URL": df_columns[0] if df_columns else ""}
    # Optionally set empty mappings for other expected columns
    for col in ["Name", "Type", "Sub Type", "Description", "ScrapedText",
                "Address line 1", "Address line 2", "City", "County", "Country",
                "Post code", "Country code", "State"]:
        mapping.setdefault(col, "")
    return mapping

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

# ---------------------------
# Main Processing Function
# ---------------------------

# NEW: Helper function to scan candidate pages for an address
def extract_address_from_candidates(session, base_url, soup):
    """
    Automatically gathers candidate page URLs from navigation and footer elements,
    attempts address extraction via GPT on each, and returns the first valid address.
    """
    candidate_links = set()
    keywords = ['contact', 'address', 'about', 'team', 'location', 'office', 'find us']
    # Search in nav, header, and footer
    for section in soup.find_all(['nav', 'header', 'footer']):
        for a in section.find_all('a', href=True):
            text = a.get_text(separator=" ", strip=True).lower()
            href = a['href'].lower()
            if any(kw in text or kw in href for kw in keywords):
                candidate_links.add(urljoin(base_url, a['href']))
    
    valid_address = None
    from gpt_helpers import extract_address_fields_gpt
    from azure import is_postcode_valid
    # Iterate over candidate pages (sequentially for stability)
    for link in candidate_links:
        try:
            r = session.get(link, timeout=10, verify=False)
            if r.status_code == 200:
                candidate_soup = BeautifulSoup(r.text, "html.parser")
                candidate_text = candidate_soup.get_text(separator=" ", strip=True)
                candidate_addr = extract_address_fields_gpt(candidate_text, candidate_soup)
                if candidate_addr and candidate_addr.get("Full address"):
                    postcode = candidate_addr.get("Post code", "").strip()
                    if is_postcode_valid(postcode):
                        print(f"Candidate URL {link} yielded valid address.")
                        valid_address = candidate_addr
                        break
        except Exception as e:
            print(f"Error scanning candidate URL {link}: {e}")
    return valid_address

def process_row(i, row, df, s, final_type, gig_synonyms):
    """Modified process_row with correct footer extraction"""
    url = str(row.get("URL", "")).strip()
    df.at[i, "Error"] = ""
    
    if not url:
        df.at[i, "Error"] = "No URL provided"
        return
        
    domain = url.replace("http://", "").replace("https://", "").strip("/")
    print(f"Processing row {i + 1}: {domain}")
    
    try:
        # Get webpage with fallbacks
        resp, final_url, err = try_url_variants(s, domain)
        if not resp or resp.status_code != 200:
            df.at[i, "Error"] = err or f"HTTP {resp.status_code if resp else 'error'}"
            return
            
        # Parse content
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Get footer and main content
        footer_content = extract_footer_content(soup)  # Now properly imported from scraper.py
        main_content = soup.get_text(separator=" ", strip=True)
        combined_text = f"{main_content}\n{footer_content}"
        
        # Extract contact info from combined text
        contact_info = extract_contact_info(combined_text)
        df.at[i, "EmailContacts"] = sorted(list(set(contact_info["emails"])))
        df.at[i, "PhoneContacts"] = sorted(list(set(contact_info["phones"])))
        
        # Get contact page for additional info
        contact_url = find_contact_page_url(soup, final_url)
        if contact_url:
            contact_text = get_contact_page_text(s, contact_url, final_url)
            if contact_text:
                contact_info2 = extract_contact_info(contact_text)
                # Merge new contact info
                df.at[i, "EmailContacts"].extend(contact_info2["emails"])
                df.at[i, "PhoneContacts"].extend(contact_info2["phones"])
                # Deduplicate
                df.at[i, "EmailContacts"] = sorted(list(set(df.at[i, "EmailContacts"])))
                df.at[i, "PhoneContacts"] = sorted(list(set(df.at[i, "PhoneContacts"])))
        
        # Extract address with GPT
        address_data = extract_address_fields_gpt(combined_text, soup)
        from azure import is_postcode_valid
        if not (address_data and address_data.get("Full address") and is_postcode_valid(address_data.get("Post code", "").strip())):
            print("Primary extraction failed; scanning candidate pages.")
            # Call the new candidate scanning function
            candidate_address = extract_address_from_candidates(s, final_url, soup)
            if candidate_address and candidate_address.get("Full address"):
                address_data = candidate_address
                print("Candidate page extraction successful.")
        if address_data and address_data.get("Full address"):
            for field in ["Full address", "Address line 1", "Address line 2", 
                         "City", "County", "Country", "Post code", "Country code"]:
                if field in address_data:
                    df.at[i, field] = address_data[field]
        
        # Extract images with proxy fallback
        images = set()
        quick_images = quick_extract_images(soup, s, final_url)
        if quick_images:
            images.update(quick_images)
            
        thorough_images = find_all_images_500(soup, s, final_url)
        if thorough_images:
            images.update(thorough_images)
            
        # Try proxy for problematic images
        proxy_url = "https://proxyapp-hjeqhbg2h2c2baay.uksouth-01.azurewebsites.net/proxy"
        proxy_images = []
        for img_url in images:
            size = try_fetch_image(s, img_url, proxy_url)
            if size:
                proxy_images.append(img_url)
                
        df.at[i, "AllImages"] = sorted(list(set(images).union(proxy_images)))
        
        # Get social media links
        social = find_social_links(soup)
        df.at[i, "InstagramURL"] = social["instagram_url"] or ""
        df.at[i, "FacebookURL"] = social["facebook_url"] or ""
        df.at[i, "TwitterURL"] = social["twitter_url"] or ""
        df.at[i, "LinkedInURL"] = social["linkedin_url"] or ""
        df.at[i, "YoutubeURL"] = social["youtube_url"] or ""
        df.at[i, "TiktokURL"] = social["tiktok_url"] or ""
        
        # Store raw text for later use
        df.at[i, "ScrapedText"] = combined_text
        
        # Special handling for venues - look for gig listings
        if final_type.lower() == "venues":
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].lower()
                text = a_tag.get_text(separator=" ", strip=True).lower()
                if any(syn in href or syn in text for syn in gig_synonyms):
                    df.at[i, "GigListingURL"] = build_absolute_url(a_tag["href"], final_url)
                    break
        
        print(f"✓ Processed {domain} successfully")
        
    except Exception as e:
        df.at[i, "Error"] = f"Processing error: {str(e)}"
        print(f"⚠️ Error processing row {i + 1}: {e}")
        
    time.sleep(1)  # Rate limiting

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
        return False, missing
    return True, []

# ---------------------------
# Expected Columns (for mapping)
# ---------------------------
EXPECTED_COLUMNS = {
    "URL": ["url", "website", "web", "link", "address"],
    "Name": ["name", "business_name", "company", "title"],
    "Type": ["type", "category", "business_type"],
    "Sub Type": ["sub_type", "subcategory", "sub"],
    "Description": ["description", "desc", "about", "details"],
    "ScrapedText": ["scraped_text", "raw_text", "content", "page_text", "text_content"],
    "Address line 1": ["address1", "address_1", "street", "address_line_1"],
    "Address line 2": ["address2", "address_2", "address_line_2"],
    "City": ["city", "town", "municipality"],
    "County": ["county", "region", "province", "state"],
    "Country": ["country", "nation"],
    "Post code": ["postcode", "zip", "zip_code", "postal_code", "postal"],
    "Country code": ["country_code", "countrycode", "iso_code"],
    "State": ["state", "province", "region"],
}

# ---------------------------
# (Optional) Main Testing Block
# ---------------------------
if __name__ == "__main__":
    # For testing purposes, load a sample CSV and process rows.
    # Example usage:
    sample_df = pd.read_csv("sample_urls.csv")
    # Optionally, define final_type and gig_synonyms as needed.
    final_type = "Services"
    gig_synonyms = []  # or list your synonyms here
    # Create a requests session with default settings.
    import requests
    from requests.adapters import HTTPAdapter
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=1)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Process each row in the DataFrame
    for i, row in sample_df.iterrows():
        process_row(i, row, sample_df, session, final_type, gig_synonyms)
        time.sleep(1)
    
    # Cleanup address lines and print the final DataFrame
    sample_df = cleanup_address_lines(sample_df)
    print(sample_df.head())
