"""
Database Configuration for Cin7 PO Wizard
Uses Google Sheets as the backend for storing Cin7 product data
"""

import streamlit as st
from gsheets_db import GoogleSheetsDatabase

# Google Sheets settings for product database
PRODUCT_SPREADSHEET_NAME = "Cin7 Products Database"
PRODUCT_WORKSHEET_NAME = "products"


def get_product_database():
    """
    Get the product database instance (Google Sheets).

    Returns:
        GoogleSheetsDatabase instance connected to the products sheet
    """
    try:
        db = GoogleSheetsDatabase(
            spreadsheet_name=PRODUCT_SPREADSHEET_NAME,
            worksheet_name=PRODUCT_WORKSHEET_NAME
        )
        return db
    except Exception as e:
        st.error(f"Failed to connect to product database: {str(e)}")
        st.info("Make sure you've:")
        st.code("1. Created Google Cloud credentials\n"
                "2. Added them to Streamlit secrets or created credentials.json\n"
                "3. Shared the spreadsheet with your service account")
        return None
