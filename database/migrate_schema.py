import sqlite3

con = sqlite3.connect("products.db")
cur = con.cursor()

cur.execute("ALTER TABLE products RENAME TO products_old;")

cur.execute("""
CREATE TABLE products (
    code TEXT PRIMARY KEY,
    id INTEGER,
    name TEXT,
    styleCode TEXT,
    stockControl TEXT,
    supplierCode TEXT,
    supplierName TEXT,
    supplierId INTEGER,
    description TEXT,
    lastModified TEXT
);
""")

cur.execute("""
INSERT OR IGNORE INTO products (code, id, name, styleCode, stockControl,
                                supplierCode, supplierName, supplierId,
                                description, lastModified)
SELECT code, id, name, styleCode, stockControl,
       supplierCode, supplierName, supplierId,
       description, lastModified
FROM products_old;
""")

con.commit()
con.close()

print("Migration complete.")
