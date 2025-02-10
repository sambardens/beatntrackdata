# processing.py

import time
import re
import pandas as pd
from urllib.parse import urljoin
from io import StringIO
import os
import streamlit as st
from bs4 import BeautifulSoup
import random
import requests
from requests.adapters import HTTPAdapter
import gpt_helpers  # Add this import

# Import functions from other modules
from scraper import (
    try_url_variants,
    quick_extract_contact_info,  # This will now use the correct version
    quick_extract_address,
    quick_extract_images,
    find_all_images_500,
    try_fetch_image,
    find_social_links,
    find_contact_page_url,
    get_contact_page_text,
    build_absolute_url,
    extract_contact_info,
    extract_footer_content,
)
from gpt_helpers import extract_address_fields_gpt
from azure import thorough_azure_lookup  # new import

# ---------------------------
# Utility Functions
# ---------------------------

def auto_download_csv(df, prefix=""):
    # Minimal implementation: do nothing (or optionally save to disk)
    return

def cleanup_address_lines(df):
    # Minimal implementation: return the DataFrame unchanged
    for i, row in df.iterrows():
        line2 = row.get("Address line 2", "")
        city = row.get("City", "")
        if line2.strip().lower() == city.strip().lower():
            df.at[i, "Address line 2"] = ""
    return df

def ensure_string_format(value):
    # Minimal implementation: always return a string
    return str(value)

def adaptive_delay(min_seconds, max_seconds):
    """Add a random delay between min_seconds and max_seconds"""
    time.sleep(min_seconds + (max_seconds - min_seconds) * random.random())

def wait_for_page_load(soup):
    """Check if the page has loaded by verifying basic HTML structure."""
    return bool(soup and soup.find('body'))

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

