import streamlit as st
import pandas as pd

class StateManager:
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

    # Class attributes
    gig_synonyms = [
        "whatson", "what-s-on", "events", "event-listings", "eventcalendar", "event-calendar",
        "events-upcoming", "event-schedule", "gigs", "gig-listings", "gig-schedule", "gig-guide",
        "lineup", "concerts", "concert-guide", "live-events", "live-shows", "live-music",
        "live-music-calendar", "music-calendar", "music-events", "music-schedule", "venue-calendar",
        "venue-events", "whats-happening", "happening-now", "coming-soon", "special-events",
        "on-stage", "agenda", "diary", "live-diary", "all-events", "all-gigs", "full-schedule",
        "full-lineup", "show-guide", "shows", "shows-list", "upcoming", "upcoming-events",
        "upcoming-gigs", "upcoming-shows", "dates", "dates-and-tickets", "tour-dates", "tickets",
        "ticket-info", "performances", "performance-schedule", "schedule-of-events", "program",
        "programme", "artist-schedule", "music-events", "music-schedule", "venue-events",
        "calendar", "schedule"
    ]

    @staticmethod
    def init_state():
        """Initialize all required session state variables"""
        if "initialized" not in st.session_state:
            defaults = {
                "initialized": True,
                "form_data": {
                    "country": "United Kingdom",  # default changed
                    "state": "",
                    "city": "",
                    "type": "Services",
                    "custom_type": "",
                    "sub_type": "",
                },
                "column_mapping_accepted": False,
                "column_mapping": {},
                "df_original": None,
                "df": None,
                "processing_complete": False,
                "gig_synonyms": StateManager.gig_synonyms  # Add gig synonyms to state
            }
            
            for key, value in defaults.items():
                if key not in st.session_state:
                    st.session_state[key] = value

    @staticmethod
    def handle_column_mapping(df_original):
        """Handle column mapping state and UI"""
        if "column_mapping" not in st.session_state:
            st.session_state.column_mapping = StateManager.guess_column_mapping(df_original.columns)
            
        # Create UI for unmapped columns
        st.subheader("Column Mapping")
        st.write("Please verify or correct the column mappings below:")
        
        # Create two columns layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("##### Required Fields")
            # URL field (required)
            url_col = st.session_state.column_mapping.get("URL", "")
            url_options = [""] + list(df_original.columns)
            url_index = url_options.index(url_col) if url_col in url_options else 0
            url_selected = st.selectbox("URL field", options=url_options, index=url_index, key="url_mapping")
            if url_selected:
                st.session_state.column_mapping["URL"] = url_selected
        
        with col2:
            st.write("##### Optional Fields")
            optional_fields = [
                "Name", "Type", "Sub Type", "Description", "ScrapedText",
                "Address line 1", "Address line 2", "City", "County", "Country",
                "Post code", "Country code", "State"
            ]
            for field in sorted(optional_fields):
                current_value = st.session_state.column_mapping.get(field, "")
                options = [""] + list(df_original.columns)
                index = options.index(current_value) if current_value in options else 0
                selected = st.selectbox(
                    f"{field} field", 
                    options=options,
                    index=index,
                    key=f"mapping_{field}"
                )
                if selected:
                    st.session_state.column_mapping[field] = selected

        if st.button("Accept Mapping"):
            if not st.session_state.column_mapping.get("URL"):
                st.error("URL field mapping is required")
                return False
            else:
                st.session_state.column_mapping_accepted = True
                st.session_state.df_original = df_original
                return True
                
        return False

    @staticmethod
    def guess_column_mapping(df_columns):
        """Smarter column mapping with debug output"""
        mapping = {}
        df_columns_lower = {col.lower().strip(): col for col in df_columns}
        print(f"Available columns: {df_columns}")

        # First pass: Look for exact matches
        for expected_col, alternatives in StateManager.EXPECTED_COLUMNS.items():
            # Try exact match first
            if expected_col.lower() in df_columns_lower:
                mapping[expected_col] = df_columns_lower[expected_col.lower()]
                print(f"Exact match found for {expected_col}: {mapping[expected_col]}")
                continue
            
            # Try alternatives
            for alt in alternatives:
                if alt.lower() in df_columns_lower:
                    mapping[expected_col] = df_columns_lower[alt.lower()]
                    print(f"Alternative match found for {expected_col}: {mapping[expected_col]}")
                    break

        # Second pass: Try partial/fuzzy matches for unmapped fields
        for expected_col, alternatives in StateManager.EXPECTED_COLUMNS.items():
            if expected_col not in mapping:
                for col in df_columns:
                    col_lower = col.lower()
                    # Check if the column contains any of our expected terms
                    if any(term in col_lower for term in [expected_col.lower()] + [alt.lower() for alt in alternatives]):
                        mapping[expected_col] = col
                        print(f"Fuzzy match found for {expected_col}: {col}")
                        break

        # Special handling for URL column
        if "URL" not in mapping and len(df_columns) == 1:
            mapping["URL"] = df_columns[0]
            print(f"Single column, assuming it's URL: {df_columns[0]}")

        print(f"Final mapping: {mapping}")
        return mapping

    @staticmethod
    def ensure_string_format(value):
        """Improved string conversion for arrays"""
        if isinstance(value, list):
            if all(isinstance(x, str) for x in value):
                return "||".join(value)
            return ", ".join(map(str, value))
        return str(value) if pd.notnull(value) else ""

    @staticmethod
    def get_form_data(field, default=None):
        """Safely get form data"""
        try:
            return st.session_state.form_data.get(field, default)
        except:
            st.session_state.form_data = {}
            return default

    @staticmethod
    def update_form_data(field, value):
        """Safely update form data"""
        if "form_data" not in st.session_state:
            st.session_state.form_data = {}
        st.session_state.form_data[field] = value

    @staticmethod
    def create_widget_key(base_name, suffix=""):
        """Create a unique, stable key for widgets"""
        return f"widget_{base_name}_{suffix}"

    @staticmethod
    def get_widget_value(widget_id):
        """Get a widget's current value from session state"""
        return st.session_state.get(widget_id)

    @staticmethod
    def on_change_handler(field):
        """Create a callback function for widget changes"""
        def callback():
            widget_id = StateManager.create_widget_key(field)
            value = st.session_state[widget_id]
            StateManager.update_form_data(field, value)
        return callback

    @staticmethod
    def update_descriptions(df):
        """Update DataFrame with new descriptions and refresh state"""
        if df is not None:
            # Ensure Description column exists
            if 'Description' not in df.columns:
                df['Description'] = ''
            
            # Update session state
            st.session_state.df = df
            st.session_state.processing_complete = True
            
            # Save to CSV
            df.to_csv('updated_venues.csv', index=False)
            print("DataFrame updated with new descriptions")
            
            # Force cache clear for the dataframe
            st.cache_data.clear()
            
    @staticmethod
    def refresh_data():
        """Refresh the DataFrame from CSV"""
        try:
            df = pd.read_csv('updated_venues.csv')
            st.session_state.df = df
            return True
        except Exception as e:
            print(f"Error refreshing data: {e}")
            return False
