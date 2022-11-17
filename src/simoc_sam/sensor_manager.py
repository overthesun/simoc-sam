import sys
import signal
import asyncio
import subprocess

import socketio

sio = socketio.AsyncClient()
processes = dict()

def terminate_all():
    """Stop all sensor processes"""
    global processes
    for sensor, process in processes.items():
        print(f'Killing {sensor}')
        process.send_signal(signal.SIGINT)
        process.communicate()
    processes = dict()

def start_all():
    """Attempt to start all sensor types"""
    sensors_to_start = ['scd30', 'vernier', 'mocksensor']
    for sensor in sensors_to_start:
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

async def main(port=None):
    """Connect to the server and register as a sensor manager."""
    # connect to the server and wait
    if port is None:
        port = 8081
    try:
        await sio.connect(f'http://localhost:{port}')
        await sio.wait()
    finally:
        terminate_all()

if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(port))
