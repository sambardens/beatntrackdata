import streamlit as st
import pandas as pd
import logging

def finalize_data(df):
    """
    Finalizes the data by updating the session state and saving the DataFrame to a CSV file.
    """
    try:
        # Ensure the Description column exists
        if 'Description' not in df.columns:
            df['Description'] = ''

        # Clear any existing display containers
        if 'table_area' in st.session_state:
            st.session_state.table_area.empty()
        if 'df_container' in st.session_state:
            st.session_state.df_container.empty()

        # Create/update display container
        if 'display_container' not in st.session_state:
            st.session_state.display_container = st.empty()

        # Update session state with the new DataFrame
        st.session_state.df = df
        st.session_state.processing_complete = True

        # Save to CSV
        df.to_csv('final_data.csv', index=False)
        logging.info("Final CSV saved successfully")

        # Update the display using the persistent container
        st.session_state.display_container.dataframe(df, use_container_width=True)

        return True
    except Exception as e:
        logging.error(f"Error saving DataFrame: {e}", exc_info=True)
        return False
