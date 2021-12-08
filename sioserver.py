import asyncio
import random

import socketio

from aiohttp import web

HAB_INFO = dict(humans=4, volume=272)
SENSORS = set()
CLIENTS = set()
SUBSCRIBERS = set()

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

# default events

@sio.event
def connect(sid, environ):
    print('CONNECTED:', sid)

@sio.event
def disconnect(sid):
    print('DISCONNECTED:', sid)
    if sid in SUBSCRIBERS:
        print('Removing disconnected client:', sid)
        SUBSCRIBERS.remove(sid)
    # remove the sid from the other groups if present
    CLIENTS.discard(sid)
    SENSORS.discard(sid)


# new clients events

@sio.on('register-sensor')
async def register_sensor(sid):
    """Handle new sensors and request sensor data."""
    print('New sensor connected:', sid)
    SENSORS.add(sid)
    print('Requesting sensor data from', sid)
    # request data from the sensor
    await sio.emit('send-data', to=sid)

@sio.on('register-client')
async def register_client(sid):
    """Handle new clients and send habitat info."""
    print('New client connected:', sid)
    CLIENTS.add(sid)
    print('Sending client habitat info:', HAB_INFO)
    await sio.emit('hab-info', HAB_INFO, to=sid)


# data-related events

@sio.on('send-step-data')
async def send_step_data(sid):
    """Handle client requests to send step data."""
    print('Start sending step data to', sid)
    SUBSCRIBERS.add(sid)

@sio.on('sensor-batch')
async def sensor_batch(sid, batch):
    """Handle batches of sensor data and broadcast them to the clients."""
    print(f'Received a batch of {len(batch)} readings from sensor {sid}:')
    for step in batch:
        print('  {step_num}: CO2: {co2_ppm:6.0f}ppm; Temperature: {temp:2.2f}°; '
              'Humidity: {hum_perc:2.2}%'.format_map(step))
    if SUBSCRIBERS:
        # TODO: set up a room for the clients and broadcast to the room
        print(f'Broadcasting step data batch to {len(SUBSCRIBERS)} clients')
        for client_id in SUBSCRIBERS:
            await sio.emit('step-batch', batch, to=client_id)


# test events (obsolete)

@sio.event
async def msg(sid, data):
    print('msg:', data)
    await sio.emit('log', f'Server received: {data}')

@sio.event
async def get_data(sid, n):
    print('get_data:', n)
    for x in range(int(n)):
        data =  f'Random num {x+1}: {random.randint(1, 10000)}'
        await sio.emit('send_data', data)
        await asyncio.sleep(1)


#app.router.add_static('/static', 'static')
app.router.add_get('/', index)

if __name__ == '__main__':
    web.run_app(app)
