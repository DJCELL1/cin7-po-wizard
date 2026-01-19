# Migration Guide: PostgreSQL (Railway) → Google Sheets

This guide will help you migrate your Cin7 PO Wizard from PostgreSQL to Google Sheets.

## Why Migrate?

- ✅ **No Database Costs**: Google Sheets is free
- ✅ **Easy to View**: View/edit products directly in Google Sheets
- ✅ **Simple Setup**: No database server to manage
- ✅ **Same Credentials**: Uses the same Google credentials as SDATA database

## Step 1: Upload Products to Google Sheets

### Option A: Use SDATA Database Manager

1. Copy your Google credentials to this project:
   ```bash
   cp "../SDATA/credentials.json" "./"
   ```

2. Run the SDATA Database Manager:
   ```bash
   cd "../SDATA"
   streamlit run database_manager.py
   ```

3. Upload your `Products.csv`:
   - Click "Upload CSV (Cin7)"
   - Select `Products.csv`
   - Choose "Replace all existing data"
   - Click "Import Data"

4. The products are now in Google Sheets!

### Option B: Manual Upload

1. Go to https://sheets.google.com
2. Create a new spreadsheet named "Cin7 Products Database"
3. Import your `Products.csv` file
4. Share with your service account: `sdata-service-account@sdata-database.iam.gserviceaccount.com`
5. Give it "Editor" access

## Step 2: Update Code

The following files have been created/updated:

- ✅ `gsheets_db.py` - Google Sheets database module (copied from SDATA)
- ✅ `db_config.py` - Configuration for product database
- ✅ `requirements.txt` - Added gspread and oauth2client
- 🔄 `podata.py` - Needs updates (see below)

## Step 3: Code Changes Needed in podata.py

Replace the database sections with Google Sheets lookups:

### Remove (lines 1-64):
```python
import psycopg2
# All Railway config
# All PostgreSQL database config and helpers
```

### Add at top:
```python
from db_config import get_product_database
```

### Replace `db_product_by_sku` function:
```python
@st.cache_data(ttl=3600)
def db_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Query products from Google Sheets."""
    sku = (sku or "").strip()
    if not sku:
        return None

    db = get_product_database()
    if not db:
        return None

    # Search for SKU in the database
    results = db.search("sku", sku)

    if len(results) == 0:
        return None

    # Return first match as dictionary
    return results.iloc[0].to_dict()
```

### Replace `db_supplier_by_name` function:
```python
@st.cache_data(ttl=3600)
def db_supplier_by_name(supplier_name: str) -> Optional[int]:
    """Look up supplier ID from Google Sheets."""
    supplier_name = (supplier_name or "").strip()
    if not supplier_name:
        return None

    db = get_product_database()
    if not db:
        return None

    # Search for supplier
    results = db.search("suppliername", supplier_name)

    if len(results) == 0:
        return None

    # Return supplier ID
    row = results.iloc[0]
    return int(row.get("supplierid", 0))
```

## Step 4: Deploy to Streamlit Cloud

1. Push changes to GitHub
2. In Streamlit Cloud, add your Google credentials to secrets:

```toml
[gcp_service_account]
type = "service_account"
project_id = "sdata-database"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "sdata-service-account@sdata-database.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

3. Keep your existing `[cin7]` secrets
4. Remove `[railway]` and `[railway_db]` secrets (no longer needed)

## Step 5: Test

1. Run locally: `streamlit run podata.py`
2. Test SKU lookups work
3. Test supplier lookups work
4. Create a test PO

## Benefits

- 💰 **Free**: No database costs
- 📊 **Visual**: Edit products in Google Sheets
- 🔄 **Sync**: Changes in Sheets reflect immediately
- 🚀 **Simple**: No database management

## Need Help?

See `../SDATA/GOOGLE_SHEETS_SETUP.md` for detailed Google Sheets setup instructions.
