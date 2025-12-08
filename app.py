import streamlit as st
import pandas as pd
import requests
import json
import re
from difflib import SequenceMatcher
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="HDL Purchase Order Builder v3", layout="wide")
st.title("📦 HDL Purchase Order Builder — Multi-Supplier Auto-Split Edition")

# ---------------------------------------------------------
# CIN7 CONFIG
# ---------------------------------------------------------
cin7 = st.secrets["cin7"]
base_url = cin7["base_url"].rstrip("/")
api_username = cin7["api_username"]
api_key = cin7["api_key"]

branch_Hamilton = cin7.get("branch_Hamilton", 230)
branch_Avondale = cin7.get("branch_Avondale", 3)

auth = HTTPBasicAuth(api_username, api_key)

# ---------------------------------------------------------
# BASIC GET WRAPPER
# ---------------------------------------------------------
def cin7_get(endpoint, params=None):
    url = f"{base_url}/{endpoint}"
    r = requests.get(url, params=params, auth=auth)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except:
        return None

# ---------------------------------------------------------
# LOAD PRODUCTS.CSV (USED FOR SUPPLIER + CONTACT ID)
# ---------------------------------------------------------
@st.cache_data
def load_products():
    df = pd.read_csv("Products.csv", dtype=str)
    df["Code"] = df["Code"].str.upper().str.strip()
    df["Supplier"] = df["Supplier"].fillna("").astype(str)
    df["Contact ID"] = df["Contact ID"].fillna("0").astype(int)
    return df

products_df = load_products()

# ---------------------------------------------------------
# SMART FIND ORDER (Q-ref search)
# ---------------------------------------------------------
def smart_find_order(qref):
    q = qref.strip().upper()

    # exact match
    res = cin7_get("v1/SalesOrders", params={"where": f"reference='{q}'"})
    if res:
        return res[0]

    res = cin7_get("v1/SalesOrders", params={"where": f"customerOrderNo='{q}'"})
    if res:
        return res[0]

    # partial match
    res = cin7_get("v1/SalesOrders", params={"where": f"reference like '%{q}%'"})
    if res:
        return res[0]

    res = cin7_get("v1/SalesOrders", params={"where": f"customerOrderNo like '%{q}%'"})
    if res:
        return res[0]

    return None

# ---------------------------------------------------------
# BOM SUPPORT
# ---------------------------------------------------------
def get_bom(code):
    search = cin7_get("v1/BomMasters", params={"where": f"code='{code}'"})
    if not search:
        return []

    bom_id = search[0]["id"]
    bom_data = cin7_get(f"v2/BomMasters/{bom_id}")
    if not bom_data:
        return []

    comps = bom_data.get("products", [])
    out = []
    for c in comps:
        out.append({
            "code": c.get("code"),
            "qty": c.get("quantity", 1),
            "unitCost": c.get("unitCost", 0)
        })
    return out

# ---------------------------------------------------------
# BUILD PO PAYLOAD
# ---------------------------------------------------------
def build_single_po_payload(qref, supplier_id, supplier_name, branch_id, df):
    line_items = []

    for _, r in df.iterrows():
        parent = r["Item Code"]
        qty = float(r["Qty"])
        cost = float(r["Cost"])

        bom = get_bom(parent)
        if bom:
            for b in bom:
                line_items.append({
                    "code": b["code"],
                    "qty": b["qty"] * qty,
                    "unitPrice": b["unitCost"]
                })
        else:
            line_items.append({
                "code": parent,
                "qty": qty,
                "unitPrice": cost
            })

    # PO Reference format you wanted:
    # "PO-" + QREF + first 4 letters of supplier (uppercase)
    abbr = supplier_name[:4].upper()

    return [{
        "reference": f"PO-{qref}{abbr}",
        "supplierId": supplier_id,
        "memberId": supplier_id,
        "branchId": branch_id,
        "isApproved": True,
        "staffId": 1,
        "enteredById": 1,
        "lineItems": line_items
    }]

# ---------------------------------------------------------
# PUSH PO TO CIN7
# ---------------------------------------------------------
def push_po(payload):
    url = f"{base_url}/v1/PurchaseOrders"
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, data=json.dumps(payload), headers=headers, auth=auth)
    return r.status_code, r.text

# =========================================================
# UI START
# =========================================================
st.header("Step 1 — Enter Q-Ref")
qref = st.text_input("Enter Q-number (e.g. Q19663E.S26):")

# Initialise session state
if "item_table" not in st.session_state:
    st.session_state.item_table = pd.DataFrame()

if "loaded" not in st.session_state:
    st.session_state.loaded = False

# ---------------------------------------------------------
# LOAD ORDER BUTTON
# ---------------------------------------------------------
if st.button("Load Order"):
    so = smart_find_order(qref)

    if not so:
        st.error("❌ Could not find Sales Order for this Q-ref.")
        st.stop()

    st.success("Sales Order Loaded Successfully")

    company = so.get("company", "")
    project = so.get("projectName", "")

    st.markdown(f"### Customer: **{company}**")
    st.markdown(f"### Project: **{project}**")
    st.markdown(f"### Order Ref: **{qref}**")

    # Build line table with supplier mapping
    rows = []
    for li in so.get("lineItems", []):
        pid = li.get("productId", 0)
        if pid == 0:
            continue

        code = li.get("code", "").upper()
        prod_match = products_df[products_df["Code"] == code]

        if prod_match.empty:
            supplier_name = "UNKNOWN"
            supplier_id = 0
        else:
            supplier_name = prod_match["Supplier"].iloc[0]
            supplier_id = prod_match["Contact ID"].iloc[0]

        rows.append({
            "Select": False,
            "Supplier": supplier_name,
            "SupplierID": supplier_id,
            "Item Code": code,
            "Item Name": li.get("name", ""),
            "Qty": li.get("qty", 0),
            "Cost": li.get("unitCost", 0)
        })

    st.session_state.item_table = pd.DataFrame(rows)
    st.session_state.loaded = True

# ---------------------------------------------------------
# SHOW TABLE IF LOADED
# ---------------------------------------------------------
if st.session_state.loaded:

    st.subheader("Step 2 — Review & Select Items")
    edited = st.data_editor(
        st.session_state.item_table,
        key="editor",
        num_rows="dynamic",
        hide_index=True
    )

    st.session_state.item_table = edited

    st.subheader("Step 3 — Push POs")

    if st.button("Create Purchase Orders"):

        df = st.session_state.item_table
        selected = df[df["Select"] == True]

        if selected.empty:
            st.error("No items selected!")
            st.stop()

        grouped = selected.groupby("Supplier")

        results = []

        for supplier, grp in grouped:
            supplier_id = int(grp["SupplierID"].iloc[0])
            branch_id = branch_Avondale   # default for now

            payload = build_single_po_payload(
                qref=qref,
                supplier_id=supplier_id,
                supplier_name=supplier,
                branch_id=branch_id,
                df=grp
            )

            status, resp = push_po(payload)
            results.append((supplier, status, resp))

        st.subheader("PO Creation Results")

        for supplier, status, resp in results:
            if status == 200:
                st.success(f"PO for {supplier} created successfully")
            else:
                st.error(f"Failed for {supplier}: {resp}")
