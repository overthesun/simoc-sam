import sys
import random
import asyncio

import socketio


STEP_INTERVAL = 1  # how many seconds between readings
BATCH_SIZE = 10  # how many steps in a batch

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print('Connected to server')
    print('Registering sensor')
    await sio.emit('register-sensor')

@sio.event
async def disconnect():
    print('Server disconnected')

@sio.on('send-data')
async def send_data():
    """Generate fake sensor data and send them to the server in batches."""
    print('Server requested sensor data')
    step_num = 0
    co2_ppm = 1000
    temp = 20
    hum_perc = 50
    print('Starting to read data from the (mock) sensor')
    # endless loop that reads sensor data
    while True:
        batch = []
        for step in range(BATCH_SIZE):
            # add/remove random increment/decrements
            co2_ppm += random.randint(1, 500) * random.choice([-1, 0, +1])
            temp += random.random() * random.choice([-1, 0, +1])
            hum_perc += random.randint(1, 10) * random.choice([-1, 0, +1])
            # clip values to be within range
            co2_ppm = max(250, min(co2_ppm, 5000))
            temp = max(15, min(temp, 25))
            hum_perc = max(0, min(hum_perc, 100))

            print(f'{step_num}: CO2: {co2_ppm:4}ppm; Temperature: '
                  f'{temp:2.1f}°; Humidity: {hum_perc:2}%')
            # add sensor data to the batch
            batch.append(dict(step_num=step_num, co2_ppm=co2_ppm,
                              temp=temp, hum_perc=hum_perc))
            step_num += 1
            # wait for the next sensor reading
            await asyncio.sleep(STEP_INTERVAL)
        if not sio.connected:
            print('Not connected to server, stop reading/sending data')
            return  # TODO: this will reset the step_num
        # send batch to the server
        print(f'Sending a {BATCH_SIZE}-readings batch')
        await sio.emit('sensor-batch', batch)



async def main(port=None):
    if port is None:
        port = '5000'
    # connect to the server and wait
    await sio.connect(f'http://localhost:{port}')
    await sio.wait()


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(port))
