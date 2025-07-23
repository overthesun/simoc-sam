import socket
import traceback
import ipaddress
import configparser

from datetime import datetime
from collections import defaultdict, deque

import socketio
import netifaces

from aiohttp import web

from .sensors import utils


class BaseServer:
    """Base class for sensor data servers (SocketIO and MQTT bridge)"""
    # This class handles data exchange between the sensors and the clients.
    # The communication with the client (usually SIMOC web) always happens
    # through SocketIO.  The communication with the sensors generally
    # happens through MQTT (when the MQTTWrapper and the MQTT bridge are
    # used)but could also happen through SocketIO (when the SIOWrapper
    # and SIO server are used).

    def __init__(self, port=8081):
        self.port = port
        self.hab_info = dict(humans=4, volume=272)
        self.sensor_info = {}
        self.sensor_readings = defaultdict(lambda: deque(maxlen=10))
        self.sensors = set()
        self.sensor_managers = set()
        self.clients = set()
        self.subscribers = set()

        # Initialize SocketIO server with appropriate CORS settings
        self.sio = self.create_sio_server()
        self.setup_sio_events()

    def get_host_ips(self):
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

    def create_sio_server(self):
        """Create SocketIO server with dynamic CORS settings."""
        # Use dynamic CORS settings to avoid CORS issues
        # The origin is sent by the web client with the Origin header and
        # will correspond to one of the IPs or hostnames of this machine
        # (e.g. localhost:8080, sambridge:8080, 10.0.0.100:8080).
        # Therefore we need to find and explicitly allow all these IPs,
        # as long as they are in the same (private) network.
        # The sensors and the Python client don't send the Origin header,
        # and they work without being allowed explicitly.
        allowed_origins = [f'http://{ip}:8080' for ip in self.get_host_ips()]
        print("Allowed origins:", allowed_origins)
        return socketio.AsyncServer(cors_allowed_origins=allowed_origins,
                                   async_mode='aiohttp')

    def get_sensor_info_from_cfg(self, sensor_id, cfg_file='config.cfg'):
        """Get sensor information from configuration file."""
        config = configparser.ConfigParser()
        config.read(cfg_file)
        for name, section in config.items():
            if name.lower() == sensor_id.lower():
                return dict(section)

    def setup_sio_events(self):
        """Set up basic SocketIO event handlers."""

        @self.sio.event
        def connect(sid, environ):
            print('CONNECTED:', sid)

        @self.sio.event
        def disconnect(sid):
            print('DISCONNECTED:', sid)
            if sid in self.subscribers:
                print('Removing disconnected client:', sid)
                self.subscribers.remove(sid)
            self.clients.discard(sid)

        @self.sio.on('register-client')
        async def register_client(sid):
            """Handle new clients and send habitat info."""
            print('New client connected:', sid)
            self.clients.add(sid)
            print('Sending habitat info to client:', self.hab_info)
            await self.sio.emit('hab-info', self.hab_info, to=sid)
            print('Sending sensor info to client:', self.sensor_info)
            await self.sio.emit('sensor-info', self.sensor_info, to=sid)
            print(f'Adding {sid!r} to subscribers')
            self.subscribers.add(sid)

    async def emit_to_subscribers(self, *args, **kwargs):
        """Emit data to all subscribers."""
        # TODO: replace with a namespace
        # Iterate on a copy to avoid size changes
        # caused by other threads adding/removing subs
        for client_id in self.subscribers.copy():
            await self.sio.emit(*args, to=client_id, **kwargs)

    def get_timestamp(self):
        """Return the current timestamp as a string."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    async def emit_readings(self):
        """Emit a bundle with the latest reading of all sensors."""
        args = utils.parse_args()  # TODO: create separate parser for the server
        delay = args.delay
        print(f'Broadcasting data every {delay} seconds.')
        n = 0
        while True:
            if self.sensors and self.subscribers:
                # TODO: set up a room for the clients and broadcast to the room
                # TODO: improve ctrl+c handling (see graceful shutdown)
                timestamp = self.get_timestamp()
                print('Last readings:',
                      {k: [v[-1]['n'], v[-1]['timestamp']]
                       for k, v in self.sensor_readings.items()})
                sensors_readings = {sid: readings[-1]
                                    for sid, readings in self.sensor_readings.items()
                                    if readings}
                bundle = dict(n=n, timestamp=timestamp, readings=sensors_readings)
                try:
                    # the frontend expects a list of bundles
                    await self.emit_to_subscribers('step-batch', [bundle])
                    n += 1
                    print(f'{len(self.sensors)} sensor(s); {len(self.subscribers)} '
                        f'subscriber(s); {n} readings broadcasted')
                except Exception as e:
                    print('!!! Failed to emit step-batch:')
                    traceback.print_exc()
            await self.sio.sleep(delay)

    async def index(self, request):
        """Serve the client-side application."""
        with open('index.html') as f:
            return web.Response(text=f.read(), content_type='text/html')

    def create_app(self):
        """Create the web application."""
        app = web.Application()
        # app.router.add_static('/static', 'static')
        app.router.add_get('/', self.index)
        return app

    async def init_app(self, app):
        """Initialize the application."""
        self.sio.attach(app)
        self.sio.start_background_task(self.emit_readings)
        return app

    def run(self):
        """Run the server."""
        app = self.create_app()
        web.run_app(self.init_app(app), port=self.port)
