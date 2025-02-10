# config.py
import os
from dotenv import load_dotenv
import openai

load_dotenv()

AZURE_MAPS_KEY = os.getenv("AZURE_MAPS_KEY")
BING_KEY = os.getenv("BING_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_KEY  # Make sure the OpenAI key is set
