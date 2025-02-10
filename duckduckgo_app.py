import streamlit as st
import pandas as pd
import re
from duckduckgo import get_address_and_phone_from_duckduckgo

# Page config
st.set_page_config(page_title="DuckDuckGo Address Finder", page_icon="🔍")

# Title and description
st.title("🦆 DuckDuckGo Address Finder")
st.write("Enter a business name to search for its address and phone numbers.")

# Input fields
col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("Business Name:")
with col2:
    country = st.selectbox(
        "Country:",
        ["United Kingdom", "United States"],
        index=0
    )

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
        # Clean and validate the first found postcode
        postcode = re.sub(r'\s+', ' ', postcode_matches[0].strip())
        if re.match(r'^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$', postcode, re.I):
            return postcode
    return None

# Search button
if st.button("Search", type="primary"):
    if query:
        with st.spinner("Searching DuckDuckGo..."):
            # Get results
            address_dict, phones = get_address_and_phone_from_duckduckgo(query, country)
            
            # Store the raw text in address_dict for processing
            raw_text = address_dict.get("ScrapedText", "")
            if raw_text:
                # Try to find postcode in raw text
                postcode = extract_postcode_from_text(raw_text)
                if postcode:
                    print(f"Found postcode in raw text: {postcode}")
                    address_dict["Post code"] = postcode
                    if "Full address" in address_dict:
                        address_dict["Full address"] = f"{address_dict['Full address']}, {postcode}"

            # Display results in a DataFrame
            if address_dict or phones:
                # Show raw scraped text for debugging
                st.subheader("🔍 Raw Search Results")
                st.text(raw_text)
                
                # Create DataFrame for address, ensuring postcode is included
                if address_dict.get("Post code"):
                    if "Full address" in address_dict and address_dict["Post code"] not in address_dict["Full address"]:
                        address_dict["Full address"] = f"{address_dict['Full address']}, {address_dict['Post code']}"
                
                # Create address DataFrame
                address_df = pd.DataFrame([address_dict])
                
                # Create DataFrame for phones
                phones_df = pd.DataFrame({
                    "Phone Numbers": phones if phones else ["No phone numbers found"]
                })
                
                # Show results
                st.subheader("📍 Address Details")
                st.dataframe(address_df, use_container_width=True)
                
                st.subheader("📞 Phone Numbers")
                st.dataframe(phones_df, use_container_width=True)
                
                # Show postcode separately for clarity
                if address_dict.get("Post code"):
                    st.success(f"Found Postcode: {address_dict['Post code']}")
            else:
                st.error("No results found")
    else:
        st.warning("Please enter a business name")

# Footer
st.markdown("---")
st.markdown("### How to use:")
st.markdown("""
1. Enter a business name in the search box
2. Select the country
3. Click 'Search' to find address and phone numbers
4. Results will appear in tables below
""")
