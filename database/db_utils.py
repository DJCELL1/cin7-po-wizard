import sqlite3

def get_connection():
    return sqlite3.connect("products.db")

def run_query(sql, params=None):
    con = get_connection()
    cur = con.cursor()
    cur.execute(sql, params or [])
    rows = cur.fetchall()
    con.close()
    return rows
