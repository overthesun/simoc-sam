import sys
import asyncio

import socketio

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print('Connected to server')

@sio.event
async def log(data):
    print(data)

@sio.event
async def send_data(data):
    print(data)

@sio.event
async def disconnect():
    print('Server disconnected')

async def main(port=None):
    if port is None:
        port = '5000'
    await sio.connect(f'http://localhost:{port}')

    await sio.emit('msg', '1st test message')
    await sio.emit('get_data', '5')
    await sio.emit('msg', '2nd test message')
    await sio.emit('get_data', '5')
    await sio.emit('msg', '3rd test message')

    await sio.wait()


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(port))
