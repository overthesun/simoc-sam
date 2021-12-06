import sys
import asyncio

import socketio

sio = socketio.AsyncClient()


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
    print('Requesting step data')
    await sio.emit('send-step-data')

@sio.on('step-batch')
async def step_batch(batch):
    """Handle batches of step data received by the server."""
    print(f'Received a batch of {len(batch)} step from the server:')
    for step in batch:
        print('  {step_num}: CO2: {co2_ppm:4}ppm; Temperature: {temp:2.1f}°; '
              'Humidity: {hum_perc:2}%'.format_map(step))

# main

async def main(port=None):
    """Connect to the server and register as a client."""
    if port is None:
        port = '5000'
    # connect to the server and wait
    await sio.connect(f'http://localhost:{port}')
    await sio.wait()


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(port))
