import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

def create_safe_migration():
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        
        cur = conn.cursor()

        # Check existing columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users';
        """)
        
        existing_columns = [row[0] for row in cur.fetchall()]
        print(f"Existing columns: {existing_columns}")

        # Create migration content
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        migration_content = f'''"""add missing user columns and timestamps

Revision ID: {timestamp}
Revises: 
Create Date: {datetime.now().isoformat()}

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers
revision = '{timestamp}'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Check if users table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'users' not in tables:
        # Create users table if it doesn't exist
        op.create_table('users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(), nullable=True),
            sa.Column('uid', sa.String(), nullable=True),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('picture', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), server_onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_uid'), 'users', ['uid'], unique=True)
    else:
        # Add columns if they don't exist
        columns = [c['name'] for c in inspector.get_columns('users')]
        
        if 'uid' not in columns:
            op.add_column('users', sa.Column('uid', sa.String(), nullable=True))
            op.create_index(op.f('ix_users_uid'), 'users', ['uid'], unique=True)
        
        if 'name' not in columns:
            op.add_column('users', sa.Column('name', sa.String(), nullable=True))
        
        if 'picture' not in columns:
            op.add_column('users', sa.Column('picture', sa.String(), nullable=True))
            
        if 'created_at' not in columns:
            op.add_column('users', 
                sa.Column('created_at', sa.DateTime(), 
                         server_default=sa.text('CURRENT_TIMESTAMP'), 
                         nullable=False))
                         
        if 'updated_at' not in columns:
            op.add_column('users', 
                sa.Column('updated_at', sa.DateTime(), 
                         server_default=sa.text('CURRENT_TIMESTAMP'),
                         nullable=False))
            
            # Add trigger for updated_at
            op.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            
            op.execute("""
                DROP TRIGGER IF EXISTS update_users_updated_at ON users;
                CREATE TRIGGER update_users_updated_at
                    BEFORE UPDATE ON users
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """)


def downgrade() -> None:
    # Remove trigger first
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop columns
    try:
        op.drop_index(op.f('ix_users_uid'), table_name='users')
        op.drop_column('users', 'updated_at')
        op.drop_column('users', 'created_at')
        op.drop_column('users', 'uid')
        op.drop_column('users', 'name')
        op.drop_column('users', 'picture')
    except Exception:
        pass  # Ignore errors if columns don't exist
'''

        # Create versions directory if it doesn't exist
        os.makedirs('migrations/versions', exist_ok=True)

        # Write migration file
        migration_file = f'migrations/versions/{timestamp}_add_missing_user_columns.py'
        with open(migration_file, 'w') as f:
            f.write(migration_content)
            
        print(f"Created safe migration file: {migration_file}")
        print("You can now run: alembic upgrade head")
        
    except Exception as e:
        print(f"Error creating migration: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    create_safe_migration()