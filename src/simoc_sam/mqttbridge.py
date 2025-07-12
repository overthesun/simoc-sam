import json
import copy
import asyncio
import traceback

import aiomqtt

from .sensors import utils
from .baseserver import BaseServer


# default host:port of the MQTT broker
MQTT_HOST, MQTT_PORT = utils.get_mqtt_addr()


class MQTTBridge(BaseServer):
    """MQTT bridge server that combines MQTT and SocketIO functionality"""

    def __init__(self, port=8081):
        super().__init__(port=port)
        self.sensor_data = self.convert_sensor_data()

    def convert_sensor_data(self):
        """Convert sensor data from utils to the format expected by MQTT bridge."""
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

    async def mqtt_handler(self):
        """Handle MQTT connections and messages."""
        args = utils.parse_args()
        mqtt_broker = args.host or MQTT_HOST
        topic_sub = args.mqtt_topic
        print(self.sensor_info)
        interval = 5  # Seconds
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
                        # print(topic)
                        sam, host, sensor = topic.split('/')
                        sensor_id = f'{host}.{sensor}'
                        if sensor_id not in self.sensor_info:
                            self.sensors.add(sensor_id)
                            info = copy.deepcopy(self.sensor_data[sensor])
                            info['sensor_name'] = sensor_id
                            info['sensor_id'] = sensor_id
                            info['sensor_desc'] = f'{sensor} sensor on {host}'
                            self.sensor_info[sensor_id] = info
                            await self.emit_to_subscribers('sensor-info', self.sensor_info)

                        payload = json.loads(message.payload.decode())
                        # print('adding', payload)
                        self.sensor_readings[sensor_id].append(payload)
            except aiomqtt.MqttError as err:
                print(f'* Connection lost from <{mqtt_broker}>; {err}')
                print(f'* Reconnecting in {interval} seconds...')
                await asyncio.sleep(interval)

    async def init_app(self, app):
        """Initialize the application with MQTT handler."""
        self.sio.attach(app)
        self.sio.start_background_task(self.emit_readings)
        asyncio.ensure_future(self.mqtt_handler())
        return app


if __name__ == '__main__':
    server = MQTTBridge(port=8081)
    server.run()
