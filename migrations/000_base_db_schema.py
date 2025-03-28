from peewee import *
import datetime

def migrate(db):
    """Create the base database schema"""
    # Check if table exists first
    cursor = db.execute_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dikerecord'"
    )
    if cursor.fetchone() is None:
        # Table doesn't exist, create it
        db.execute_sql("""
            CREATE TABLE IF NOT EXISTS dikerecord (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                stratum TEXT,
                rock_type TEXT,
                era TEXT,
                map_sheet TEXT,
                address TEXT,
                distance REAL,
                angle REAL,
                x_coord_1 REAL,
                y_coord_1 REAL,
                lat_1 REAL,
                lng_1 REAL,
                x_coord_2 REAL,
                y_coord_2 REAL,
                lat_2 REAL,
                lng_2 REAL,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        print("DikeRecord table already exists, skipping creation")

def rollback(db):
    """Drop all base tables"""
    db.execute_sql("DROP TABLE IF EXISTS dikerecord")