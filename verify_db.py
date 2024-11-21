import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def verify_database():
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        
        # Create cursor
        cur = conn.cursor()
        
        # Check table structure
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'users'
            ORDER BY ordinal_position;
        """)
        
        print("\nTable structure:")
        for row in cur.fetchall():
            print(f"Column: {row[0]}")
            print(f"Type: {row[1]}")
            print(f"Max Length: {row[2]}")
            print("-" * 30)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error verifying database: {e}")

if __name__ == "__main__":
    verify_database()