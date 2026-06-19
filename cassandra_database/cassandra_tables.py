"""
    This was the original implementation of creating tables using CQL statements before
    moving to using models and sync_table(). This can most likely be removed or paired down
    to table specific functions such as the drop_tables() one below.
"""
from logging_config import log

import cassandra_connection as cass_db


table_list = ['sensors', 'sensors_by_location', 'readings_by_sensor']

def drop_tables():
    session, cluster = cass_db.cassandra_connection()

    try:
        for table in table_list:
            drop_table = 'DROP TABLE IF EXISTS {table}'.format(table=table)
            log.info('dropping {table} table'.format(table=table))
            session.execute(drop_table)
            log.info('{table} dropped'.format(table=table))
    except Exception as e:
        print(e)
        log.exception(e)

    finally:
        log.info('Terminating connection to cluster')
        session.shutdown()
        cluster.shutdown()


def create_base_tables():
    session, cluster = cass_db.cassandra_connection()

    try:
        for table in table_list:
            drop_table = 'DROP TABLE IF EXISTS {table}'.format(table=table)
            log.info('dropping {table} table'.format(table=table))
            session.execute(drop_table)
            log.info('{table} dropped'.format(table=table))

        create_sensors_table = """
            CREATE TABLE IF NOT EXISTS sensors
                               (sensor_id uuid,
                                sensor_name text,
                                sensor_number text,
                                sensor_type text,
                                PRIMARY KEY ((sensor_id, sensor_name)));
            """
        log.info('Creating sensors table')
        session.execute(create_sensors_table)
        log.info('Successfully created sensors table')

        create_sensors_by_location_table = """
            CREATE TABLE IF NOT EXISTS sensors_by_location
                                           (location_id uuid,
                                           location text,
                                           sensor_id uuid,
                                           sensor_name text,
                                           sensor_type text,
                                           PRIMARY KEY ((location_id, location)));
                """
        log.info('Creating sensors_by_location table')
        session.execute(create_sensors_by_location_table)
        log.info('Successfully created sensors_by_location table')

        create_readings_by_sensor_table = """
            CREATE TABLE IF NOT EXISTS readings_by_sensor
                                          (reading_id uuid,
                                           sensor_id uuid,
                                           sensor_name text,
                                           sensor_number text,
                                           sensor_type text,
                                           sensor_location text,
                                           co2 decimal,
                                           temperature decimal,
                                           humidity decimal,
                                           pressure decimal,
                                           PRIMARY KEY ((sensor_id), reading_id)
                                           )
                                           WITH CLUSTERING ORDER BY (reading_id DESC);
                """
        log.info('Creating readings_by_sensor table')
        session.execute(create_readings_by_sensor_table)
        log.info('Successfully created readings_by_sensor table')

    except Exception as e:
        print(e)
        log.exception(e)

    finally:
        log.info('Terminating connection to cluster')
        session.shutdown()
        cluster.shutdown()


if __name__ == "__main__":
    log.info('Not callable')
