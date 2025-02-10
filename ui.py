# ui.py
import streamlit as st
from io import StringIO
import pandas as pd
import requests
import time
import os
import re
from dotenv import load_dotenv
import openai
from PIL import Image
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter

# Import your helper functions from your modular files.
# (Make sure these modules are created and contain the corresponding functions.)
from processing import auto_download_csv, cleanup_address_lines, ensure_string_format, process_row, initialize_dataframe, EXPECTED_COLUMNS
from gpt_helpers import generate_gpt_description, extract_address_fields_gpt, extract_city_country_gpt, extract_name_gpt, fix_country_code
from scraper import (
    quick_extract_images, find_all_images_500, try_fetch_image, build_absolute_url, try_url_variants, find_social_links, get_contact_page_text, find_contact_page_url, quick_extract_contact_info, quick_extract_address
)
from bubble import bubble_initialize_button, bubble_send_final_button
from state_manager import StateManager
from countries import COUNTRY_DATA, get_country_code   # new import
from finalsave import finalize_data  # Add this import

# Constants for dropdown options
SERVICES_SUBTYPES = [
    "Recording Studios",
    "Rehearsal Spaces",
    "Record Shops",
    "Radio Stations",
    "Festivals",
    "Artist Managers",
    "Booking Agents",
    "Instrument Repair Services",
    "Producers",
    "Music Industry Organisations",
    "Other"
]

VENUES_SUBTYPES = [
    "Live music venue",
    "Nightclub",
    "Festival",
    "Other"
]

