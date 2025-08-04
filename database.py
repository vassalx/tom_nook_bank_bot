import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, timedelta

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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_requests (
        request_id TEXT PRIMARY KEY,
        from_id INTEGER NOT NULL,
        to_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    def log_transaction(user_id: int, tx_type: str, amount: int, target_user_id: int = None):
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO transactions (user_id, type, amount, timestamp, target_user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, tx_type, amount, timestamp, target_user_id))

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
    
    def add_pending_request(request_id: str, from_id: int, to_id: int, amount: int):
        created_at = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO pending_requests (request_id, from_id, to_id, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (request_id, from_id, to_id, amount, created_at)
        )

    def get_pending_request(request_id: str):
        cursor.execute("SELECT from_id, to_id, amount FROM pending_requests WHERE request_id = ?", (request_id,))
        row = cursor.fetchone()
        return row if row else None

    def delete_pending_request(request_id: str):
        cursor.execute("DELETE FROM pending_requests WHERE request_id = ?", (request_id,))

    def cleanup_old_requests(days: int = 1):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor.execute("DELETE FROM pending_requests WHERE created_at < ?", (cutoff,))
            

except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")
