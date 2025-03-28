import os
from peewee import SqliteDatabase
from migrations.migration_manager import apply_migrations, is_new_database

def create_legacy_database(db_path):
    """Create a database with the base schema but no migration info"""
    db = SqliteDatabase(db_path)
    db.execute_sql("""
        CREATE TABLE dikerecord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            strike INTEGER,
            dip INTEGER,
            distance REAL,
            angle REAL,
            raw_x REAL,
            raw_y REAL,
            lat REAL,
            lng REAL,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add some test data
    db.execute_sql(
        "INSERT INTO dikerecord (symbol, strike, dip) VALUES (?, ?, ?)",
        ("LEGACY", 45, 30)
    )
    db.close()

def test_database_init():
    test_db = "test.db"
    
    # Clean up any existing test database
    if os.path.exists(test_db):
        os.remove(test_db)
    
    print("\nTesting new database creation...")
    db = SqliteDatabase(test_db)
    apply_migrations(db)
    db.close()
    
    print("\nTesting existing database with migrations...")
    db = SqliteDatabase(test_db)
    apply_migrations(db)
    db.close()
    
    # Clean up and create legacy database
    os.remove(test_db)
    print("\nTesting pre-existing database without migration info...")
    create_legacy_database(test_db)
    
    # Try applying migrations to legacy database
    db = SqliteDatabase(test_db)
    apply_migrations(db)
    
    # Verify legacy data still exists and new columns are added
    cursor = db.execute_sql("SELECT symbol, memo FROM dikerecord")
    record = cursor.fetchone()
    print(f"Retrieved legacy record - Symbol: {record[0]}, Memo: {record[1]}")
    
    # Clean up
    db.close()
    os.remove(test_db)
    print("\nTest completed successfully!")

if __name__ == "__main__":
    test_database_init()