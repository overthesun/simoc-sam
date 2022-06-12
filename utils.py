import re
from datetime import datetime

def format_reading(reading, *, time_fmt='%H:%M:%S', sensor_info=None):
    """Format a sensor reading and return it as a string."""
    r = dict(reading)  # make a copy
    n = r.pop('n')
    dt = datetime.strptime(r.pop('timestamp'), '%Y-%m-%d %H:%M:%S.%f')
    timestamp = dt.strftime(time_fmt)
    sensor_name = sensor_info['sensor_name'] if sensor_info else '-'
    reading_info = sensor_info['reading_info'] if sensor_info else None
    result = []
    for key, value in r.items():
        v = f'{value:.2f}' if isinstance(value, float) else str(value)
        label, unit = key, ''
        if reading_info:
            label = reading_info[key]['label']
            unit = ' ' + reading_info[key]['unit']
        result.append(f'{label}: {v}{unit}')
    return f'{sensor_name}|{timestamp}|{n:<3}  {"; ".join(result)}'

def alphanum(string):
    """Return a string with non-alphanumeric characters removed"""
    return re.sub(r'[^a-zA-Z0-9]', '', string)

def format_sensor_id(location, sensor_type, sensor_name):
    return f'{location}_{sensor_type}_{sensor_name}'

def get_sensor_id(sensor_info, active_sensors=[], serial_length=-1):
    """Return a unique, non-random id for each location/type/device"""

    # The location is a unique identifier for the device where the class
    # instance of the sensor is running (e.g. a Raspberry Pi), and should be
    # descriptive (e.g. 'greenhouse').
    location = alphanum(sensor_info.get('location') or 'loc0')
    # Hardcoded into the class instance.
    sensor_type = alphanum(sensor_info.get('sensor_type', 'sensor0'))
    # The sensor name is a unique identifier for the sensor itself, in case two
    # sensors of the same type are connected at the same location.
    serial_number = sensor_info.get('serial_number', None)
    if serial_number is not None:
        serial_number = alphanum(serial_number)[:serial_length]
    else:
        serial_number = 0
        while True:
            id = format_sensor_id(location, sensor_type, serial_number)
            if id not in active_sensors:
                break
            else:
                serial_number += 1
    return format_sensor_id(location, sensor_type, serial_number)
