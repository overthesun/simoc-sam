import sys
import asyncio

import socketio

from utils import format_reading


sio = socketio.AsyncClient()
client_nsp = socketio.AsyncClientNamespace('/client')

# default events

@sio.event
async def connect():
    print('Connected to server')
    print('Registering client')
    await client_nsp.emit('register-client')

@sio.event
async def disconnect():
    print('Server disconnected')


# step-data-related events

@sio.on('hab-info', namespace='/client')
async def on_hab_info(data):
    """Handle habitat info sent by the server and request step data."""
    print('Received habitat info:', data)
    print('Requesting step data')
    await client_nsp.emit('send-step-data')

@sio.on('step-batch', namespace='/client')
async def on_step_batch(batch):
    """Handle batches of step data received by the server."""
    print(f'Received a batch of {len(batch)} readings from the server:')
    for reading in batch:
        print(format_reading(reading))

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
    sio.register_namespace(client_nsp)
    await sio.connect(f'http://localhost:{port}')
    await sio.wait()


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(port))
