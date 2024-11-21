from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

def create_database():
    # Connect to default database to create new database
    default_db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/postgres"
    engine = create_engine(default_db_url)
    
    db_name = os.getenv('DB_NAME')
    
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # Check if database exists
        result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
        exists = result.scalar()
        
        if not exists:
            try:
                # Create database
                conn.execute(text(f'CREATE DATABASE {db_name}'))
                print(f"Database {db_name} created successfully")
            except Exception as e:
                print(f"Error creating database: {e}")
        else:
            print(f"Database {db_name} already exists")

if __name__ == "__main__":
    create_database()