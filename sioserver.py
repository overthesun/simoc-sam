import asyncio
import random

import socketio

from aiohttp import web


sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app)

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

@sio.event
def connect(sid, environ):
    print('connect:', sid)

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

@sio.event
def disconnect(sid):
    print('disconnect:', sid)

#app.router.add_static('/static', 'static')
app.router.add_get('/', index)

if __name__ == '__main__':
    web.run_app(app)
