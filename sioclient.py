import sys
import asyncio

import socketio

from utils import format_reading


sio = socketio.AsyncClient()
client_ns = socketio.AsyncClientNamespace('/client')

SENSOR_INFO = {}


# default events

@sio.event
async def connect():
    print('Connected to server')
    print('Registering client')
    sio.register_namespace(client_ns)
    await client_ns.emit('register-client')

@sio.event
async def disconnect():
    print('Server disconnected')


# step-data-related events

@sio.on('hab-info', namespace='/client')
async def hab_info(data):
    """Handle habitat info sent by the server and request step data."""
    print('Received habitat info:', data)
    print('Requesting step data')
    await client_ns.emit('send-step-data')

@sio.on('sensor-info', namespace='/client')
async def sensor_info(data):
    """Handle sensor info sent by the server."""
    print('Received sensor info:', data)
    SENSOR_INFO.update(data)

@sio.on('step-batch', namespace='/client')
async def step_batch(batch):
    """Handle batches of step data received by the server."""
    print(f'Received a batch of {len(batch)} readings from the server:')
    # TODO get info from the right sensor
    sensor_info = list(SENSOR_INFO.values())[0]
    for reading in batch:
        print(format_reading(reading, sensor_info=sensor_info))

@sio.on('message', namespace='/client')
async def on_message(msg):
    """"Test message function"""
    print(f'Received message: {str(msg)}')

# main

async def main(port=None):
    """Connect to the server and register as a client."""
    if port is None:
        port = '5000'
    # connect to the server and wait
    await sio.connect(f'http://localhost:{port}', namespaces=['/client', '/'])
    await sio.wait()


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(port))
