import sqlite3
import requests
import base64
import tomllib
import time
import os
from datetime import datetime


# -------------------------------
# Load secrets
# -------------------------------
def load_secrets():
    secret_path = os.path.join(".streamlit", "secrets.toml")
    if not os.path.exists(secret_path):
        raise FileNotFoundError("Uso – secrets.toml not found!")

    with open(secret_path, "rb") as f:
        return tomllib.load(f)


secrets = load_secrets()

USERNAME = secrets["cin7"]["api_username"]
API_KEY = secrets["cin7"]["api_key"]
BASE_URL = secrets["cin7"]["base_url"]

if not BASE_URL.endswith("/"):
    BASE_URL += "/"

combo = f"{USERNAME}:{API_KEY}".encode("utf-8")
encoded = base64.b64encode(combo).decode("utf-8")
HEADERS = {"Authorization": f"Basic {encoded}"}


# -------------------------------
# Load/save sync timestamp
# -------------------------------
SYNC_FILE = "last_sync.txt"

def get_last_sync():
    if not os.path.exists(SYNC_FILE):
        return None
    with open(SYNC_FILE, "r") as f:
        return f.read().strip()

def save_last_sync():
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    with open(SYNC_FILE, "w") as f:
        f.write(now)


# -------------------------------
# Get highest product ID in DB
# -------------------------------
def get_max_product_id():
    con = sqlite3.connect("products.db")
    cur = con.cursor()
    cur.execute("SELECT MAX(id) FROM products;")
    result = cur.fetchone()[0]
    con.close()
    return result or 0


# -------------------------------
# Retry wrapper for Cin7
# -------------------------------
def safe_request(url):
    retries = 0
    while retries < 5:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)

            if response.status_code == 429:
                print("Cin7 crying… waiting 2 seconds…")
                time.sleep(2)
                continue

            response.raise_for_status()
            return response

        except requests.exceptions.RequestException:
            print("Cin7 had a seizure, retrying in 3 seconds…")
            time.sleep(3)
            retries += 1

    raise Exception("Cin7 failed after 5 retries. They need to sort their life out.")


# -------------------------------
# Fetch PRODUCTS modified since last sync
# -------------------------------
def fetch_modified_products(last_sync):
    if not last_sync:
        print("No last sync date found. Skipping modified sync (you already have full DB).")
        return []

    print(f"Checking for modified products since {last_sync}")

    url = f"{BASE_URL}v1/Products?rows=250&where=ModifiedDate > '{last_sync}'"
    response = safe_request(url)
    data = response.json()

    print(f"Found {len(data)} modified products.")
    return data


# -------------------------------
# Fetch NEW products by ID > max_id
# -------------------------------
def fetch_new_products():
    max_id = get_max_product_id()
    print(f"Checking for new products where id > {max_id}")

    url = f"{BASE_URL}v1/Products?rows=250&where=id > {max_id}"
    response = safe_request(url)
    data = response.json()

    print(f"Found {len(data)} new products.")
    return data


# -------------------------------
# Save changes to DB
# -------------------------------
def save_products(products):
    con = sqlite3.connect("products.db")
    cur = con.cursor()

    for p in products:
        supplier_code = None
        if p.get("productOptions"):
            supplier_code = p["productOptions"][0].get("supplierCode")

        cur.execute("""
            INSERT INTO products (
                code, id, name, styleCode, stockControl,
                supplierCode, supplierName, supplierId,
                description, lastModified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                id=excluded.id,
                name=excluded.name,
                styleCode=excluded.styleCode,
                stockControl=excluded.stockControl,
                supplierCode=excluded.supplierCode,
                supplierName=excluded.supplierName,
                supplierId=excluded.supplierId,
                description=excluded.description,
                lastModified=excluded.lastModified
        """, (
            p.get("code") or p.get("styleCode"),
            p.get("id"),
            p.get("name"),
            p.get("styleCode"),
            p.get("stockControl"),
            supplier_code,
            p.get("brand"),
            p.get("supplierId"),
            p.get("description", ""),
            p.get("modifiedDate", "")
        ))

    con.commit()
    con.close()


# -------------------------------
# MAIN SYNC LOGIC
# -------------------------------
def sync_products():
    print("Starting LIGHTNING SYNC, uce…")

    last_sync = get_last_sync()

    modified = fetch_modified_products(last_sync)
    new = fetch_new_products()

    products = modified + new

    if not products:
        print("No new or modified products. Fa'amalulu, you're already fresh.")
        save_last_sync()
        return

    save_products(products)

    save_last_sync()
    print(f"Seki! Updated {len(products)} products lightning fast, sole.")


# -------------------------------
# EXECUTE
# -------------------------------
if __name__ == "__main__":
    sync_products()
