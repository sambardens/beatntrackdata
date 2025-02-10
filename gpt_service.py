import openai
import json

class GPTService:
    def __init__(self, api_key):
        openai.api_key = api_key

    def generate_gpt_description(self, text):
        prompt = (
            "You are generating descriptions for a music map website. "
            "Summarize the following content in around 100 words, focusing on the most interesting "
            "and relevant details about this venue, artist, or music-related service. "
            "Do NOT include addresses, as those will be shown separately. "
            "Highlight key features such as music styles, history, unique offerings, events, or reputation. "
            "Keep it engaging, clear, and informative:\n\n"
            + text
            + "\n\nMusic Map Description:"
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.0,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"(OpenAI Error: {e})"

    def extract_address_fields_gpt(self, text):
        prompt = """Extract the full postal address from the text below. The text may contain multiple sections separated by '====='.
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

        Now, analyze this text and extract the address:

        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt + text}
                ],
                max_tokens=500,
                temperature=0.0,
            )
            raw_json = response.choices[0].message.content.strip()
            return json.loads(raw_json) if raw_json else {}
        except Exception as e:
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