import sys
import signal
import asyncio
import subprocess

import socketio

from .sensors import utils

# default host:port of the sioserver
SIO_HOST, SIO_PORT = utils.get_sioserver_addr()

sio = socketio.AsyncClient()
processes = dict()

def terminate_all():
    """Stop all sensor processes"""
    for sensor, process in processes.items():
        print(f'Killing {sensor}')
        process.send_signal(signal.SIGINT)
        process.communicate()
    processes.clear()

def start_all():
    """Attempt to start all sensor types"""
    # TODO: Generate list by scanning sensors dir or calling method on each
    # class found in dir
    sensors_to_start = ['scd30', 'vernier', 'mocksensor']
    for sensor in sensors_to_start:
        print(f'Attempting to start {sensor}...')
        process = subprocess.Popen(['python3', '-m', f'simoc_sam.sensors.{sensor}'])
        processes[sensor] = process

@sio.on('refresh-sensors')
def refresh_sensors():
    """Reset all sensors on sensor-manager device"""
    print('Refreshing sensors')
    terminate_all()
    start_all()

@sio.event
async def connect():
    print('Connected to server')
    print('Registering sensor manager')
    await sio.emit('register-sensor-manager')

@sio.event
async def disconnect():
    print('Server disconnected')

async def main(host=SIO_HOST, port=SIO_PORT):
    """Connect to the server and register as a sensor manager."""
    # connect to the server and wait
    try:
        await sio.connect(f'http://{host}:{port}')
        await sio.wait()
    finally:
        terminate_all()

if __name__ == '__main__':
    parser = utils.get_addr_argparser()
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
