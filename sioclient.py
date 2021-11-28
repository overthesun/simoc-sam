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

async def main():
    await sio.connect('http://localhost:8081')

    await sio.emit('msg', '1st test message')
    await sio.emit('get_data', '5')
    await sio.emit('msg', '2nd test message')
    await sio.emit('get_data', '5')
    await sio.emit('msg', '3rd test message')

    await sio.wait()


if __name__ == '__main__':
    asyncio.run(main())
