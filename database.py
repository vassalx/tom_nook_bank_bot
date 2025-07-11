import sqlite3

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    last_claim TEXT DEFAULT ''
)
""")
conn.commit()

def add_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT coins, last_claim FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row if row else (0, "")

def update_coins(user_id, amount):
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def set_last_claim(user_id, date_str):
    cursor.execute("UPDATE users SET last_claim = ? WHERE user_id = ?", (date_str, user_id))
    conn.commit()

def set_coins(user_id, amount):
    cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def get_top_users():
    cursor.execute("SELECT user_id, coins FROM users ORDER BY coins DESC")
    return cursor.fetchall()
