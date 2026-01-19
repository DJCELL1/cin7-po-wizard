import streamlit as st
import pandas as pd
import requests
import json
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, Any, Tuple
from db_config import get_product_database

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="HDL PO Wizard v4", layout="wide")
st.title("📦 HDL Purchase Order Builder — Multi-Supplier Edition (Google Sheets Version)")

# ---------------------------------------------------------
# CIN7 CONFIG
# ---------------------------------------------------------
cin7 = st.secrets["cin7"]
base_url = cin7["base_url"].rstrip("/")
api_username = cin7["api_username"]
api_key = cin7["api_key"]
auth = HTTPBasicAuth(api_username, api_key)

branch_Hamilton = cin7.get("branch_Hamilton", cin7.get("branch_hamilton_id", 230))
branch_Avondale = cin7.get("branch_Avondale", cin7.get("branch_avondale_id", 3))

# ---------------------------------------------------------
# GOOGLE SHEETS DATABASE CONFIG
# ---------------------------------------------------------
# Products are now stored in Google Sheets instead of PostgreSQL
# See db_config.py and MIGRATION_GUIDE.md for details

# ---------------------------------------------------------
# HTTP HELPERS
# ---------------------------------------------------------
def cin7_get(endpoint: str, params: Optional[Dict[str, Any]] = None):
    url = f"{base_url}/{endpoint}"
    r = requests.get(url, params=params, auth=auth, timeout=30)
    return r.json() if r.status_code == 200 else None

# ---------------------------------------------------------
# DATABASE LOOKUPS (CACHED)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def db_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Query products from Google Sheets database."""
    sku = (sku or "").strip()
    if not sku:
        return None

    db = get_product_database()
    if not db:
        return None

    try:
        # Search for SKU in the database
        results = db.search("sku", sku)

        if len(results) == 0:
            return None

        # Return first match as dictionary
        return results.iloc[0].to_dict()
    except Exception as e:
        st.warning(f"⚠️ Database query error for SKU {sku}: {e}")
        return None

@st.cache_data(ttl=3600)
def db_supplier_map_get(supplier_name: str) -> Optional[int]:
    """Look up supplier ID from Google Sheets database."""
    supplier_name = (supplier_name or "").strip()
    if not supplier_name:
        return None

    db = get_product_database()
    if not db:
        return None

    try:
        # Search for supplier by name
        results = db.search("suppliername", supplier_name)

        if len(results) == 0:
            return None

        # Return supplier ID
        row = results.iloc[0]
        supplier_id = row.get("supplierid")
        if supplier_id:
            return int(supplier_id)
        return None
    except Exception as e:
        st.warning(f"⚠️ Database query error for supplier {supplier_name}: {e}")
        return None

# ---------------------------------------------------------
# BOM LOOKUP (CACHED)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_bom(code: str):
    search = cin7_get("v1/BomMasters", params={"where": f"code='{code}'"})
    if not search:
        return []
    bom_id = search[0].get("id")
    if not bom_id:
        return []

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
def smart_find_order(qref: str):
    q = (qref or "").strip().upper()
    if not q:
        return None

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
# PO BUILD
# ---------------------------------------------------------
def build_po_payloads(qref: str, df: pd.DataFrame):
    po_groups = []

    for supplier_name, grp in df.groupby("Supplier"):
        supplier_id = int(grp["Contact ID"].iloc[0])
        po_ref = f"PO-{qref}{supplier_name[:4].upper()}"

        line_items = []
        for _, r in grp.iterrows():
            code = (r["Item Code"] or "").strip()
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

            # Keeping your existing behaviour, but ideally this should be YOUR staff/member ID,
            # not the supplier ID. Change when you're ready.
            "memberId": supplier_id,

            "branchId": branch_Avondale,  # you hardcoded 3 previously
            "staffId": 1,
            "enteredById": 1,
            "isApproved": True,
            "lineItems": line_items
        }

        po_groups.append((supplier_name, po_ref, payload))

    return po_groups

