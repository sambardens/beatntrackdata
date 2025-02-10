import requests
from bs4 import BeautifulSoup
from address_utils import quick_extract_address

def fetch_prs_contact_address(session) -> str:
    """
    Forcefully fetch the PRS for Music contact page and extract a proper UK address with postcode.
    """
    url = "https://prsformusic.com/help/contact-us"
    resp = session.get(url, timeout=10, verify=False)
    if resp.status_code == 200:
        # Parse the entire text
        soup = BeautifulSoup(resp.text, "html.parser")
        full_text = soup.get_text(separator="\n", strip=True)
        # Attempt extracting a complete address
        possible_address = quick_extract_address(full_text, country="UK")
        if possible_address:
            return possible_address
    return ""
