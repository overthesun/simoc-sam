import asyncio
import random

import socketio

from aiohttp import web

from utils import format_reading


HAB_INFO = dict(humans=4, volume=272)
SENSOR_INFO = dict()
SENSORS = set()
CLIENTS = set()
SUBSCRIBERS = set()

sio = socketio.AsyncServer(
        cors_allowed_origins=['http://localhost:8080','http://localhost:8081'])
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
async def register_sensor(sid, sensor_info):
    """Handle new sensors and request sensor data."""
    print('New sensor connected:', sid)
    print('Sensor info:', sensor_info)
    SENSORS.add(sid)
    SENSOR_INFO[sid] = sensor_info
    # TODO: send sensor-info to clients when a new
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
    sensor_info = SENSOR_INFO[sid]
    for reading in batch:
        print(format_reading(reading, sensor_info=sensor_info))
    if SUBSCRIBERS:
        # TODO: set up a room for the clients and broadcast to the room
        print(f'Broadcasting step data batch to {len(SUBSCRIBERS)} clients')
        for client_id in SUBSCRIBERS:
            await sio.emit('step-batch', batch, to=client_id)

@sio.on('sensor-reading')
async def sensor_reading(sid, reading):
    """Get a single sensor reading and add it to SENSOR_READINGS."""
    #print(f'Received a reading from sensor {sid}:')
    SENSOR_READINGS[sid].append(reading)
    sensor_info = SENSOR_INFO[sid]
    print(format_reading(reading, sensor_info=sensor_info))



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


#app.router.add_static('/static', 'static')
app.router.add_get('/', index)

if __name__ == '__main__':
    web.run_app(app)
