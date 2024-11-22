import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def create_tables():
    try:
        # Connect directly to the existing database
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),  # This will be dcl55gg9emha80
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT', '5432')
        )
        cur = conn.cursor()

        # Create tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                message TEXT NOT NULL,
                sender VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS persona_input (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                persona_id INTEGER NOT NULL,
                post_content TEXT NOT NULL,
                post_date TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicks INTEGER DEFAULT 0,
                regenerate_clicks INTEGER DEFAULT 0
            );
        """)
        
        conn.commit()
        print("Tables created successfully")
        
        # Verify tables were created
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('chat_history', 'persona_input', 'posts');
        """)
        
        existing_tables = cur.fetchall()
        print("Existing tables:", [table[0] for table in existing_tables])
        
        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    create_tables()