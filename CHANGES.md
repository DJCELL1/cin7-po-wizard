# Migration to Google Sheets - Changes Summary

## ✅ What Was Changed

### Files Added:
1. **`gsheets_db.py`** - Google Sheets database module (copied from SDATA)
2. **`db_config.py`** - Configuration for Cin7 product database
3. **`credentials.json`** - Google Cloud service account credentials (copied from SDATA)
4. **`MIGRATION_GUIDE.md`** - Detailed migration instructions
5. **`podata_old.py`** - Backup of original file

### Files Modified:
1. **`podata.py`**:
   - Removed PostgreSQL/psycopg2 imports
   - Removed Railway config and connection code
   - Updated `db_product_by_sku()` to use Google Sheets
   - Updated `db_supplier_map_get()` to use Google Sheets
   - Changed title to "Google Sheets Version"

2. **`requirements.txt`**:
   - Added `gspread>=5.12.0`
   - Added `oauth2client>=4.1.3`

3. **`.gitignore`**:
   - Added credentials file protection
   - Added backup file exclusion

## 🔧 What You Need To Do

### Step 1: Upload Products to Google Sheets

You have two options:

**Option A - Use SDATA Manager (Recommended):**
```bash
cd "../SDATA"
streamlit run database_manager.py
```
- Upload your `Products.csv` using "Upload CSV (Cin7)"
- Choose "Replace all existing data"
- Click "Import Data"

**Option B - Manual:**
- Go to https://sheets.google.com
- Create spreadsheet: "Cin7 Products Database"
- Import `Products.csv`
- Share with: `sdata-service-account@sdata-database.iam.gserviceaccount.com`
- Give "Editor" access

### Step 2: Test Locally

```bash
cd "C:\Users\selwy\OneDrive\Desktop\PROJECTS HDL\cin7-po-wizard"
streamlit run podata.py
```

Test that:
- ✅ App loads without errors
- ✅ SKU lookups work
- ✅ Supplier lookups work
- ✅ You can create a PO

### Step 3: Deploy to Streamlit Cloud

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Migrate from PostgreSQL to Google Sheets"
   git push
   ```

2. **Update Streamlit Secrets:**
   - Remove `[railway]` section
   - Remove `[railway_db]` section
   - Add `[gcp_service_account]` section (see MIGRATION_GUIDE.md)
   - Keep `[cin7]` section unchanged

3. **Share the Google Sheet:**
   - Make sure "Cin7 Products Database" is shared with your service account

## 📊 Benefits

- 💰 **No Database Costs**: Removed Railway PostgreSQL ($5-20/month)
- 👀 **Easy to View**: View/edit products in Google Sheets
- 🔄 **Real-time Sync**: Changes in Sheets reflect immediately
- 🚀 **Simpler**: No database server to manage

## ⚠️ Important Notes

- Google Sheets has a 5 million cell limit
- For very large datasets (>50K rows), consider using Google Sheets API batching
- The `Products.csv` file in this directory is now just a backup/reference

## 🆘 Troubleshooting

### "Failed to connect to product database"
→ Make sure `credentials.json` is in the project directory
→ OR add credentials to Streamlit secrets

### "SKU not found"
→ Make sure you uploaded Products.csv to Google Sheets
→ Check the spreadsheet name is exactly "Cin7 Products Database"
→ Check the worksheet/tab name is "products"

### "No permission" error
→ Share the spreadsheet with your service account email
→ Give it "Editor" access

## 📝 What Columns Are Expected

The Google Sheets database should have at least these columns from your Products.csv:
- `sku` - Product SKU code
- `suppliername` - Supplier name
- `supplierid` - Cin7 supplier/contact ID
- ... (all other columns from your Cin7 export)

## 🔙 Rollback (If Needed)

If you need to rollback:
```bash
cp podata_old.py podata.py
git checkout requirements.txt .gitignore
```

Then redeploy to Streamlit Cloud with Railway secrets.
