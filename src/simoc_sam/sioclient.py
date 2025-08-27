import os
import csv
import shutil
import asyncio
import datetime

import socketio

from .sensors import utils
from . import config


# default host:port of the sioserver
SIO_HOST, SIO_PORT = config.sio_host, config.sio_port

sio = socketio.AsyncClient()

HAB_INFO = {}
SENSOR_INFO = {}

# default events

@sio.event
async def connect():
    print('Connected to server')
    print('Registering client')
    await sio.emit('register-client')

@sio.event
async def disconnect():
    print('Server disconnected')


# step-data-related events

@sio.on('hab-info')
async def hab_info(data):
    """Handle habitat info sent by the server and request step data."""
    print('Received habitat info:', data)
    HAB_INFO.clear()  # remove old info
    HAB_INFO.update(data)

@sio.on('sensor-info')
async def sensor_info(data):
    """Handle sensor info sent by the server."""
    print('Received sensor info:', data)
    SENSOR_INFO.clear()  # remove old info
    SENSOR_INFO.update(data)

@sio.on('step-batch')
async def step_batch(batch):
    """Handle batches of step data received by the server."""
    #print(f'Received a batch of {len(batch)} bundles from the server:')
    to_csv(batch)
    for bundle in batch:
        for sensor, reading in bundle['readings'].items():
            sensor_info = SENSOR_INFO[sensor]
            print(utils.format_reading(reading, sensor_info=sensor_info))

# csv

fpath = None
FIELDNAMES = ['timestamp']

def to_csv(batch):
    """Update fieldnames in logfile to latest sensor_info and write readings

    Column 1 is timestamp of batch
    Columns after that are <sensor_id>_<reading_label>, e.g. '92U81J_co2'
    """
    # Compile row, update FIELDNAMES
    rows = []
    for bundle in batch:
        row = {'timestamp': bundle['timestamp']}
        for sid, reading in bundle['readings'].items():
            if not SENSOR_INFO[sid]['sensor_id']:
                raise ValueError('sensor_id must be defined for all sensors')
            sensor_id = SENSOR_INFO[sid]['sensor_id']
            for field, value in reading.items():
                if field in {'timestamp', 'n'}:
                    continue
                field_id = f'{sensor_id}_{field}'
                if field_id not in FIELDNAMES:
                    FIELDNAMES.append(field_id)
                row[field_id] = value
        rows.append(row)

    global fpath
    if fpath is None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fpath = f'simoc_log_{timestamp}.csv'

    # Initialize log file w/ headers
    if not os.path.exists(fpath):
        with open(fpath, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

    # Update log file for new columns
    else:
        with open(fpath, 'r') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not set(FIELDNAMES).issubset(fieldnames):
                print('Updating CSV header...')
                with open('temp_output.csv', 'w') as f:
                    fieldnames += [f for f in FIELDNAMES if f not in fieldnames]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in reader:
                        writer.writerow(row)
                shutil.move('temp_output.csv', fpath)

    # Write new readings
    with open(fpath, 'a') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerows(rows)

# main

async def main(host=SIO_HOST, port=SIO_PORT):
    """Connect to the server and register as a client."""
    # connect to the server and wait
    for n in range(10):
        print(f'Connecting to <{host}:{port}>...')
        try:
            await sio.connect(f'http://{host}:{port}')
            await sio.wait()
            break  # after a successful connection
        except socketio.exceptions.ConnectionError as err:
            print(f'Failed to connect (attempt {n+1}): {err}')
            await asyncio.sleep(5)
    else:
        print(f'Giving up after {n+1} attempts')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except asyncio.exceptions.CancelledError:
        print('Client stopped')
