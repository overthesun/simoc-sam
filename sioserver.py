import asyncio
import random

from datetime import datetime
from collections import defaultdict, deque

import socketio

from aiohttp import web

from utils import format_reading


HAB_INFO = dict(humans=4, volume=272)
SENSOR_INFO = dict()
SENSOR_READINGS = defaultdict(lambda: deque(maxlen=10))
SENSORS = set()
CLIENTS = set()
SUBSCRIBERS = set()

# TODO: add non-localhost origin for deployed setup or find a better fix
allowed_origins = ['http://localhost:8080', 'http://localhost:8081']
sio = socketio.AsyncServer(cors_allowed_origins=allowed_origins,
                           async_mode='aiohttp')


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
    if sid in SENSORS:
        SENSORS.remove(sid)
        del SENSOR_READINGS[sid]


# new clients events

@sio.on('register-sensor')
async def register_sensor(sid, sensor_info):
    """Handle new sensors and request sensor data."""
    print('New sensor connected:', sid)
    print('Sensor info:', sensor_info)
    SENSORS.add(sid)
    SENSOR_INFO[sid] = sensor_info
    await emit_to_subscribers('sensor-info', SENSOR_INFO)
    # sensor is added once we set up a room
    print('Requesting sensor data from', sid)
    # request data from the sensor
    await sio.emit('send-data', to=sid)

@sio.on('register-client')
async def register_client(sid):
    """Handle new clients and send habitat info."""
    print('New client connected:', sid)
    CLIENTS.add(sid)
    print('Sending habitat info to client:', HAB_INFO)
    await sio.emit('hab-info', HAB_INFO, to=sid)
    print('Sending sensor info to client:', SENSOR_INFO)
    await sio.emit('sensor-info', SENSOR_INFO, to=sid)
    print(f'Adding {sid!r} to subscribers')
    SUBSCRIBERS.add(sid)


# data-related events

async def emit_to_subscribers(*args, **kwargs):
    # TODO: replace with a namespace
    for client_id in SUBSCRIBERS:
        await sio.emit(*args, to=client_id, **kwargs)

@sio.on('sensor-batch')
async def sensor_batch(sid, batch):
    """Get a batch of readings and it to SENSOR_READINGS."""
    #print(f'Received a batch of {len(batch)} readings from sensor {sid}:')
    SENSOR_READINGS[sid].extend(batch)
    sensor_info = SENSOR_INFO[sid]
    for reading in batch:
        print(format_reading(reading, sensor_info=sensor_info))

@sio.on('sensor-reading')
async def sensor_reading(sid, reading):
    """Get a single sensor reading and add it to SENSOR_READINGS."""
    #print(f'Received a reading from sensor {sid}:')
    SENSOR_READINGS[sid].append(reading)
    sensor_info = SENSOR_INFO[sid]
    print(format_reading(reading, sensor_info=sensor_info))

def get_timestamp():
    """Return the current timestamp as a string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')



# test events (obsolete)

@sio.event
async def msg(sid, data):
    print('msg:', data)
    await sio.emit('log', f'Server received: {data}')

@sio.event
async def get_data(sid, n):
    print('get_data:', n)
    for x in range(int(n)):
        data = f'Random num {x+1}: {random.randint(1, 10000)}'
        await sio.emit('send_data', data)
        await asyncio.sleep(1)


# main loop that broadcasts bundles

async def emit_readings():
    """Emit a bundle with the latest reading of all sensors."""
    n = 0
    while True:
        if SENSORS and SUBSCRIBERS:
            # TODO: set up a room for the clients and broadcast to the room
            # TODO: improve ctrl+c handling
            print(f'Broadcasting reading to {len(SUBSCRIBERS)} clients')
            timestamp = get_timestamp()
            sensors_readings = {sid: readings[-1]
                                for sid, readings in SENSOR_READINGS.items()}
            bundle = dict(n=n, timestamp=timestamp, readings=sensors_readings)
            # the frontend expects a list of bundles
            await emit_to_subscribers('step-batch', [bundle])
            n += 1
        await sio.sleep(1)


# app setup

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

def create_app():
    app = web.Application()
    # app.router.add_static('/static', 'static')
    app.router.add_get('/', index)
    return app

async def init_app(app):
    sio.attach(app)
    sio.start_background_task(emit_readings)
    return app


if __name__ == '__main__':
    app = create_app()
    web.run_app(init_app(app))
