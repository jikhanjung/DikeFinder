from peewee import *
import time
import random
import string
from playhouse.migrate import SqliteMigrator, migrate as migrate_fields

def base62_encode(num):
    chars = string.digits + string.ascii_letters
    base = len(chars)
    result = ''
    while num > 0:
        num, rem = divmod(num, base)
        result = chars[rem] + result
    return result or '0'

def generate_sortable_id(length=10):
    t = int(time.time() * 1000)
    r = random.randint(0, 9999)
    combined = int(f"{t}{r}")
    encoded = base62_encode(combined)
    return encoded.rjust(length, '0')

def column_exists(db, table, column):
    """Check if a column exists in the table"""
    cursor = db.execute_sql(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def index_exists(db, index_name):
    """Check if an index exists"""
    cursor = db.execute_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,)
    )
    return cursor.fetchone() is not None

def migrate(db):
    """
    Add unique_id column to DikeRecord table and populate it for existing records
    """
    migrator = SqliteMigrator(db)

    # Step 1: Check if column exists and add if it doesn't
    if not column_exists(db, 'dikerecord', 'unique_id'):
        print("Adding unique_id column...")
        migrate_fields(
            migrator.add_column('dikerecord', 'unique_id', 
                               CharField(max_length=10, null=True))
        )
    else:
        print("unique_id column already exists")

    # Step 2: Generate and set unique IDs for records that don't have one
    print("Checking for records without unique_id...")
    cursor = db.execute_sql('SELECT id FROM dikerecord WHERE unique_id IS NULL')
    records = cursor.fetchall()
    
    if records:
        print(f"Generating unique_ids for {len(records)} records...")
        for record in records:
            unique_id = generate_sortable_id()
            db.execute_sql(
                'UPDATE dikerecord SET unique_id = ? WHERE id = ?',
                (unique_id, record[0])
            )
    else:
        print("All records have unique_ids")

    # Step 3: Make the column non-nullable if it's nullable
    cursor = db.execute_sql("PRAGMA table_info(dikerecord)")
    column_info = [row for row in cursor.fetchall() if row[1] == 'unique_id'][0]
    if column_info[3] == 0:  # notnull is 0 (meaning nullable)
        print("Making unique_id column non-nullable...")
        migrate_fields(
            migrator.add_not_null('dikerecord', 'unique_id'),
        )
    else:
        print("unique_id column is already non-nullable")
    
    # Step 4: Add unique index if it doesn't exist
    if not index_exists(db, 'idx_dikerecord_unique_id'):
        print("Adding unique index...")
        db.execute_sql(
            'CREATE UNIQUE INDEX idx_dikerecord_unique_id ON dikerecord(unique_id)'
        )
    else:
        print("Unique index already exists")

def rollback(db):
    """
    Remove the unique_id column
    """
    # Only attempt to drop if things exist
    if index_exists(db, 'idx_dikerecord_unique_id'):
        print("Dropping unique index...")
        db.execute_sql('DROP INDEX idx_dikerecord_unique_id')
    
    if column_exists(db, 'dikerecord', 'unique_id'):
        print("Dropping unique_id column...")
        migrator = SqliteMigrator(db)
        migrate_fields(
            migrator.drop_column('dikerecord', 'unique_id')
        ) 