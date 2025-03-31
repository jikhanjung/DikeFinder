"""Migration to add is_deleted and last_sync_date columns to DikeRecord table"""
from peewee import *
from playhouse.migrate import SqliteMigrator, migrate as migrate_fields

def migrate(db):
    """Write your migrations here."""
    migrator = SqliteMigrator(db)
    
    # Execute migrations
    migrate_fields(
        migrator.add_column('dikerecord', 'is_deleted',
                           BooleanField(default=False)),
        migrator.add_column('dikerecord', 'last_sync_date',
                           DateTimeField(null=True))
    )


def rollback(db):
    """Write your rollback migrations here."""
    migrator = SqliteMigrator(db)
    
    # Execute rollback
    migrate_fields(
        migrator.drop_column('dikerecord', 'is_deleted'),
        migrator.drop_column('dikerecord', 'last_sync_date')
    ) 