import os
import datetime
from peewee import *
from playhouse.sqlite_ext import SqliteExtDatabase
from migrations.migration_manager import apply_migrations

# Get the directory of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Default database path
DB_PATH = os.path.join(SCRIPT_DIR, 'dikemapper.db')

# Initialize the database with SQLite
db = SqliteDatabase(None)  # Initialize without path

class BaseModel(Model):
    class Meta:
        database = db

class DikeRecord(BaseModel):
    symbol = CharField(null=True)
    stratum = CharField(null=True)
    rock_type = CharField(null=True)
    era = CharField(null=True)
    map_sheet = CharField(null=True)
    address = CharField(null=True)
    distance = FloatField(null=True)
    angle = FloatField(null=True)
    x_coord_1 = FloatField(null=True)
    y_coord_1 = FloatField(null=True)
    lat_1 = FloatField(null=True)
    lng_1 = FloatField(null=True)
    x_coord_2 = FloatField(null=True)
    y_coord_2 = FloatField(null=True)
    lat_2 = FloatField(null=True)
    lng_2 = FloatField(null=True)
    memo = TextField(null=True)
    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(default=datetime.datetime.now)

class SyncEvent(BaseModel):
    event_id = CharField(unique=True)  # Server-provided sync event ID
    timestamp = DateTimeField(default=datetime.datetime.now)
    status = CharField()  # 'pending', 'in_progress', 'completed', 'failed'
    error_message = TextField(null=True)  # Store any error information

class SyncEventRecord(BaseModel):
    sync_event = ForeignKeyField(SyncEvent, backref='records')
    dike_record = ForeignKeyField(DikeRecord, backref='sync_events')
    sync_result = CharField()  # 'success', 'failed', 'skipped', etc.
    result_message = TextField(null=True)  # Details about success/failure
    timestamp = DateTimeField(default=datetime.datetime.now)

    class Meta:
        # Ensure each record appears only once per sync event
        indexes = (
            (('sync_event', 'dike_record'), True),
        )

def init_database(custom_path=None):
    """Initialize the database and create tables
    
    Args:
        custom_path (str, optional): Custom path for the database file. 
                                   If None, uses the default path.
    """
    global DB_PATH
    
    # Update DB_PATH if custom path is provided
    if custom_path:
        DB_PATH = custom_path
    
    # Initialize database with the path
    db.init(DB_PATH)
    db.connect()
    
    try:
        # Let the migration system handle everything
        print("Checking database schema and applying migrations...")
        apply_migrations(db)
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        raise
    finally:
        db.close()

def get_db():
    """Get the database instance"""
    return db 