import sqlite3
import pandas as pd

def load_products(db_path="products.db"):
    con = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM products", con)
    con.close()
    return df
