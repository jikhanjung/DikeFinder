"""Migration to remove SyncEventRecord and update SyncEvent with new fields"""
from peewee import *
from playhouse.migrate import SqliteMigrator, migrate as migrate_fields

def migrate(db):
    """Write your migrations here."""
    migrator = SqliteMigrator(db)
    
    # Drop the SyncEventRecord table
    db.execute_sql('DROP TABLE IF EXISTS synceventrecord;')
    
    # Add new columns to SyncEvent
    migrate_fields(
        migrator.add_column('syncevent', 'total_records',
                           IntegerField(null=True)),
        migrator.add_column('syncevent', 'success_count',
                           IntegerField(default=0)),
        migrator.add_column('syncevent', 'fail_count',
                           IntegerField(default=0)),
        migrator.add_column('syncevent', 'details',
                           TextField(null=True)),
        migrator.add_column('syncevent', 'end_timestamp',
                           DateTimeField(null=True))
    )


def rollback(db):
    """Write your rollback migrations here."""
    migrator = SqliteMigrator(db)
    
    # Remove new columns from SyncEvent
    migrate_fields(
        migrator.drop_column('syncevent', 'total_records'),
        migrator.drop_column('syncevent', 'success_count'),
        migrator.drop_column('syncevent', 'fail_count'),
        migrator.drop_column('syncevent', 'details'),
        migrator.drop_column('syncevent', 'end_timestamp')
    )
    
    # Note: We don't recreate the SyncEventRecord table in rollback
    # as it would require recreating all the data which is not possible 