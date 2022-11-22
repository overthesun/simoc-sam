import sys
import asyncio

import socketio

from .sensors import utils


# default host:port of the sioserver
SIO_HOST, SIO_PORT = utils.get_sioserver_addr()

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
    print(f'Received a batch of {len(batch)} bundles from the server:')
    for bundle in batch:
        for sensor, reading in bundle['readings'].items():
            sensor_info = SENSOR_INFO[sensor]
            print(utils.format_reading(reading, sensor_info=sensor_info))

# main

async def main(host=SIO_HOST, port=SIO_PORT):
    """Connect to the server and register as a client."""
    # connect to the server and wait
    await sio.connect(f'http://{host}:{port}')
    await sio.wait()


if __name__ == '__main__':
    parser = utils.get_addr_argparser()
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
