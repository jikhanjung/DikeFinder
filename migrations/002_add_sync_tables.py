from peewee import *
from playhouse.migrate import SqliteMigrator, migrate as migrate_fields
import datetime

def migrate(db):
    """
    Add SyncEvent and SyncEventRecord tables for server synchronization
    """
    # Create SyncEvent table
    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS syncevent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id VARCHAR(255) UNIQUE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(50),
            error_message TEXT
        )
    """)
    
    # Create SyncEventRecord table with foreign keys
    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS synceventrecord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_event_id INTEGER,
            dike_record_id INTEGER,
            sync_result VARCHAR(50),
            result_message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sync_event_id) REFERENCES syncevent (id),
            FOREIGN KEY (dike_record_id) REFERENCES dikerecord (id)
        )
    """)
    
    # Create index for the unique constraint on sync_event and dike_record
    db.execute_sql("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_event_record 
        ON synceventrecord (sync_event_id, dike_record_id)
    """)

def rollback(db):
    """
    Remove the sync tables
    """
    db.execute_sql("DROP TABLE IF EXISTS synceventrecord")
    db.execute_sql("DROP TABLE IF EXISTS syncevent") 