def process_row(i, row, df, s, final_type, gig_synonyms):
    """Enhanced row processing with multi-attempt Azure fallback for missing postcode"""
    url = str(row.get("URL", "")).strip()
    df.at[i, "Error"] = ""
    
    if not url:
        df.at[i, "Error"] = "No URL provided"
        return
        
    domain = url.replace("http://", "").replace("https://", "").strip("/")
    print(f"Processing row {i + 1}: {domain}")
    
    try:
        # Get webpage with better load verification
        resp, final_url, err = try_url_variants(s, domain)
        if not resp or resp.status_code != 200:
            df.at[i, "Error"] = err or f"HTTP {resp.status_code if resp else 'error'}"
            return
            
        # Parse and verify content
        soup = BeautifulSoup(resp.text, "html.parser")
        if not wait_for_page_load(soup):
            df.at[i, "Error"] = "Page failed to load completely"
            return
            
        # Add delay before content extraction
        adaptive_delay(1, 2)
        
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
                
        # Ensure AllImages is always a list
        all_images = sorted(list(set(images).union(proxy_images)))
        df.at[i, "AllImages"] = all_images if isinstance(all_images, list) else [all_images]
        
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

        # After initial scraping
        entry = row.to_dict()
        
        # Enhanced Azure lookup
        updated_entry = thorough_azure_lookup(entry)
        
        # Update DataFrame with enriched data
        for key, value in updated_entry.items():
            if value:  # Only update non-empty values
                df.at[i, key] = value

        # Multi-attempt fallback if no Post code (up to 3 tries)
        attempt = 1
        while attempt < 4 and not df.at[i, "Post code"]:
            print(f"Post code still missing for {domain}: Attempt {attempt} extra fallback")
            entry = df.loc[i].to_dict()
            updated_entry = thorough_azure_lookup(entry)
            if updated_entry:
                for field in ["Full address", "Address line 1", "Address line 2", 
                              "City", "County", "Country", "Post code", "Country code"]:
                    if updated_entry.get(field) and not df.at[i, field]:
                        df.at[i, field] = updated_entry[field]
            # Optionally re-run parts of the scraping workflow (e.g. re-fetch contact page)
            if not df.at[i, "Post code"]:
                alt_contact_url = find_contact_page_url(soup, final_url)
                if alt_contact_url:
                    alt_text = get_contact_page_text(s, alt_contact_url, final_url)
                    if alt_text:
                        alt_address = extract_address_fields_gpt(alt_text, soup)
                        if alt_address and alt_address.get("Post code"):
                            for field in ["Full address", "Address line 1", "Address line 2", 
                                          "City", "County", "Country", "Post code", "Country code"]:
                                if alt_address.get(field):
                                    df.at[i, field] = alt_address[field]
            attempt += 1

        # After getting ScrapedText
        if combined_text:
            # Extract contacts using GPT
            gpt_contacts = gpt_helpers.extract_contacts_gpt(combined_text)
            
            # Convert existing contacts to lists if they're strings
            existing_emails = df.at[i, "EmailContacts"]
            existing_phones = df.at[i, "PhoneContacts"]
            
            if isinstance(existing_emails, str):
                existing_emails = existing_emails.split(',') if existing_emails else []
            if isinstance(existing_phones, str):
                existing_phones = existing_phones.split(',') if existing_phones else []
                
            existing_contacts = {
                "emails": existing_emails if isinstance(existing_emails, list) else [],
                "phones": existing_phones if isinstance(existing_phones, list) else []
            }
            
            merged_contacts = gpt_helpers.merge_contacts(existing_contacts, gpt_contacts)
            
            # Update DataFrame with merged results
            df.at[i, "EmailContacts"] = merged_contacts["emails"]
            df.at[i, "PhoneContacts"] = merged_contacts["phones"]
        
        # Get existing ScrapedText content
        existing_text = df.at[i, "ScrapedText"]
        if isinstance(existing_text, float):  # Handle NaN
            existing_text = ""
        
        # Initialize new text collection
        new_text_parts = []
        
        # Add homepage text if available
        if main_content:
            new_text_parts.append("Homepage Content:\n" + main_content)
        
        # Add contact page text if available
        if contact_text:
            new_text_parts.append("Contact Page Content:\n" + contact_text)
            
        # Add footer content if available
        footer_content = extract_footer_content(soup)
        if footer_content:
            new_text_parts.append("Footer Content:\n" + footer_content)
        
        # Combine new text
        new_text = "\n=====\n".join(filter(None, new_text_parts))
        
        # Append new text to existing text if there is any
        if existing_text and new_text:
            combined_text = f"{existing_text}\n=====\nNew Scrape Results:\n{new_text}"
        else:
            combined_text = new_text or existing_text
            
        # Update DataFrame with combined text
        df.at[i, "ScrapedText"] = combined_text
        
        # Continue with contact extraction using combined text
        if combined_text:
            # Extract contacts using both methods
            emails, phones = quick_extract_contact_info(soup, combined_text)
            
            # Then try GPT extraction for additional results
            gpt_contacts = gpt_helpers.extract_contacts_gpt(combined_text)
            
            # Merge results
            all_emails = set(emails + gpt_contacts.get("emails", []))
            all_phones = set(phones + gpt_contacts.get("phones", []))
            
            # Update DataFrame
            df.at[i, "EmailContacts"] = list(all_emails)
            df.at[i, "PhoneContacts"] = list(all_phones)
        
        print(f"✓ Processed {domain} successfully")
        
    except Exception as e:
        df.at[i, "Error"] = f"Processing error: {str(e)}"
        print(f"⚠️ Error processing row {i + 1}: {e}")
        
    adaptive_delay(2, 4)

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

def run_azure_fallback_on_df(df):
    """Improved Azure fallback that runs on every row"""
    print("Running Azure fallback on all rows...")
    for i, row in df.iterrows():
        try:
            entry = row.to_dict()
            print(f"\nProcessing row {i+1} with Azure...")
            updated_entry = thorough_azure_lookup(entry)
            
            # Update fields if Azure returned results
            if updated_entry:
                for field in ["Full address", "Address line 1", "Address line 2", 
                            "City", "County", "Country", "Post code", "Country code"]:
                    if updated_entry.get(field):
                        df.at[i, field] = updated_entry[field]
        except Exception as e:
            print(f"Error in Azure fallback for row {i+1}: {e}")
            
    return df

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
    
    # Cleanup address lines
    sample_df = cleanup_address_lines(sample_df)
    
    # Run the Azure fallback for rows missing/with invalid "Post code"
    sample_df = run_azure_fallback_on_df(sample_df)
    
    print(sample_df.head())
