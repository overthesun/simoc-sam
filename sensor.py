import sys
import random
import asyncio
import argparse
import socketio

STEP_INTERVAL = 1  # how many seconds between readings for fake mode
BATCH_SIZE = 10  # how many steps in a batch

sio = socketio.AsyncClient()

def get_fake_data(co2_ppm, temp, hum_perc):
    """ Generate fake sensor data """
    # add/remove random increment/decrements
    co2_ppm += random.randint(1, 500) * random.choice([-1, 0, +1])
    temp += random.random() * random.choice([-1, 0, +1])
    hum_perc += random.randint(1, 10) * random.choice([-1, 0, +1])
    # clip values to be within range
    co2_ppm = max(250, min(co2_ppm, 5000))
    temp = max(15, min(temp, 25))
    hum_perc = max(0, min(hum_perc, 100))
    # convert to float since server expects float
    co2_ppm, temp, hum_perc = float(co2_ppm), float(temp), float(hum_perc)
    return dict(co2=co2_ppm, temp=temp, humidity=hum_perc)

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
    """Generate sensor data and send them to the server in batches."""
    print('Server requested sensor data')
    step_num = 0
    co2_ppm = 1000.0
    temp = 20.0
    hum_perc = 50.0
    if live_mode: 
        sensor = senseutil.Sensor()
        sensor_type = "live"
    else:
        sensor_type = "mock"
    print(f'Starting to read data from the {sensor_type} sensor')
    # endless loop that reads sensor data
    while True:
        batch = []
        for step in range(BATCH_SIZE):
            try:
                if live_mode:  # Get live data from a real sensor
                    interval_data = senseutil.get_interval_data(sensor.scd,
                                                                step_num)
                else:  # Get fake semi-random data
                    interval_data = get_fake_data(co2_ppm, temp, hum_perc)
                # Retrieve data from dict
                co2_ppm = interval_data["co2"]
                temp = interval_data["temp"]
                hum_perc = interval_data["humidity"]
                
                #prnt the data to the screen
                print(f'{step_num}: CO2: {co2_ppm:5.0f}ppm; Temperature: '
                      f'{temp:2.2f}°; Humidity: {hum_perc:2.2f}%')
                # add sensor data to the batch
                batch.append(dict(step_num=step_num, co2_ppm=co2_ppm,
                                  temp=temp, hum_perc=hum_perc))
                step_num += 1
                # wait for the next sensor reading
                await asyncio.sleep(STEP_INTERVAL)
            except RuntimeError as e:  # Ignore sensor error and retry step
                print(e)
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
    parser = argparse.ArgumentParser()
    port_help = "The port used to connect to the server."
    parser.add_argument('port', nargs='?', default=None, help=port_help ,type=int)
    live_help = "Read data from a live sensor"
    parser.add_argument('--live', help=live_help, action='store_true')
    args = parser.parse_args()
    port = str(args.port)
    live_mode = args.live
    if live_mode:
        import senseutil
        STEP_INTERVAL = 3  # SCD-30 only has data available every ~ 2.2-2.6s
    asyncio.run(main(port))
