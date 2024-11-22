import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def create_new_tables():
    # Get database credentials from environment variables
    db_params = {
        'dbname': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'host': os.getenv('DB_HOST'),
        'port': os.getenv('DB_PORT')
    }

    # SQL to create the new tables
    create_tables_sql = """
    -- Create new persona table
    CREATE TABLE IF NOT EXISTS persona_input_new (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR NOT NULL,
        profession VARCHAR NOT NULL,
        current_work VARCHAR NOT NULL,
        goal VARCHAR NOT NULL,
        journey TEXT,
        company_size VARCHAR,
        industry_target VARCHAR NOT NULL,
        target_type VARCHAR NOT NULL,
        favorite_posts TEXT NOT NULL,
        best_posts TEXT NOT NULL,
        posts_to_create INTEGER NOT NULL,
        post_purpose VARCHAR NOT NULL,
        timeline VARCHAR NOT NULL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- Create index on user_id
    CREATE INDEX IF NOT EXISTS idx_persona_input_new_user_id ON persona_input_new(user_id);

    -- Create new posts table
    CREATE TABLE IF NOT EXISTS posts_new (
        id SERIAL PRIMARY KEY,
        persona_id INTEGER NOT NULL,
        post_content TEXT NOT NULL,
        post_date TIMESTAMPTZ NOT NULL,
        clicks INTEGER DEFAULT 0,
        regenerate_clicks INTEGER DEFAULT 0,
        FOREIGN KEY (persona_id) REFERENCES persona_input_new(id)
    );

    -- Create index on persona_id for faster joins
    CREATE INDEX IF NOT EXISTS idx_posts_new_persona_id ON posts_new(persona_id);
    """

    try:
        # Connect to the database
        print("Connecting to database...")
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()

        # Create the tables
        print("Creating new tables...")
        cursor.execute(create_tables_sql)
        
        print("Tables created successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    create_new_tables()