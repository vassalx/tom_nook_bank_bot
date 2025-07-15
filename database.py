import psycopg2
from dotenv import load_dotenv
import os

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

    with connection.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            last_claim TEXT DEFAULT ''
        )
        """)

    def add_user(user_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (user_id) VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id,))

    def get_user(user_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT coins, last_claim FROM users WHERE user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
            return row if row else (0, "")

    def update_coins(user_id, amount):
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET coins = coins + %s WHERE user_id = %s
            """, (amount, user_id))

    def set_last_claim(user_id, date_str):
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET last_claim = %s WHERE user_id = %s
            """, (date_str, user_id))

    def set_coins(user_id, amount):
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET coins = %s WHERE user_id = %s
            """, (amount, user_id))

    def get_top_users(limit=10):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT %s
            """, (limit,))
            return cursor.fetchall()

except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")