def push_po(payload: Dict[str, Any]) -> Tuple[int, str]:
    url = f"{base_url}/v1/PurchaseOrders"
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, headers=headers, data=json.dumps([payload]), auth=auth, timeout=60)
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
    missing_in_railway = []

    for li in so.get("lineItems", []):
        if li.get("productId", 0) == 0:
            continue

        code = (li.get("code", "") or "").upper().strip()
        if not code:
            continue

        # Check SKU exists in cin7_products table
        prod = db_product_by_sku(code)
        if not prod:
            missing_in_railway.append(code)

        # Auto-populate supplier from database if available
        supplier_name = prod.get("supplier_name", "") if prod else ""
        supplier_code = prod.get("supplier_code", "") if prod else ""

        rows.append({
            "Select": False,
            "Supplier": supplier_name,
            "Supplier Code": supplier_code,
            "Contact ID": "",        # resolved from supplier_map
            "Item Code": code,
            "Item Name": li.get("name", ""),
            "Qty": li.get("qty", 0),
            "Cost": li.get("unitCost", 0),
            "Notes": "" if prod else "SKU not found in cin7_products table"
        })

    if missing_in_railway:
        st.warning(f"⚠️ {len(missing_in_railway)} SKUs not found in cin7_products table. They can still be ordered, but check codes.")

    st.session_state.lines = pd.DataFrame(rows)

# ---------------------------------------------------------
# UI STEP 2 — Edit + Resolve Supplier IDs
# ---------------------------------------------------------
if st.session_state.lines is not None:
    st.header("Step 2 — Select Items + Supplier Mapping")

    st.caption(
        "Supplier names are auto-populated from cin7_products. Edit if needed, then click **Resolve Contact IDs**."
    )

    edited = st.data_editor(
        st.session_state.lines,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(),
            "Supplier": st.column_config.TextColumn(help="Supplier name (must match supplier_map key)"),
            "Supplier Code": st.column_config.TextColumn(disabled=True, help="Supplier's product code"),
            "Contact ID": st.column_config.TextColumn(disabled=True),
            "Notes": st.column_config.TextColumn(disabled=True),
        }
    )
    st.session_state.lines = edited

    colA, colB = st.columns([1, 2])
    with colA:
        if st.button("Resolve Contact IDs"):
            df = st.session_state.lines.copy()

            missing_supplier = 0
            unmapped = 0

            for i, r in df.iterrows():
                supplier_name = (r.get("Supplier") or "").strip()
                if not supplier_name:
                    df.at[i, "Contact ID"] = ""
                    df.at[i, "Notes"] = "Missing Supplier"
                    missing_supplier += 1
                    continue

                cid = db_supplier_map_get(supplier_name)
                if cid is None:
                    df.at[i, "Contact ID"] = ""
                    df.at[i, "Notes"] = "Supplier not mapped in supplier_map table"
                    unmapped += 1
                else:
                    df.at[i, "Contact ID"] = int(cid)
                    # keep existing notes if it was about sku missing
                    if df.at[i, "Notes"] in ("Missing Supplier", "Supplier not mapped in supplier_map table"):
                        df.at[i, "Notes"] = ""

            st.session_state.lines = df

            if missing_supplier:
                st.warning(f"⚠️ {missing_supplier} line(s) missing Supplier.")
            if unmapped:
                st.warning(f"⚠️ {unmapped} supplier(s) not mapped yet. Add them to the supplier_map table.")

    with colB:
        st.info(
            "To add a supplier mapping, run SQL:\n"
            "INSERT INTO supplier_map (supplier_name, cin7_contact_id) VALUES ('NAME', 1234)\n"
            "ON CONFLICT (supplier_name) DO UPDATE SET cin7_contact_id = EXCLUDED.cin7_contact_id;"
        )

# ---------------------------------------------------------
# UI STEP 3 — Create POs
# ---------------------------------------------------------
if st.session_state.lines is not None:
    st.header("Step 3 — Create Purchase Orders")

    if st.button("Create POs"):
        df_all = st.session_state.lines.copy()
        selected = df_all[df_all["Select"] == True]

        if selected.empty:
            st.error("❌ No items selected.")
            st.stop()

        # Validate: Supplier and Contact ID must exist for selected lines
        selected["Supplier"] = selected["Supplier"].astype(str).str.strip()
        selected["Contact ID"] = selected["Contact ID"].astype(str).str.strip()

        missing_supplier = selected[selected["Supplier"] == ""]
        missing_cid = selected[selected["Contact ID"] == ""]

        if not missing_supplier.empty:
            st.error("❌ Some selected lines are missing Supplier. Fill Supplier then Resolve Contact IDs.")
            st.dataframe(missing_supplier[["Item Code", "Item Name", "Supplier", "Notes"]], use_container_width=True)
            st.stop()

        if not missing_cid.empty:
            st.error("❌ Some selected lines have no Contact ID (supplier not mapped). Map supplier then Resolve Contact IDs.")
            st.dataframe(missing_cid[["Item Code", "Item Name", "Supplier", "Notes"]], use_container_width=True)
            st.stop()

        # Convert Contact ID to int now that it's validated
        selected["Contact ID"] = selected["Contact ID"].astype(int)

        # Create POs per supplier group
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
