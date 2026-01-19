# Google Sheets Integration Setup Guide

This guide explains how to integrate your cin7-po-wizard app with Google Sheets.

## Overview

The app now loads product data from Google Sheets instead of (or in addition to) the local Products.csv file. This allows you to:
- Update product data in real-time without redeploying the app
- Share product management with team members
- Keep a centralized, cloud-based product database

## Setup Steps

### 1. Get Your Google Sheet ID

1. Open your Google Sheet (the one that mirrors Products.csv)
2. Look at the URL in your browser. It should look like:
   ```
   https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit
   ```
3. Copy the `SHEET_ID` part (the long string between `/d/` and `/edit`)

### 2. Share the Sheet with the Service Account

The app uses a service account to access Google Sheets. You need to share your sheet with this account:

1. Click the **Share** button in your Google Sheet
2. Add this email address:
   ```
   sdata-service-account@sdata-database.iam.gserviceaccount.com
   ```
3. Give it **Editor** permissions
4. Uncheck "Notify people"
5. Click **Share** or **Done**

### 3. Update the Sheet ID in secrets.toml

1. Open `.streamlit/secrets.toml`
2. Find the line that says:
   ```toml
   google_sheet_id = "..."
   ```
3. Replace the value with your actual Sheet ID from Step 1
4. Save the file

### 4. Verify Your Google Sheet Structure

Your Google Sheet must have these columns (matching Products.csv):
- **Product Name** (optional but recommended)
- **Style Code** (optional)
- **Stock Control** (optional)
- **Code** (required - product code)
- **Supplier Code** (optional)
- **Supplier** (required - supplier name)
- **Contact ID** (required - Cin7 supplier contact ID)

The app will display an error if required columns are missing.

### 5. Test the Integration

Run the app:
```bash
cd "C:\Users\selwy\OneDrive\Desktop\PROJECTS HDL\cin7-po-wizard"
streamlit run app.py
```

Look for the message in the sidebar:
- ✅ **"Using Google Sheets for product data"** = Success!
- ⚠️ **"Google Sheets not available, using CSV"** = Fallback to CSV (check the error message)

## How It Works

### Automatic Fallback
The app tries to load from Google Sheets first. If that fails, it automatically falls back to the local Products.csv file.

### Caching
Product data is cached for 5 minutes to improve performance. Changes to your Google Sheet will appear in the app within 5 minutes.

To force a refresh, click the menu (☰) in Streamlit and select "Clear cache".

### Data Flow
```
Google Sheets → Service Account → gspread library → pandas DataFrame → app.py
```

## Troubleshooting

### Error: "Google Sheet missing required column"
- Make sure your sheet has columns: `Code`, `Supplier`, and `Contact ID`
- Column names are case-sensitive
- Check for extra spaces in column names

### Error: "Spreadsheet not found"
- Verify you shared the sheet with the service account email
- Check that the Sheet ID in secrets.toml is correct
- Make sure the sheet is not deleted

### Error: "Permission denied"
- The service account needs "Editor" access (not just "Viewer")
- Re-share the sheet and ensure you selected "Editor"

### App is using CSV instead of Google Sheets
- Check the sidebar message for the specific error
- Common issues:
  - Wrong Sheet ID
  - Sheet not shared with service account
  - Missing or incorrect credentials in secrets.toml

## Files Modified

1. **google_sheets_products.py** - New module for Google Sheets integration
2. **app.py** - Updated to use Google Sheets with CSV fallback
3. **.streamlit/secrets.toml** - Added Google credentials and sheet ID

## Security Notes

- The `credentials.json` file contains sensitive credentials - never commit it to public repositories
- The `.streamlit/secrets.toml` file is already in `.gitignore`
- The service account only has access to sheets you explicitly share with it

## Next Steps

Once you confirm the Sheet ID and complete the setup:
1. Test the app locally
2. Update products in Google Sheets
3. Verify changes appear in the app (within 5 minutes)
4. Deploy to Streamlit Cloud if needed (add secrets to cloud environment)
