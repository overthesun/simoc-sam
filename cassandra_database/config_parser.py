"""
    Testing script for config parsing. This may or may not be moved to use yaml to allow
    for better control and less necessary files for SAM.
"""
import configparser
import datetime

from uuid import uuid4
from cassandra_models import ReadingsBySensor, Sensors, SensorsByLocation
from cassandra.util import uuid_from_time
from logging_config import log


def config_as_dict_to_db():
    config = configparser.ConfigParser()
    config.read_file(open('/sensors.cfg'))
    sensor_dict = {s: dict(config.items(s)) for s in config.sections()}
    log.info('Sucessfully parsed config file')

    for key, val in sensor_dict.items():
        if isinstance(val, dict):
            Sensors.create(
                sensor_id=uuid4(),
                sensor_name=val['sensor_name'],
                sensor_number=val['sensor_number'],
                sensor_type=val['sensor_type'])
            log.info('Sensor row inserted')


def config_to_db():
    config = configparser.ConfigParser()

    with open('/sensors.cfg') as f:
        config.read_file(f)
    for name, section in config.items():
        if name == 'DEFAULT':
            continue
        Sensors.create(
            sensor_id=uuid4(),
            sensor_name=section['sensor_name'],
            sensor_number=section['sensor_number'],
            sensor_type=section['sensor_type'])
        log.info('Sensor row inserted')


def insert_reading_to_db():
    sensor_id = uuid4()
    for _ in range(100):
        time1 = datetime.datetime.now()
        ReadingsBySensor.create(
            sensor_id=sensor_id,
            reading_id=uuid_from_time(time1),
            sensor_name='testsensor1',
            sensor_number='01',
            sensor_type='SCD-30',
            sensor_location='greenhouse')
        log.info('Sensor readings inserted')


def insert_sensor_location_to_db():
    config = configparser.ConfigParser()

    with open('/location.cfg') as fl:
        config.read_file(fl)
    for name, section in config.items():
        if name == 'DEFAULT':
            continue
        SensorsByLocation.create(
            location_id=uuid4(),
            location=section['location_name'],
            sensor_id=uuid4(),
            sensor_name=section['sensor_name'],
            sensor_type=section['sensor_type'])
        log.info('Sensor location inserted')


if __name__ == '__main__':
    log.info('Cannot call')
