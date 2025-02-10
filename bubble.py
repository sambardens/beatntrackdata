import streamlit as st
import requests
import pandas as pd
from requests.exceptions import RequestException
from urllib.parse import urljoin

def bubble_initialize_button():
    """
    Send sample JSON to Bubble's 'initialize' endpoint.
    We'll send up to 5 rows from st.session_state['df'] as sample data.
    """
    if st.session_state.get("df") is None:
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
    except RequestException as e:
        st.error(f"Error contacting Bubble initialize endpoint: {e}")

def bubble_send_final_button():
    """Enhanced Bubble integration that properly handles arrays"""
    if st.session_state.get("df") is None:
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
    except RequestException as e:
        st.error(f"Error contacting Bubble production endpoint: {e}")

# Example usage (for testing purposes):
if __name__ == "__main__":
    # Load a sample DataFrame (adjust the file path as needed)
    df = pd.read_csv("sample_data.csv")
    
    # Call the initialization function
    bubble_initialize_button()
    
    # Call the final send function
    bubble_send_final_button(df)
