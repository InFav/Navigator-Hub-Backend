from sqlalchemy import create_engine, text
from database import DATABASE_URL
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def add_provider_column():
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Create connection
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Check if provider column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'firebase_users' 
                    AND column_name = 'provider';
                """))
                
                if not result.fetchone():
                    # Add provider column if it doesn't exist
                    print("Adding provider column...")
                    conn.execute(text("""
                        ALTER TABLE firebase_users 
                        ADD COLUMN provider VARCHAR(50);
                    """))
                    
                    # Update existing rows with 'google' as default provider
                    conn.execute(text("""
                        UPDATE firebase_users 
                        SET provider = 'google' 
                        WHERE provider IS NULL;
                    """))
                    
                    print("Provider column added successfully!")
                else:
                    print("Provider column already exists")
                
                trans.commit()
                print("Migration completed successfully!")
                
            except Exception as e:
                trans.rollback()
                print(f"Error during migration: {e}")
                raise
            
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

def verify_table_structure():
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        
        with conn.cursor() as cur:
            # Get all columns from the table
            cur.execute("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'firebase_users'
                ORDER BY ordinal_position;
            """)
            
            print("\nCurrent table structure:")
            for column in cur.fetchall():
                print(f"Column: {column[0]}")
                print(f"Type: {column[1]}")
                print(f"Max Length: {column[2]}")
                print("-" * 30)
                
    except Exception as e:
        print(f"Error verifying table structure: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    try:
        print("Starting migration...")
        add_provider_column()
        print("\nVerifying table structure...")
        verify_table_structure()
    except Exception as e:
        print(f"Migration failed: {e}")