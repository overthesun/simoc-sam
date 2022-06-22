import os
from uuid import uuid4, uuid1

from cassandra.cqlengine import columns
from cassandra.cqlengine import ValidationError
from cassandra.cqlengine.connection import register_connection, set_default_connection
from cassandra.cqlengine.management import sync_table
from cassandra.cqlengine.models import Model

from dotenv import load_dotenv

from cassandra_connection import cassandra_connection

load_dotenv()

KEYSPACE = os.getenv('CASSANDRA_KEYSPACE')

# Workaround for potential bug that may/may not have been addressed
_session, _ = cassandra_connection()
register_connection(str(_session), session=_session)
set_default_connection(str(_session))

"""
    All models below can be extended with validate() that can check for type insertion on
    fields. ValidationError raised if data checks fail
"""
class Sensors(Model):
    __keyspace__ = KEYSPACE
    session = _session
    sensor_id = columns.UUID(primary_key=True, default=uuid4)
    sensor_name = columns.Text(primary_key=True)
    sensor_number = columns.Text()
    sensor_type = columns.Text()

    def validate(self):
        super(Sensors, self).validate()
        if self.sensor_id is not type(uuid4):
            raise ValidationError('SensorID is not valid UUID4')


class SensorsByLocation(Model):
    __keyspace__ = KEYSPACE
    session = _session
    location_id = columns.UUID(primary_key=True, default=uuid4)
    location = columns.Text(primary_key=True)
    sensor_id = columns.UUID()
    sensor_name = columns.Text()
    sensor_type = columns.Text()

    def validate(self):
        super(SensorsByLocation, self).validate()
        if self.sensor_id is not type(uuid4):
            raise ValidationError('SensorID is not valid UUID4')
        if self.location_id is not type(uuid4):
            raise ValidationError('LocationID is not valid UUID4')


class ReadingsBySensor(Model):
    __keyspace__ = KEYSPACE
    session = _session
    sensor_id = columns.UUID(primary_key=True, default=uuid4)
    reading_id = columns.TimeUUID(primary_key=True, clustering_order="DESC")
    sensor_name = columns.Text()
    sensor_number = columns.Text()
    sensor_type = columns.Text()
    sensor_location = columns.Text()
    co2 = columns.Decimal()
    temperature = columns.Decimal()
    humidity = columns.Decimal()
    pressure = columns.Decimal()

    def validate(self):
        super(ReadingsBySensor, self).validate()
        if self.sensor_id is not type(uuid4):
            raise ValidationError('SensorID is not valid UUID4')
        if self.reading_id is not type(uuid1):
            raise ValidationError('ReadingID is not valid UUID1(Time)')
        

def sync_all_tables():
    _session, _ = cassandra_connection()
    register_connection(str(_session), session=_session)
    set_default_connection(str(_session))

    sync_table(Sensors)
    sync_table(SensorsByLocation)
    sync_table(ReadingsBySensor)