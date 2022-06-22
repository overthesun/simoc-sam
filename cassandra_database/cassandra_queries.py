from uuid import uuid4
from logging_config import log

import cassandra_connection as cass_db


def insert_sensor_data(sensor_name, sensor_number, sensor_type):
    session, cluster = cass_db.cassandra_connection()
    log.info('session successfully connected')

    insert_sensor = session.prepare("""
        INSERT INTO sensors (sensor_id,
                             sensor_name,
                             sensor_number,
                             sensor_type)
        VALUES (?, ?, ?, ?)
    """)

    session.execute(
        insert_sensor,
        (uuid4(), sensor_name, sensor_number, sensor_type))

    session.shutdown()
    cluster.shutdown()


def insert_sensor_by_location(location, sensor_id, sensor_name, sensor_type):
    session, cluster = cass_db.cassandra_connection()

    insert_sensor_by_location = session.prepare("""
        INSERT INTO sensor_by_location(location_id,
                                       location,
                                       sensor_id,
                                       sensor_name,
                                       sensor_type)
        VALUES (?, ?, ?, ?, ?)
    """)

    session.execute(
        insert_sensor_by_location,
        (uuid4(), location, sensor_id, sensor_name, sensor_type)
    )

    session.shutdown()
    cluster.shutdown()
