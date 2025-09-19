import json
import copy
import socket
import asyncio
import ipaddress
import traceback

from datetime import datetime
from collections import defaultdict, deque

import aiomqtt
import socketio
import netifaces

from aiohttp import web

from .sensors import utils
from . import config


# default host:port of the server
SIO_HOST, SIO_PORT = config.sio_host, config.sio_port
# default host:port of the MQTT broker
MQTT_HOST, MQTT_PORT = config.mqtt_host, config.mqtt_port

def convert_sensor_data():
    info = {}
    for name, data in utils.SENSOR_DATA.items():
        info[name] = {
            'sensor_type': data.name,
            'sensor_name': None,
            'sensor_id': None,
            'sensor_desc': None,
            'reading_info': data.data,
        }
    return info

HAB_INFO = dict(humans=config.humans, volume=config.volume)
SENSOR_DATA = convert_sensor_data()
SENSOR_INFO = {}
SENSOR_READINGS = defaultdict(lambda: deque(maxlen=10))
SENSORS = set()
CLIENTS = set()
SUBSCRIBERS = set()


def get_host_ips():
    """Return a list of IPs and hostnames for the current host."""
    hostname = socket.gethostname()
    ips = {hostname, 'localhost', '127.0.0.1'}  # init with known IPs/hostnames
    # find all local private networks we are in and our IP in those networks
    for interface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
        for addr in addrs:
            ip = addr.get('addr')
            if ip and ipaddress.ip_address(ip).is_private:
                ips.add(ip)  # only add IPs in the private range
    return ips

# Use dynamic CORS settings for hosts to avoid CORS issues.
# This is mostly needed for SIMOC web since the sensors and Python
# clients don't send the Origin header and no CORS validation happens.
# When SIMOC web is running on the local machine, it can be reached
# through a browser both from the local machine itself or from any
# other machine in any of the networks this machine is in by using
# the IP or hostname that the local machine has on those networks.
# Since the browser will send the IP/hostname used to connect to this
# machine through the Origin header (which is used for CORS validation),
# the value might be different depending on where the browser is running
# (it could be localhost or 127.0.0.1 if it's on the same machine,
# or 192.168.0.1, 10.0.0.1, etc. if it's connecting to this machine
# from another device in one of the other private networks).
# Therefore we need to find all the IPs/hostnames that point to
# this machine in the different networks and explicitly allow them.
# The port is also used for CORS validation, and must match the
# port used by SIMOC web (8080 is used by default).
port = config.simoc_web_port
allowed_origins = [f'http://{ip}' for ip in get_host_ips()]
print("Allowed origins:", allowed_origins)
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


# new clients events

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

def get_timestamp():
    """Return the current timestamp as a string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

async def emit_to_subscribers(*args, **kwargs):
    # TODO: replace with a namespace
    # Iterate on a copy to avoid size changes
    # caused by other threads adding/removing subs
    for client_id in SUBSCRIBERS.copy():
        await sio.emit(*args, to=client_id, **kwargs)


# main loop that broadcasts bundles

async def emit_readings():
    """Emit a bundle with the latest reading of all sensors."""
    args = utils.parse_args()  # TODO: create separate parser for the server
    delay = args.delay
    print(f'Broadcasting data every {delay} seconds.')
    n = 0
    while True:
        # TODO: set up a room for the clients and broadcast to the room
        # TODO: improve ctrl+c handling (see graceful shutdown)
        timestamp = get_timestamp()
        print('Last readings:',
              {k: [v[-1]['n'], v[-1]['timestamp']]
               for k, v in SENSOR_READINGS.items()})
        sensors_readings = {sid: readings[-1]
                            for sid, readings in SENSOR_READINGS.items()
                            if readings}
        bundle = dict(n=n, timestamp=timestamp, readings=sensors_readings)
        # print(bundle)
        try:
            # the frontend expects a list of bundles
            await emit_to_subscribers('step-batch', [bundle])
            n += 1
            print(f'{len(SENSORS)} sensor(s); {len(SUBSCRIBERS)} '
                    f'subscriber(s); {n} readings broadcasted')
        except Exception as e:
            print('!!! Failed to emit step-batch:')
            traceback.print_exc()
        await sio.sleep(delay)


async def mqtt_handler():
    args = utils.parse_args()
    mqtt_broker = args.host or MQTT_HOST
    topic_sub = args.mqtt_topic_sub or config.mqtt_topic_sub
    print(SENSOR_INFO)
    interval = config.mqtt_reconnect_delay
    while True:
        try:
            # the client is supposed to be reusable, so it should be possible
            # to instantiate it outside of the loop, but that doesn't work
            print(f'* Connecting to <{mqtt_broker}>...')
            client = aiomqtt.Client(mqtt_broker)
            async with client:
                await client.subscribe(topic_sub)
                print(f'* Connected to <{mqtt_broker}>, '
                      f'subscribed to <{topic_sub}>.')
                async for message in client.messages:
                    topic = message.topic.value
                    print(topic)
                    location, host, sensor = topic.split('/')
                    sensor_id = f'{host}.{sensor}'
                    if sensor_id not in SENSOR_INFO:
                        SENSORS.add(sensor_id)
                        info = copy.deepcopy(SENSOR_DATA[sensor])
                        info['sensor_name'] = sensor_id
                        info['sensor_id'] = sensor_id
                        info['sensor_desc'] = f'{sensor} sensor on {host}'
                        SENSOR_INFO[sensor_id] = info
                        await emit_to_subscribers('sensor-info', SENSOR_INFO)

                    payload = json.loads(message.payload.decode())
                    # print('adding', payload)
                    SENSOR_READINGS[sensor_id].append(payload)
        except aiomqtt.MqttError as err:
            print(f'* Connection lost from <{mqtt_broker}>; {err}')
            print(f'* Reconnecting in {interval} seconds...')
            await asyncio.sleep(interval)


# app setup

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

def create_app():
    app = web.Application()
    # app.router.add_static('/static', 'static')
    # app.router.add_get('/', index)
    return app

async def init_app(app):
    # Start the MQTT handler in the background
    sio.attach(app)
    sio.start_background_task(emit_readings)
    asyncio.ensure_future(mqtt_handler())
    return app


if __name__ == '__main__':
    app = create_app()
    web.run_app(init_app(app), port=SIO_PORT)
