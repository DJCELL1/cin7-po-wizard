"""
Test script to verify Google Sheets integration
Run this to check if the Google Sheets connection is working
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import sys

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Load credentials
with open('credentials.json', 'r', encoding='utf-8') as f:
    creds_dict = json.load(f)

# Setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Get the Sheet ID - UPDATE THIS with your actual Sheet ID
SHEET_ID = "1cKoXDL4BjoiyU__jM67jwZaBodYB6bkbwPETwmuLQVU"

print("=" * 60)
print("Google Sheets Connection Test")
print("=" * 60)
print()

try:
    print("1. Loading credentials...")
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    print("   [OK] Credentials loaded successfully")
    print()

    print("2. Connecting to Google Sheets...")
    client = gspread.authorize(creds)
    print("   [OK] Connected to Google Sheets")
    print()

    print(f"3. Opening spreadsheet with ID: {SHEET_ID}")
    sheet = client.open_by_key(SHEET_ID)
    print(f"   [OK] Opened spreadsheet: {sheet.title}")
    print()

    print("4. Getting worksheet data...")
    worksheet = sheet.get_worksheet(0)
    print(f"   [OK] Worksheet name: {worksheet.title}")
    print()

    print("5. Reading data...")
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        raise ValueError("Sheet appears to be empty")
    headers = all_values[0]
    data_rows = all_values[1:]
    df = pd.DataFrame(data_rows, columns=headers)
    print(f"   [OK] Read {len(df)} rows")
    print()

    print("6. Checking columns...")
    print(f"   Columns found: {list(df.columns)}")
    print()

    required_cols = ["Code", "Supplier", "Contact ID"]
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        print(f"   [ERROR] Missing required columns: {missing}")
    else:
        print(f"   [OK] All required columns present!")
    print()

    print("7. Sample data (first 5 rows):")
    print(df.head())
    print()

    print("=" * 60)
    print("SUCCESS! Google Sheets integration is working!")
    print("=" * 60)

except Exception as e:
    print()
    print("=" * 60)
    print("ERROR!")
    print("=" * 60)
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print()
    print("Troubleshooting tips:")
    print("1. Check that SHEET_ID is correct (from the Google Sheets URL)")
    print("2. Make sure the sheet is shared with:")
    print("   sdata-service-account@sdata-database.iam.gserviceaccount.com")
    print("3. Verify the service account has 'Editor' permissions")
    print("4. Ensure the sheet has the required columns: Code, Supplier, Contact ID")
