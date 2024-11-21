import psycopg2
import json
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

def backup_database():
    try:
        # Get database credentials from environment
        DB_NAME = os.getenv("DB_NAME")
        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")
        DB_HOST = os.getenv("DB_HOST")
        DB_PORT = os.getenv("DB_PORT")

        # Connect to database
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )

        # Create cursor
        cur = conn.cursor()

        # Get all tables
        cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        
        tables = cur.fetchall()
        backup_data = {}

        # Backup schema and data for each table
        for table in tables:
            table_name = table[0]
            print(f"Backing up table: {table_name}")

            # Get table schema
            cur.execute(f"""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            
            # Get table data
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()
            
            # Store both schema and data
            backup_data[table_name] = {
                'schema': [
                    {
                        'column_name': col[0],
                        'data_type': col[1],
                        'max_length': col[2],
                        'is_nullable': col[3]
                    } for col in columns
                ],
                'data': [list(row) for row in rows]
            }

        # Create backup file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_{DB_NAME}_{timestamp}.json"
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
            
        print(f"Database backup created successfully: {backup_file}")

        # Create restore script
        restore_script = f"restore_script_{timestamp}.py"
        with open(restore_script, 'w') as f:
            f.write('''import psycopg2
import json
from dotenv import load_dotenv
import os

load_dotenv()

def restore_database(backup_file):
    try:
        # Read backup file
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        # Connect to database
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        
        conn.autocommit = False
        cur = conn.cursor()

        try:
            # Restore each table
            for table_name, table_data in backup_data.items():
                print(f"Restoring table: {table_name}")
                
                # Recreate table if needed
                columns = [
                    f"{col['column_name']} {col['data_type']}"
                    + (f"({col['max_length']})" if col['max_length'] else "")
                    + (" NULL" if col['is_nullable'] == 'YES' else " NOT NULL")
                    for col in table_data['schema']
                ]
                
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        {', '.join(columns)}
                    )
                """)

                # Insert data
                if table_data['data']:
                    cols = [col['column_name'] for col in table_data['schema']]
                    placeholder = ','.join(['%s'] * len(cols))
                    insert_query = f"""
                        INSERT INTO {table_name} ({','.join(cols)})
                        VALUES ({placeholder})
                        ON CONFLICT DO NOTHING
                    """
                    cur.executemany(insert_query, table_data['data'])

            conn.commit()
            print("Restore completed successfully")

        except Exception as e:
            conn.rollback()
            print(f"Error during restore: {e}")
            raise

    except Exception as e:
        print(f"Restore error: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python restore_script.py <backup_file>")
    else:
        restore_database(sys.argv[1])
''')
            
        print(f"Restore script created: {restore_script}")

    except Exception as e:
        print(f"Backup error: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    backup_database()