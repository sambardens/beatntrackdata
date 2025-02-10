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
from duckduckgo import get_address_and_phone_from_duckduckgo

# ---------------------------
# Utility Functions
# ---------------------------

def auto_download_csv(df, prefix=""):
    # Minimal implementation: do nothing (or optionally save to disk)
    return

def cleanup_address_lines(df):
    """Enhanced address cleanup that properly splits components"""
    for i, row in df.iterrows():
        full_address = str(row.get('Full address', '')).strip()
        if not full_address:
            continue

        # 1. Ensure country is in full address
        country = row.get('Country', '').strip()
        if country and country.lower() not in full_address.lower():
            if country.lower() in ['uk', 'gb']:
                country = 'United Kingdom'
            full_address = f"{full_address}, {country}"
            df.at[i, 'Full address'] = full_address

        # 2. Split components by comma
        components = [comp.strip() for comp in full_address.split(',')]
        if len(components) < 3:
            continue  # Not enough components for valid address

        # 3. Process components from end to start
        for comp in reversed(components):
            comp = comp.strip()
            
            # Check for postcode
            if re.match(r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$', comp, re.I):
                df.at[i, 'Post code'] = comp
                components.remove(comp)
                continue
                
            # Check for country
            if comp.lower() in ['united kingdom', 'uk', 'great britain', 'england']:
                df.at[i, 'Country'] = 'United Kingdom'
                components.remove(comp)
                continue
                
            # Check for known cities
            if any(city in comp.lower() for city in ['london', 'manchester', 'birmingham', 'leeds', 'letchworth']):
                df.at[i, 'City'] = comp
                components.remove(comp)
                continue

        # 4. Handle remaining components
        if components:
            # If 3 or more components remain, combine first two for Address line 1
            if len(components) >= 3:
                df.at[i, 'Address line 1'] = f"{components[0]}, {components[1]}"
                if len(components) > 3:
                    df.at[i, 'Address line 2'] = components[2]
                # If city wasn't found earlier, use the last component
                if not df.at[i, 'City']:
                    df.at[i, 'City'] = components[-1]
            # If 2 components remain
            elif len(components) == 2:
                df.at[i, 'Address line 1'] = components[0]
                df.at[i, 'Address line 2'] = components[1]
            # If only 1 component remains
            elif len(components) == 1:
                df.at[i, 'Address line 1'] = components[0]

        # 5. Ensure Country and Country code are set correctly
        if df.at[i, 'Country'] == 'United Kingdom':
            df.at[i, 'Country code'] = 'GB'
        
        print(f"Cleaned address for row {i}:")
        print(f"Full address: {df.at[i, 'Full address']}")
        print(f"Address line 1: {df.at[i, 'Address line 1']}")
        print(f"Address line 2: {df.at[i, 'Address line 2']}")
        print(f"City: {df.at[i, 'City']}")
        print(f"Post code: {df.at[i, 'Post code']}")
        print(f"Country: {df.at[i, 'Country']}")
        print("-" * 50)

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

def extract_postcode_from_text(text):
    """Extract postcode from Companies House or general text"""
    # Look specifically for Companies House format first
    ch_pattern = r"[Rr]egistered\s+office\s+address[^.]*?([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})"
    ch_match = re.search(ch_pattern, text, re.IGNORECASE)
    if ch_match:
        return ch_match.group(1).strip()
    
    # Then try general UK postcode pattern
    uk_pattern = r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}"
    postcode_matches = re.findall(uk_pattern, text, re.IGNORECASE)
    if postcode_matches:
        postcode = re.sub(r'\s+', ' ', postcode_matches[0].strip())
        if re.match(r'^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$', postcode, re.I):
            return postcode
    return None

def process_row(i, row, df, s, final_type, gig_synonyms):
    """Modified process_row with better DuckDuckGo integration"""
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
        if address_data and address_data.get("Full address"):
            for field in ["Full address", "Address line 1", "Address line 2", 
                         "City", "County", "Country", "Post code", "Country code"]:
                if field in address_data:
                    df.at[i, field] = address_data[field]
        
        # After GPT address extraction fails or returns empty results, try DuckDuckGo
        if not df.at[i, "Post code"].strip():
            try:
                business_name = df.at[i, "Name"]
                country = df.at[i, "Country"] or "United Kingdom"  # Default to UK if not specified
                
                if business_name:
                    print(f"Running DuckDuckGo search for: {business_name}")
                    duck_address, duck_phones = get_address_and_phone_from_duckduckgo(business_name, country)
                    
                    if duck_address:
                        # Update address fields
                        for field in ["Full address", "Address line 1", "Address line 2", 
                                    "City", "County", "Post code"]:
                            if field in duck_address and duck_address[field]:
                                df.at[i, field] = duck_address[field]
                                print(f"DuckDuckGo found {field}: {duck_address[field]}")
                        
                        # Merge any new phone numbers found
                        if duck_phones:
                            existing_phones = df.at[i, "PhoneContacts"]
                            if isinstance(existing_phones, list):
                                df.at[i, "PhoneContacts"] = sorted(list(set(existing_phones + duck_phones)))
                            else:
                                df.at[i, "PhoneContacts"] = duck_phones
                            
                        print("DuckDuckGo search successful")
                        df.at[i, "Error"] = (df.at[i, "Error"] or "") + " | DuckDuckGo: Success"
                    else:
                        print("DuckDuckGo found no valid address")
                        df.at[i, "Error"] = (df.at[i, "Error"] or "") + " | DuckDuckGo: No address found"
                else:
                    print("Skipping DuckDuckGo - no business name")
                    df.at[i, "Error"] = (df.at[i, "Error"] or "") + " | DuckDuckGo: No business name"
                    
            except Exception as e:
                print(f"DuckDuckGo error: {str(e)}")
                df.at[i, "Error"] = (df.at[i, "Error"] or "") + f" | DuckDuckGo error: {str(e)}"
        
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
