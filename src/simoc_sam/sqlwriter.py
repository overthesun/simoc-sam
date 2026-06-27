import json

import paho.mqtt.client as mqtt

from simoc_sam import config
from simoc_sam.db import init_db
from simoc_sam.sensors.utils import SENSOR_DATA


DB_CONN = None


def on_connect(client, userdata, flags, rc, properties=None):
    print(f'Connected with result code {rc}')
    client.subscribe(config.mqtt_topic_sub)


def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    topic = msg.topic
    print(f'Received message <{topic}>: {payload}')
    try:
        data = json.loads(payload)
        location, host, sensor = topic.split('/')
        fields = list(SENSOR_DATA[sensor].data.keys())
    except (json.JSONDecodeError, ValueError) as e:
        print(f'Skipping invalid message <{topic}>: {payload} ({e})')
        return
    except KeyError:
        print(f'Skipping unknown sensor in <{topic}>')
        return
    sensor_id = f'{location}.{host}.{sensor}'
    cols = ['sensor_id', 'location', 'host', 'n', 'timestamp', *fields]
    values = [sensor_id, location, host,
               data.get('n'), data.get('timestamp'),
               *[data.get(f) for f in fields]]
    placeholders = ', '.join('?' * len(cols))
    DB_CONN.execute(
        f'INSERT INTO {sensor} ({", ".join(cols)}) VALUES ({placeholders})',
        values,
    )
    DB_CONN.commit()


def main():
    global DB_CONN
    if not config.data_dir.exists():
        print(f'Creating data directory: {config.data_dir}')
        config.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = config.data_dir / config.db_name
    print(f'Opening SQLite database: {db_path}')
    DB_CONN = init_db(db_path)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.mqtt_host, config.mqtt_port)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print('Interrupted by user, disconnecting...')
        client.disconnect()
    finally:
        DB_CONN.close()
        print('Disconnected from MQTT broker')


if __name__ == '__main__':
    main()