# Load environment variables
AZURE_MAPS_KEY = os.getenv("AZURE_MAPS_KEY")
BING_KEY = os.getenv("BING_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Custom CSS styles (same as your old code)
CUSTOM_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@400;500;600&display=swap');

:root {
    --brand-red: #FF0151;
    --dark-grey: #1E1E1E;
    --mid-grey: #2D2D2D;
    --light-grey: #E5E7EB;
    --off-white: #FDFDFD;
}

/* Modern Base Theme */
.stApp {
    background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
    font-family: 'Inter', sans-serif;
}

/* Updated Header Styles */
.header {
    background-color: #f5f5f5;
    padding: 0 2rem;
    height: 90px;  /* Increased height to match logo */
    display: flex;  /* Changed from grid to flex */
    justify-content: space-between;  /* Spread items evenly */
    align-items: center;  /* Center items vertically */
    border-bottom: 1px solid #e0e0e0;
    margin-top: 50px;
}

.header-logo {
    height: 90px;
    object-fit: contain;  /* Maintain aspect ratio */
    display: block;  /* Remove any extra space */
}

.header-title {
    color: #333333;
    font-family: 'Poppins', sans-serif;
    font-size: 24px;
    font-weight: 600;
    text-align: center;
    margin: 0;
    flex: 1;  /* Allow title to take available space */
    padding: 0 20px;  /* Add some spacing around title */
}

/* Updated Navigation Links */
.header-nav {
    display: flex;
    gap: 12px;
    align-items: center;  /* Center nav items vertically */
}

.header-nav a {
    background-color: #333333;  /* Smart black background */
    color: white !important;  /* White text */
    text-decoration: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;
    border: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-nav a:hover {
    background-color: #FF0151;  /* Changed to red on hover */
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(255,1,81,0.2);  /* Red shadow on hover */
}

/* Modern Cards */
.feature-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.5rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

.feature-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
}

/* Enhanced Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%);
    border-right: 1px solid rgba(255,255,255,0.1);
}

.streamlit-expanderHeader {
    background: #ff1744;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    transition: all 0.2s ease;
}

.streamlit-expanderHeader:hover {
    background: rgba(255,255,255,0.1);
}

/* Updated Button Styles */
.stButton > button {
    color: white !important;  /* Force white text */
    background: linear-gradient(135deg, #FF0151 0%, #ff1744 100%);
}

.stButton > button:hover {
    color: white !important;  /* Keep text white on hover */
    transform: translateY(-1px);
    box-shadow: 0 8px 16px rgba(255,1,81,0.2);
}

.stButton > button:active,
.stButton > button:focus {
    color: white !important;  /* Keep text white when active/focused */
}

/* Modern Form Inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div > div {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    transition: all 0.2s ease;
    font-size: 15px;
}

.stTextInput > div > div > input:focus,
.stSelectbox > div > div > div:focus {
    border-color: #FF0151;
    box-shadow: 0 0 0 3px rgba(255,1,81,0.1);
}

/* Status Messages */
.stSuccess {
    background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
    border: 1px solid #86efac;
    color: #166534;
}

.stInfo {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    border: 1px solid #93c5fd;
    color: #1e40af;
}

.stWarning {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 1px solid #fcd34d;
    color: #92400e;
}

.stError {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border: 1px solid #fca5a5;
    color: #991b1b;
}

/* Progress Bar */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #FF0151 0%, #ff1744 100%);
    height: 8px;
    border-radius: 4px;
}

/* DataFrames */
.stDataFrame {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

/* Typography */
h1, h2, h3, h4 {
    color: #111827;
    font-family: 'Poppins', sans-serif;
    font-weight: 600;
    letter-spacing: -0.5px;
}

/* Dark Theme Inputs */
[data-testid="stSidebar"] .stTextInput > div > div > input,
[data-testid="stSidebar"] .stSelectbox > div > div > div {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: white;
}

[data-testid="stSidebar"] .stTextInput > div > div > input:focus,
[data-testid="stSidebar"] .stSelectbox > div > div > div:focus {
    border-color: #FF0151;
    background: rgba(255,255,255,0.1);
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.main-content {
    animation: fadeIn 0.5s ease-out;
}

.feature-card {
    animation: fadeIn 0.5s ease-out;
}

/* Toggle Switch Styling */
.toggle-switch {
    display: flex;
    align-items: center;
    padding: 1rem;
    margin-bottom: 1rem;
    background: rgba(255,255,255,0.05);
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
}

.toggle-switch label {
    color: white;
    font-weight: 500;
    margin-left: 0.5rem;
}

/* Custom Toggle Icon */
.toggle-icon {
    font-size: 24px;
    transition: transform 0.3s ease;
    display: inline-block;
    width: 24px;
    text-align: center;
}

.toggle-icon.on {
    transform: rotate(360deg);
}

.toggle-icon.off {
    transform: rotate(0deg);
    opacity: 0.5;
}

</style>
"""

def create_header():
    """Create the header with logo, title, and navigation"""
    header_html = """
        <div class="header">
            <img src="https://f2516c96d9c39f54193b4f5177484359.cdn.bubble.io/f1724720784592x708213008252116400/BNT_LOGOs%20%281080%20x%201080%20px%29%20%281%29.png" 
                 class="header-logo">
            <h1 class="header-title">Beat <span style="color: #FF0151;">N</span> Track Finder<span style="color: #FF0151;">.</span></h1>
            <nav class="header-nav">
                <a href="https://beatntrack.world/admin" target="_blank">Admin</a>
                <a href="https://beatntrack.world/venuedata" target="_blank">Venues</a>
                <a href="https://beatntrack.world/servicedata" target="_blank">Services</a>
                <a href="https://beatntrack.world/artistverify" target="_blank">Artists</a>
            </nav>
        </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

def main():
    """Main UI function with improved layout"""
    try:
        # Set page config
        st.set_page_config(
            page_title="Beat N Track Data Finder",
            page_icon="🎵",
            layout="wide"
        )
        
        # Apply custom styles
        st.markdown(CUSTOM_STYLES, unsafe_allow_html=True)

        # Add header before any other content
        create_header()

        # Initialize the state manager
        StateManager.init_state()

        # Wrap main content in container
        st.markdown('<div class="main-content">', unsafe_allow_html=True)

        # Get gig synonyms from StateManager before using them
        gig_synonyms = st.session_state.get("gig_synonyms", StateManager.gig_synonyms)

        # Create main layout with columns
        left_col, main_col = st.columns([1, 3])

        # Left sidebar content
        with left_col:
            # Replace the autopilot toggle section with this:
            st.markdown('<div class="toggle-switch">', unsafe_allow_html=True)
            col1, col2 = st.columns([1, 4])
            with col1:
                autopilot = st.checkbox('', value=True, key='autopilot', label_visibility="collapsed")
            with col2:
                st.markdown(
                    f'<label><span class="toggle-icon {"on" if autopilot else "off"}">{"⚡" if autopilot else "🔌"}</span> '
                    f'Autopilot Mode</label>',
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

            # Create collapsible sections
            with st.expander("📍 Location Settings", expanded=True):
                # Country Selection
                country_options = [ c["name"] for c in COUNTRY_DATA ]
                current_country = StateManager.get_form_data("country", "United Kingdom")
                selected_country = st.selectbox(
                    "Select a Country",
                    options=country_options,
                    index=country_options.index(current_country) if current_country in country_options else 0,
                    key=StateManager.create_widget_key("country"),
                    on_change=StateManager.on_change_handler("country")
                )

                # State and City inputs
                if selected_country == "United States":
                    current_state = StateManager.get_form_data("state", "")
                    selected_state = st.text_input(
                        "State",
                        value=current_state,
                        key=StateManager.create_widget_key("state"),
                        on_change=StateManager.on_change_handler("state")
                    )
                else:
                    selected_state = ""
                    StateManager.update_form_data("state", "")

                current_city = StateManager.get_form_data("city", "")
                selected_city = st.text_input(
                    "City",
                    value=current_city,
                    key=StateManager.create_widget_key("city"),
                    on_change=StateManager.on_change_handler("city")
                )

            with st.expander("🏷️ Type Settings", expanded=True):
                # Type Selection
                type_options = ["Artists", "Venues", "Services", "Other"]
                current_type = StateManager.get_form_data("type", "Services")
                selected_type = st.selectbox(
                    "Type",
                    options=type_options,
                    index=type_options.index(current_type) if current_type in type_options else 2,
                    key=StateManager.create_widget_key("type"),
                    on_change=StateManager.on_change_handler("type")
                )

                # Custom type input if "Other" is selected
                custom_type = ""
                if selected_type == "Other":
                    custom_type = st.text_input(
                        "Custom Type",
                        value=StateManager.get_form_data("custom_type", ""),
                        key=StateManager.create_widget_key("custom_type")
                    )

                # Sub Type Selection
                if selected_type == "Services":
                    sub_type = st.selectbox(
                        "Sub Type",
                        options=SERVICES_SUBTYPES,
                        key=StateManager.create_widget_key("sub_type_services")
                    )
                    if sub_type == "Other":
                        custom_sub_type = st.text_input(
                            "Custom Sub Type",
                            key=StateManager.create_widget_key("custom_sub_type")
                        )
                        final_sub_type = custom_sub_type if custom_sub_type else "Other"
                    else:
                        final_sub_type = sub_type
                elif selected_type == "Venues":
                    sub_type = st.selectbox(
                        "Sub Type",
                        options=VENUES_SUBTYPES,
                        key=StateManager.create_widget_key("sub_type_venues")
                    )
                    if sub_type == "Other":
                        custom_sub_type = st.text_input(
                            "Custom Sub Type",
                            key=StateManager.create_widget_key("custom_sub_type")
                        )
                        final_sub_type = custom_sub_type if custom_sub_type else "Other"
                    else:
                        final_sub_type = sub_type
                else:
                    final_sub_type = st.text_input(
                        "Sub Type",
                        value=StateManager.get_form_data("sub_type", ""),
                        key=StateManager.create_widget_key("sub_type_text")
                    )

                # Update the form data with final values
                StateManager.update_form_data("type", selected_type)
                StateManager.update_form_data("sub_type", final_sub_type)

            # Add download button right after Type Settings expander
            if "df" in st.session_state and isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty:
                buf = StringIO()
                st.session_state.df.to_csv(buf, index=False)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=buf.getvalue(),
                    file_name="beat_n_track_data.csv",
                    mime="text/csv",
                    key="download_csv"
                )

        # Main content area
        with main_col:
            # Feature cards at the top
            st.markdown("""
                <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0;'>
                    <div class='feature-card'>
                        <h4>📄 Upload CSV</h4>
                        <p style='font-size: 0.9em;'>Upload your CSV file with URLs and optional fields</p>
                    </div>
                    <div class='feature-card'>
                        <h4>🔍 Scrape Data</h4>
                        <p style='font-size: 0.9em;'>Automatically extract contact info, images, and more</p>
                    </div>
                    <div class='feature-card'>
                        <h4>🤖 AI Processing</h4>
                        <p style='font-size: 0.9em;'>Smart data extraction using ChatGPT</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # CSV Upload Section
            st.markdown("### Upload Business URLs CSV")
            uploaded_file = st.file_uploader(
                "Upload CSV (with optional address or name columns)", 
                type=["csv"],
                help="Your CSV file should contain at least a URL column"
            )

            # Create a container for the DataFrame display
            df_container = st.empty()
            
            # Store the table container in session state
            if 'table_area' not in st.session_state:
                st.session_state.table_area = st.empty()
            if 'df_container' not in st.session_state:
                st.session_state.df_container = st.empty()
                
            # Move download functionality to after we have data
            download_container = st.empty()
            
            # Only show download button if we have data
            if "df" in st.session_state and isinstance(st.session_state.df, pd.DataFrame):
                buf = StringIO()
                st.session_state.df.to_csv(buf, index=False)
                download_container.download_button(
                    label="Download CSV",
                    data=buf.getvalue(),
                    file_name="beat_n_track_data.csv",
                    mime="text/csv"
                )

            # --- Column Mapping and CSV Processing ---
            if uploaded_file is not None:
                file_text = uploaded_file.read().decode("utf-8", errors="replace")
                df_original = pd.read_csv(StringIO(file_text))
                
                if not st.session_state.get("column_mapping_accepted", False):
                    # Clear any existing mapping when new file is uploaded
                    if "last_file" not in st.session_state or st.session_state["last_file"] != uploaded_file.name:
                        st.session_state["column_mapping"] = None
                        st.session_state["last_file"] = uploaded_file.name
                    
                    # Initialize column mapping if not exists
                    if "column_mapping" not in st.session_state or st.session_state["column_mapping"] is None:
                        st.session_state.column_mapping = StateManager.guess_column_mapping(df_original.columns)
                        if st.session_state.column_mapping:
                            st.success("✅ Automatically detected column mappings!")
                            for k, v in st.session_state.column_mapping.items():
                                st.write(f"- Mapped '{k}' to '{v}'")

                    # Show mapping UI
                    st.subheader("Column Mapping")
                    if st.button("Accept Mapping"):
                        if not st.session_state.column_mapping.get("URL"):
                            st.error("URL field mapping is required")
                        else:
                            st.session_state.column_mapping_accepted = True
                            st.session_state.df_original = df_original
                            st.rerun()  # replaced st.experimental_rerun() with st.rerun()

                    st.write("Please verify or correct the detected mappings:")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("##### Required Fields")
                        url_col = st.session_state.column_mapping.get("URL", "")
                        url_options = [""] + list(df_original.columns)
                        url_index = max(0, url_options.index(url_col) if url_col in url_options else 0)
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
                        for expected_col in EXPECTED_COLUMNS.keys():
                            if expected_col != "URL":
                                current_value = st.session_state.column_mapping.get(expected_col, "")
                                options = [""] + list(df_original.columns)
                                index = max(0, options.index(current_value) if current_value in options else 0)
                                selected = st.selectbox(
                                    f"{expected_col} field",
                                    options=options,
                                    index=index,
                                    key=f"mapping_{expected_col}"
                                )
                                if selected:
                                    st.session_state.column_mapping[expected_col] = selected

                # Process CSV only after mapping is accepted
                if st.session_state.column_mapping_accepted:
                    if not st.session_state.get("processing_csv", False):
                        if st.button("Process CSV"):
                            st.session_state["processing_csv"] = True
                            st.rerun()  # replaced st.experimental_rerun() with st.rerun()
                    else:
                        st.info("Grab a cup of tea ☕ because this might take a while...")
                        # ...existing CSV processing logic...
                        df = pd.DataFrame()
                        for expected_col, source_col in st.session_state.column_mapping.items():
                            if source_col in st.session_state.df_original.columns:
                                df[expected_col] = st.session_state.df_original[source_col]
                        # ...rest of processing logic remains unchanged...
                        # Initialize any missing required columns
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
                        
                        # Set Type / Sub Type for all rows
                        final_type = selected_type if selected_type != "Other" else custom_type.strip()
                        if selected_type == "Other" and not final_type:
                            st.error("You selected 'Other' but did not provide a custom type.")
                            st.stop()
                        
                        # Use final_sub_type that was set in the Type Settings form
                        for i in range(len(df)):
                            df.at[i, "Type"] = final_type
                            df.at[i, "Sub Type"] = final_sub_type  # Changed from sub_type_input to final_sub_type
                            df.at[i, "GigListingURL"] = ""
                        
                        # Apply optional country/city/state to all rows
                        if selected_country.strip():
                            alpha_code = get_country_code(selected_country)
                            print(f"Debug: Selected Country: {selected_country}, Alpha Code: {alpha_code}")
                            for i in range(len(df)):
                                df.at[i, "Country"] = selected_country
                                if not df.at[i, "Country code"]:
                                    df.at[i, "Country code"] = alpha_code
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
                        
                        total = len(df)
                        pbar = st.progress(0)
                        stat_area = st.empty()
                        
                        # Process each row using your process_row function
                        for i, row in df.iterrows():
                            try:
                                process_row(i, row, df, s, final_type, gig_synonyms)
                            except Exception as e:
                                df.at[i, "Error"] = f"Processing error: {e}"
                                st.error(f"Error processing row {i+1}: {e}")
                            time.sleep(1)
                            # Update progress and display table
                            display_df = df.copy()
                            for col in ["AllImages", "EmailContacts", "PhoneContacts"]:
                                if col in display_df.columns:
                                    display_df[col] = display_df[col].apply(StateManager.ensure_string_format)
                            pbar.progress(int(((i + 1) / total) * 100))
                            stat_area.text(f"Processing row {i+1}/{total}...")
                            st.session_state.table_area.dataframe(display_df, use_container_width=True)
                        
                        # Final cleanup
                        df = cleanup_address_lines(df)
                        st.session_state["df"] = df
                        st.success("Processing complete!")
                        # Update DataFrame display
                        st.session_state.df_container.dataframe(df, use_container_width=True)
                        
                        # Remove download buttons section and keep only auto_download
                        auto_download_csv(df, "scraped_")

                        # Autopilot mode actions
                        if autopilot and "df" in st.session_state:
                            # Run GPT enhancement
                            st.info("Autopilot: Enhancing data with GPT...")
                            df = st.session_state["df"].copy()
                            length = len(df)
                            bar = st.progress(0)
                            
                            for i, row in df.iterrows():
                                txt = str(row.get("ScrapedText", "")).strip()  # ensure txt is defined every iteration
                                if not row.get("Description", "").strip() and txt:
                                    desc = generate_gpt_description(txt)
                                    df.at[i, "Description"] = desc

                                city_missing = not row.get("City", "").strip()
                                country_missing = not row.get("Country", "").strip()
                                if (city_missing or country_missing) and txt:
                                    loc_info = extract_city_country_gpt(txt)
                                    if loc_info:
                                        if city_missing and loc_info.get("City", "").strip():
                                            df.at[i, "City"] = loc_info["City"].strip()
                                        if country_missing and loc_info.get("Country", "").strip():
                                            df.at[i, "Country"] = loc_info["Country"].strip()
                                            df.at[i, "Country code"] = fix_country_code(df.loc[i])
                            
                                bar.progress(int(((i + 1) / length) * 100))
                            
                            st.session_state["df"] = df
                            st.success("GPT enhancement complete!")
                            
                            # Update state and save with single display
                            finalize_data(df)  # This will update display and save CSV
                            
                            # Send Data to Bubble
                            
                            # a. Format AllImages column
                            for i, row in df.iterrows():
                                images = row.get("AllImages", "")
                                if isinstance(images, str):
                                    if "||" in images:
                                        df.at[i, "AllImages"] = images.split("||")
                                    elif "," in images:
                                        df.at[i, "AllImages"] = [x.strip() for x in images.split(",")]
                                    else:
                                        df.at[i, "AllImages"] = [images] if images else []
                                if not isinstance(row["AllImages"], list):
                                    df.at[i, "AllImages"] = []
                            
                            records = df.to_dict(orient="records")
                            bubble_url = "https://beatntrack.world/api/1.1/wf/bntdata"
                            init_url = "https://majorlabl.bubbleapps.io/version-test/api/1.1/wf/bntdata/initialize"
                            
                            try:
                                # Send all rows to production endpoint
                                resp = requests.post(bubble_url, json=records, timeout=20)
                                if resp.status_code == 200:
                                    st.success("Data successfully sent to Bubble production endpoint!")
                                else:
                                    st.error(f"Bubble production endpoint returned {resp.status_code}: {resp.text}")
                                
                                # Send sample to initialization endpoint
                                sample = df.head(5).to_dict(orient="records")
                                resp = requests.post(init_url, json=sample, timeout=10)
                                if resp.status_code == 200:
                                    st.success("Bubble initialization success! Check your Bubble workflow to confirm.")
                                else:
                                    st.error(f"Bubble initialization endpoint returned {resp.status_code}: {resp.text}")
                                    
                            except requests.RequestException as e:
                                st.error(f"Error contacting Bubble: {e}")

            # --- GPT Summaries Button ---
            # Only show these buttons if autopilot is OFF
            if not autopilot:
                if st.button("Add Descriptions"):
                    if st.session_state.get("df") is None:
                        st.warning("No data to summarize or fill. Please scrape first.")
                    else:
                        st.info("Generating GPT summaries + filling City/Country from ScrapedText if missing...")
                        df = st.session_state["df"].copy()
                        length = len(df)
                        bar = st.progress(0)
                        
                        for i, row in df.iterrows():
                            txt = str(row.get("ScrapedText", "")).strip()
                            
                            # Add GPT description if missing
                            if not row.get("Description", "").strip() and txt:
                                desc = generate_gpt_description(txt)
                                df.at[i, "Description"] = desc

                            # Add missing city/country data if possible
                            city_missing = not row.get("City", "").strip()
                            country_missing = not row.get("Country", "").strip()
                            if (city_missing or country_missing) and txt:
                                loc_info = extract_city_country_gpt(txt)
                                if loc_info:
                                    if city_missing and loc_info.get("City", "").strip():
                                        df.at[i, "City"] = loc_info["City"].strip()
                                    if country_missing and loc_info.get("Country", "").strip():
                                        df.at[i, "Country"] = loc_info["Country"].strip()
                                        df.at[i, "Country code"] = fix_country_code(df.loc[i])
                            
                            bar.progress(int(((i + 1) / length) * 100))
                        
                        # Update state and display
                        st.session_state["df"] = df
                        st.success("GPT enhancement complete!")
                        finalize_data(df)

        st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"UI Error: {str(e)}")
        st.exception(e)
        
        # Create columns for action buttons
        action_col1, action_col2 = st.columns(2)

        # Move download button right under the DataFrame and make it more visible
        if 'df' in st.session_state and isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty:
            with action_col1:
                buf = StringIO()
                st.session_state.df.to_csv(buf, index=False)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=buf.getvalue(),
                    file_name="beat_n_track_data.csv",
                    mime="text/csv",
                    key="download_csv"  # Add unique key
                )



