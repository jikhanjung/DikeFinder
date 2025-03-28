from peewee import *
from playhouse.migrate import SqliteMigrator, migrate as migrate_fields
import datetime

def migrate(db):
    """Apply the migration"""
    migrator = SqliteMigrator(db)
    
    # Check if columns exist before adding them
    cursor = db.execute_sql("PRAGMA table_info(dikerecord)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    operations = []
    if 'memo' not in existing_columns:
        operations.append(
            migrator.add_column('dikerecord', 'memo', TextField(null=True))
        )
    
    if 'modified_date' not in existing_columns:
        operations.append(
            migrator.add_column('dikerecord', 'modified_date', 
                              DateTimeField(default=datetime.datetime.now))
        )
    
    if operations:
        migrate_fields(*operations)
        
        # Update existing records to set modified_date
        db.execute_sql(
            "UPDATE dikerecord SET modified_date = ? WHERE modified_date IS NULL",
            (datetime.datetime.now(),)
        )

def rollback(db):
    """Rollback the migration"""
    migrator = SqliteMigrator(db)
    
    migrate_fields(
        migrator.drop_column('dikerecord', 'memo'),
        migrator.drop_column('dikerecord', 'modified_date')
    )
    
    # Drop sync tables
    db.drop_tables([SyncEventRecord, SyncEvent]) 