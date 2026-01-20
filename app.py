import streamlit as st
import pandas as pd
import requests
import json
from requests.auth import HTTPBasicAuth
from hd_theme import apply_hd_theme, metric_card, add_logo

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="HDL PO Wizard v3", layout="wide")
apply_hd_theme()
add_logo(logo_path="Logos-01.jpg", subtitle="Purchase Order Wizard")
st.title("📦 HDL Purchase Order Builder — Multi-Supplier Edition (CSV Version)")

# ---------------------------------------------------------
# CIN7 CONFIG
# ---------------------------------------------------------
cin7 = st.secrets["cin7"]
base_url = cin7["base_url"].rstrip("/")
api_username = cin7["api_username"]
api_key = cin7["api_key"]
auth = HTTPBasicAuth(api_username, api_key)

branch_Hamilton = cin7.get("branch_Hamilton", 230)
branch_Avondale = cin7.get("branch_Avondale", 3)

# ---------------------------------------------------------
# CIN7 GET WRAPPER
# ---------------------------------------------------------
def cin7_get(endpoint, params=None):
    url = f"{base_url}/{endpoint}"
    r = requests.get(url, params=params, auth=auth)
    return r.json() if r.status_code == 200 else None

# ---------------------------------------------------------
# LOAD PRODUCTS FROM GOOGLE SHEETS OR CSV
# ---------------------------------------------------------
@st.cache_data
def load_products():
    """
    Load products from Google Sheets first, fall back to CSV if not available
    """
    try:
        # Try to load from Google Sheets
        from google_sheets_products import load_products_from_sheets
        df = load_products_from_sheets()
        st.sidebar.success("✅ Using Google Sheets for product data")
        return df
    except Exception as e:
        # Fall back to CSV if Google Sheets fails
        st.sidebar.warning(f"⚠️ Google Sheets not available, using CSV: {str(e)}")
        try:
            df = pd.read_csv("Products.csv")
            df.columns = [c.strip() for c in df.columns]

            required = {"Code", "Supplier", "Contact ID"}
            if not required.issubset(df.columns):
                st.error("❌ Products.csv missing required columns: Code, Supplier, Contact ID")
                st.stop()

            df["Code"] = df["Code"].astype(str).str.upper().str.strip()
            df["Supplier"] = df["Supplier"].astype(str).str.strip()

            return df
        except Exception as csv_error:
            st.error(f"❌ Could not load products from Google Sheets or CSV: {str(csv_error)}")
            st.stop()

products_df = load_products()

# ---------------------------------------------------------
# BOM LOOKUP
# ---------------------------------------------------------
def get_bom(code):
    search = cin7_get("v1/BomMasters", params={"where": f"code='{code}'"})
    if not search:
        return []
    bom_id = search[0]["id"]

    bom_data = cin7_get(f"v2/BomMasters/{bom_id}")
    if not bom_data:
        return []

    out = []
    for c in bom_data.get("products", []):
        out.append({
            "code": c.get("code"),
            "qty": c.get("quantity", 1),
            "unitCost": c.get("unitCost", 0)
        })
    return out

# ---------------------------------------------------------
# SMART ORDER SEARCH
# ---------------------------------------------------------
def smart_find_order(qref):
    q = qref.strip().upper()
    tests = [
        f"reference='{q}'",
        f"customerOrderNo='{q}'",
        f"reference like '%{q}%'",
        f"customerOrderNo like '%{q}%'"
    ]
    for t in tests:
        res = cin7_get("v1/SalesOrders", params={"where": t})
        if res:
            return res[0]
    return None

