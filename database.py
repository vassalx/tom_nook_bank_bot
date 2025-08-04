import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, timezone

# Load environment variables from .env
load_dotenv()

# Fetch variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Connect to the database
try:
    connection = psycopg2.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME
    )
    connection.autocommit = True
    print("✅ PostgreSQL connection successful!")

    cursor = connection.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        coins INTEGER DEFAULT 0,
        last_claim TEXT DEFAULT NULL
    )
    """)

    # Transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount INTEGER,
        timestamp TEXT,
        target_user_id INTEGER DEFAULT NULL
    )
    """)

    def log_transaction(user_id: int, tx_type: str, amount: int, target_user_id: int = None):
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO transactions (user_id, type, amount, timestamp, target_user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, tx_type, amount, timestamp, target_user_id))
        connection.commit()

    def add_user(user_id, username=None):
        if username:
            cursor.execute("""
                INSERT INTO users (user_id, username)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
            """, (user_id, username))
        else:
            cursor.execute("""
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id,))
    def get_user(user_id):
        cursor.execute("""
            SELECT coins, last_claim FROM users WHERE user_id = %s
        """, (user_id,))
        row = cursor.fetchone()
        return row if row else (0, "")
    
    def update_coins(user_id, amount):
        cursor.execute("""
            UPDATE users SET coins = coins + %s WHERE user_id = %s
        """, (amount, user_id))
            

    def set_last_claim(user_id, date_str):
        cursor.execute("""
            UPDATE users SET last_claim = %s WHERE user_id = %s
        """, (date_str, user_id))
            

    def set_coins(user_id, amount):
        cursor.execute("""
            UPDATE users SET coins = %s WHERE user_id = %s
        """, (amount, user_id))
            

    def get_top_users(limit=10):
        cursor.execute("""
            SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT %s
        """, (limit,))
        return cursor.fetchall()
            

    def find_user_id_by_username(username):
        cursor.execute("""
            SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s)
        """, (username,))
        result = cursor.fetchone()
        return result[0] if result else None
            

except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")
