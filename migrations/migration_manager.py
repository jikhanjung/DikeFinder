import os
import importlib.util
from peewee import SqliteDatabase

def get_migrations():
    """Get all migration modules sorted by version number"""
    migrations_dir = os.path.dirname(__file__)
    migration_files = [f for f in os.listdir(migrations_dir) 
                      if f.endswith('.py') 
                      and f != '__init__.py'
                      and f != 'migration_manager.py']  # Exclude the manager itself
    
    migrations = []
    for filename in sorted(migration_files):
        module_name = filename[:-3]
        module_path = os.path.join(migrations_dir, filename)
        
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        migrations.append((module_name, module))
    
    return migrations

def check_base_schema(db):
    """Check if database matches base schema (000)"""
    try:
        # Get table info for dikerecord
        cursor = db.execute_sql("PRAGMA table_info(dikerecord)")
        columns = {col[1].lower() for col in cursor.fetchall()}
        
        # Print current schema for debugging
        print("Current database columns:", columns)
        
        # Minimum required columns
        required_columns = {
            'id', 'symbol', 'distance', 'angle', 
            'created_date'
        }
        
        # Check if all required columns exist
        missing_columns = required_columns - columns
        if missing_columns:
            print(f"Missing required columns: {missing_columns}")
            return False
            
        return True
    except Exception as e:
        print(f"Error checking schema: {str(e)}")
        return False

def init_migration_table(db):
    """Initialize the migration tracking table"""
    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS migration_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT UNIQUE,
            applied_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

def get_applied_migrations(db):
    """Get list of already applied migrations"""
    try:
        cursor = db.execute_sql("SELECT migration_name FROM migration_record")
        return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()

def apply_migrations(db):
    """Apply all pending migrations"""
    # Check if migration_record table exists
    cursor = db.execute_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migration_record'"
    )
    migration_table_exists = cursor.fetchone() is not None
    
    if not migration_table_exists:
        # Check if this is a pre-existing database with base schema
        if check_base_schema(db):
            print("Found pre-existing database with base schema")
            # Initialize migration table and mark base migration as applied
            init_migration_table(db)
            db.execute_sql(
                "INSERT INTO migration_record (migration_name) VALUES (?)",
                ("000_base_db_schema",)
            )
        else:
            # Instead of failing, try to create tables
            print("Database doesn't match base schema, attempting to apply all migrations...")
            init_migration_table(db)
    
    # Continue with regular migration process
    applied = get_applied_migrations(db)
    print("Already applied migrations:", applied)
    
    for name, module in get_migrations():
        if name not in applied:
            print(f"Applying migration: {name}")
            try:
                module.migrate(db)
                db.execute_sql(
                    "INSERT INTO migration_record (migration_name) VALUES (?)",
                    (name,)
                )
                print(f"Successfully applied migration: {name}")
            except Exception as e:
                print(f"Error applying migration {name}: {str(e)}")
                raise

def is_new_database(db_path):
    """Check if this is a new database"""
    return not os.path.exists(db_path) or os.path.getsize(db_path) == 0