# ---------------------------------------------------------
# BUILD MULTI-SUPPLIER PAYLOADS
# ---------------------------------------------------------
def build_po_payloads(qref, df):
    po_groups = []

    for supplier_name, grp in df.groupby("Supplier"):
        supplier_id = int(grp["Contact ID"].iloc[0])
        po_ref = f"PO-{qref}{supplier_name[:4].upper()}"

        line_items = []
        for _, r in grp.iterrows():
            code = r["Item Code"]
            qty = float(r["Qty"])
            cost = float(r["Cost"])

            bom = get_bom(code)
            if bom:
                for c in bom:
                    line_items.append({
                        "code": c["code"],
                        "qty": c["qty"] * qty,
                        "unitPrice": c["unitCost"]
                    })
            else:
                line_items.append({
                    "code": code,
                    "qty": qty,
                    "unitPrice": cost
                })

        payload = {
            "reference": po_ref,
            "supplierId": supplier_id,
            "memberId": supplier_id,
            "branchId": 3,
            "staffId": 1,
            "enteredById": 1,
            "isApproved": True,
            "lineItems": line_items
        }

        po_groups.append((supplier_name, po_ref, payload))

    return po_groups

# ---------------------------------------------------------
# PUSH PO
# ---------------------------------------------------------
def push_po(payload):
    url = f"{base_url}/v1/PurchaseOrders"
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, headers=headers, data=json.dumps([payload]), auth=auth)
    return r.status_code, r.text

# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------
if "lines" not in st.session_state:
    st.session_state.lines = None

# ---------------------------------------------------------
# UI STEP 1 — Load Q Ref
# ---------------------------------------------------------
st.header("Step 1 — Enter Q Ref")

qref = st.text_input("Enter Q-number (e.g. Q19663E.S26):")

if st.button("Load Order"):
    so = smart_find_order(qref)
    if not so:
        st.error("❌ No matching Sales Order found.")
        st.stop()

    st.success("Sales Order Loaded Successfully")
    st.write("**Customer:**", so.get("company", ""))
    st.write("**Project:**", so.get("projectName", ""))
    st.write("**Order Ref:**", qref)

    rows = []
    for li in so.get("lineItems", []):
        if li.get("productId", 0) == 0:
            continue

        code = li.get("code", "").upper()
        prod_match = products_df[products_df["Code"] == code]

        if prod_match.empty:
            continue

        # Get Supplier Code if available
        supplier_code = ""
        if "Supplier Code" in prod_match.columns:
            supplier_code = prod_match["Supplier Code"].iloc[0]

        rows.append({
            "Select": False,
            "Supplier": prod_match["Supplier"].iloc[0],
            "Contact ID": prod_match["Contact ID"].iloc[0],
            "Supplier Code": supplier_code,
            "Item Code": code,
            "Item Name": li.get("name", ""),
            "Qty": li.get("qty", 0),
            "Cost": li.get("unitCost", 0)
        })

    st.session_state.lines = pd.DataFrame(rows)

# ---------------------------------------------------------
# UI STEP 2 — Select Items
# ---------------------------------------------------------
if st.session_state.lines is not None:
    st.header("Step 2 — Select Items")

    edited = st.data_editor(
        st.session_state.lines,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn()
        }
    )
    st.session_state.lines = edited

# ---------------------------------------------------------
# UI STEP 3 — Create POs
# ---------------------------------------------------------
if st.session_state.lines is not None:
    st.header("Step 3 — Create Purchase Orders")

    if st.button("Create POs"):
        selected = st.session_state.lines[st.session_state.lines["Select"] == True]

        if selected.empty:
            st.error("❌ No items selected.")
            st.stop()

        for supplier, items in selected.groupby("Supplier"):
            df_grp = pd.DataFrame(items)
            po_ref = f"PO-{qref}{supplier[:4].upper()}"

            st.write(f"📦 **Creating PO:** {po_ref}")

            payloads = build_po_payloads(qref, df_grp)
            for sup, ref, payload in payloads:
                status, resp = push_po(payload)
                if status == 200:
                    st.success(f"{ref} ✔️ Created")
                else:
                    st.error(f"{ref} ❌ Failed — {resp}")
