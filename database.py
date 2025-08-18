import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, timezone, timedelta
import psycopg2.extras

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

    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        coins INTEGER DEFAULT 0,
        last_claim TIMESTAMP WITH TIME ZONE DEFAULT NULL,
        last_quest TIMESTAMP WITH TIME ZONE DEFAULT NULL,
        is_muted_until TIMESTAMP WITH TIME ZONE DEFAULT NULL
    )
    """)

    # Transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        type TEXT,
        amount INTEGER,
        timestamp TIMESTAMP WITH TIME ZONE,
        target_user_id BIGINT
    )
    """)

    # Pending Requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pending_requests (
        request_id TEXT PRIMARY KEY,
        from_id BIGINT NOT NULL,
        to_id BIGINT NOT NULL,
        amount INTEGER NOT NULL,
        from_username TEXT,
        to_username TEXT,
        status TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL
    )
    """)

    # === FUNCTIONS ===

    def log_transaction(user_id: int, tx_type: str, amount: int, target_user_id: int = None):
        timestamp = datetime.now(timezone.utc)
        cursor.execute("""
            INSERT INTO transactions (user_id, type, amount, timestamp, target_user_id)
            VALUES (%s, %s, %s, %s, %s)
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
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row if row else (0, None)

    def update_coins(user_id, amount):
        cursor.execute("UPDATE users SET coins = coins + %s WHERE user_id = %s", (amount, user_id))

    def set_last_claim(user_id, date_time):
        cursor.execute("UPDATE users SET last_claim = %s WHERE user_id = %s", (date_time, user_id))

    def set_coins(user_id, amount):
        cursor.execute("UPDATE users SET coins = %s WHERE user_id = %s", (amount, user_id))

    def get_top_users(limit=10):
        cursor.execute("SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT %s", (limit,))
        return cursor.fetchall()

    def find_user_id_by_username(username):
        cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
        result = cursor.fetchone()
        return result["user_id"] if result else None

    def add_pending_request(request_id: str, from_id: int, to_id: int, from_username: str, to_username: str, amount: int):
        created_at = datetime.now(timezone.utc)
        cursor.execute("""
            INSERT INTO pending_requests (request_id, from_id, to_id, from_username, to_username, amount, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (request_id, from_id, to_id, from_username, to_username, amount, created_at))

    def get_pending_request(request_id: str):
        cursor.execute("SELECT from_id, to_id, from_username, to_username, amount FROM pending_requests WHERE request_id = %s", (request_id,))
        row = cursor.fetchone()
        return row if row else None

    def delete_pending_request(request_id: str):
        cursor.execute("DELETE FROM pending_requests WHERE request_id = %s", (request_id,))

    def cleanup_old_requests(days: int = 1):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cursor.execute("DELETE FROM pending_requests WHERE created_at < %s", (cutoff,))

    def mute_user(user_id: int, hours: int = 4):
        until = datetime.now(timezone.utc) + timedelta(hours=hours)
        cursor.execute("UPDATE users SET is_muted_until = %s WHERE user_id = %s", (until, user_id))

    def is_user_muted(user_id):
        cursor.execute("""
            SELECT is_muted_until FROM users WHERE user_id = %s
        """, (user_id,))
        row = cursor.fetchone()
        if row and row["is_muted_until"]:
            return float(row["is_muted_until"]) > datetime.now(timezone.utc).timestamp()
        return False

    def has_used_quest_today(user_id: int) -> bool:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor.execute("SELECT last_quest FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row and row["last_quest"] == today_str

    def is_user_bankrupt(user_id: int) -> bool:
        cursor.execute("SELECT coins FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return row and row["coins"] <= 0
    
    def update_user_quest_time(user_id: int):
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor.execute("UPDATE users SET last_quest = %s WHERE user_id = %s", (today_str, user_id))

except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")

