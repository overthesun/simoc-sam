import yaml

from uuid import uuid4
from cassandra_models import SensorsByLocation
from logging_config import log


def get_sensors_from_yaml():
    with open('/config.yaml', 'r') as f:
        data = yaml.safe_load(f)

    for _, section in data['sensors'].items():
        SensorsByLocation.create(
            location_id=uuid4(),
            location=section['location'],
            sensor_id=uuid4(),
            sensor_name=section['sensor_name'],
            sensor_type=section['sensor_type'])
    
    log.info('Sensor locations inserted')


if __name__ == '__main__':
    log.info('Cannot call')
