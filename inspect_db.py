import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

def inspect_database():
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all tables
            cur.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = cur.fetchall()
            
            print("\nExisting tables:")
            for table in tables:
                table_name = table['tablename']
                print(f"\nTable: {table_name}")
                print("-" * 50)
                
                # Get columns for each table
                cur.execute(f"""
                    SELECT column_name, data_type, character_maximum_length, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                
                for column in columns:
                    print(f"Column: {column['column_name']}")
                    print(f"Type: {column['data_type']}")
                    print(f"Max Length: {column['character_maximum_length']}")
                    print(f"Nullable: {column['is_nullable']}")
                    print("-" * 30)

    except Exception as e:
        print(f"Error inspecting database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    inspect_database()