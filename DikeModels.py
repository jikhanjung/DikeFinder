import os
import datetime
from peewee import *
from playhouse.sqlite_ext import SqliteExtDatabase

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
    created_date = DateTimeField(default=datetime.datetime.now)

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
    
    # Create tables
    db.connect()
    db.create_tables([DikeRecord], safe=True)
    db.close()

def get_db():
    """Get the database instance"""
    return db 