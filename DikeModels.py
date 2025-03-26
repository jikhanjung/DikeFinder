import os
import datetime
from peewee import *
from playhouse.sqlite_ext import SqliteExtDatabase

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'geological_data.db')

# Initialize the database
db = SqliteExtDatabase(DB_PATH)

class BaseModel(Model):
    class Meta:
        database = db

class GeologicalRecord(BaseModel):
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

def init_database():
    """Initialize the database and create tables"""
    db.connect()
    db.create_tables([GeologicalRecord], safe=True)
    db.close()

def get_db():
    """Get the database instance"""
    return db 