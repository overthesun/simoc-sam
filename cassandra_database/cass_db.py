from config_parser import (config_to_db, insert_reading_to_db,
                           insert_sensor_location_to_db)
from logging_config import log
from yaml_parser import get_sensors_from_yaml
from cassandra_models import sync_all_tables
import cassandra_tables as cass_tables


# Need to transform this into a testing suite
def main():
    #cass_tables.create_base_tables()
    #log.info('Base tables created')
    cass_tables.drop_tables()
    sync_all_tables()
    log.info('All tables synced from Cassandra models')
    get_sensors_from_yaml()
    log.info('Sensor config file read and imported into database')
    insert_reading_to_db()
    

if __name__ == "__main__":
    main()
