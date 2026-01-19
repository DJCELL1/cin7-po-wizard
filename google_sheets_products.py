"""
Google Sheets Product Data Integration
Fetches product data from Google Sheets and provides lookup functions
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

# Google Sheets configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# You can update this Sheet ID in your Streamlit secrets or here
# Get it from the URL: https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit
DEFAULT_SHEET_ID = "1cKoXDL4BjoiyU__jM67jwZaBodYB6bkbwPETwmuLQVU"


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_products_from_sheets(sheet_id=None):
    """
    Load product data from Google Sheets
    Returns a pandas DataFrame with columns matching Products.csv:
    - Product Name, Style Code, Stock Control, Code, Supplier Code, Supplier, Contact ID
    """
    try:
        # Use provided sheet_id or get from secrets or use default
        if sheet_id is None:
            sheet_id = st.secrets.get("google_sheet_id", DEFAULT_SHEET_ID)

        # Try to use service account credentials if available
        if "google" in st.secrets:
            # Convert Streamlit secrets to dict for Google API
            google_creds = dict(st.secrets["google"])
            creds = Credentials.from_service_account_info(
                google_creds,
                scopes=SCOPES
            )
            client = gspread.authorize(creds)

            # Open the spreadsheet by ID
            sheet = client.open_by_key(sheet_id)
            worksheet = sheet.get_worksheet(0)  # First worksheet

            # Get all values from the worksheet
            # Using get_all_values() to handle duplicate column names
            all_values = worksheet.get_all_values()

            if len(all_values) < 2:
                raise ValueError("Sheet appears to be empty or has no data rows")

            # First row is headers, rest is data
            headers = all_values[0]
            data_rows = all_values[1:]

            # Create DataFrame
            df = pd.DataFrame(data_rows, columns=headers)
        else:
            # Fallback: Try to read the published sheet directly
            # Note: This works only if the sheet is published to web
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            df = pd.read_csv(csv_url)

        # Clean up column names
        df.columns = [c.strip() for c in df.columns]

        # Ensure required columns exist (matching Products.csv structure)
        required_cols = ["Code", "Supplier", "Contact ID"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"❌ Google Sheet missing required column: {col}")
                st.error(f"Found columns: {list(df.columns)}")
                st.stop()

        # Clean up the data
        df["Code"] = df["Code"].astype(str).str.upper().str.strip()
        df["Supplier"] = df["Supplier"].astype(str).str.strip()

        # Handle optional columns
        if "Supplier Code" in df.columns:
            df["Supplier Code"] = df["Supplier Code"].astype(str).str.strip()

        if "Product Name" in df.columns:
            df["Product Name"] = df["Product Name"].astype(str).str.strip()

        # Remove empty rows (where Code is empty or NaN)
        df = df[df["Code"].notna()]
        df = df[df["Code"].str.len() > 0]

        return df

    except Exception as e:
        st.error(f"❌ Error loading data from Google Sheets: {str(e)}")
        st.error(f"Make sure the sheet is shared with your service account or published to web.")
        raise


def get_product_by_code(df, code):
    """
    Look up a product by its Code
    Returns a dictionary with product details or None if not found
    """
    code = str(code).upper().strip()
    result = df[df["Code"] == code]

    if result.empty:
        return None

    return result.iloc[0].to_dict()


def get_products_by_supplier_code(df, supplier_code):
    """
    Look up products by Supplier Code
    Returns a list of matching products
    """
    supplier_code = str(supplier_code).strip()
    results = df[df["Supplier Code"] == supplier_code]

    if results.empty:
        return []

    return results.to_dict('records')


def search_products(df, search_term):
    """
    Search for products by Code, Supplier Code, or Product Name
    Returns a DataFrame of matching products
    """
    search_term = str(search_term).upper().strip()

    mask = (
        df["Code"].str.contains(search_term, case=False, na=False) |
        df["Supplier Code"].str.contains(search_term, case=False, na=False) |
        df["Product Name"].str.contains(search_term, case=False, na=False)
    )

    return df[mask]


def get_all_products(df):
    """
    Get all products from the sheet
    Returns a pandas DataFrame
    """
    return df.copy()
