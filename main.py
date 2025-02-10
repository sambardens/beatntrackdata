import streamlit as st
from state_manager import StateManager
from dotenv import load_dotenv
import openai
import os

# Load environment variables first
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize state before importing UI
StateManager.init_state()

# Import UI after state is initialized
from ui import main

# Run the app
if __name__ == "__main__":
    main()
