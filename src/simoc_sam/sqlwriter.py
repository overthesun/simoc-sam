import json

import paho.mqtt.client as mqtt

from simoc_sam import config, db
from simoc_sam.sensors.utils import SENSOR_DATA


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
    n = data.get('n')
    timestamp = data.get('timestamp')
    if n is None or timestamp is None:
        print(f'Skipping message missing n/timestamp <{topic}>: {payload}')
        return
    cols = ['sensor_id', 'location', 'host', 'n', 'timestamp', *fields]
    values = [sensor_id, location, host, n, timestamp,
              *[data.get(f) for f in fields]]
    placeholders = ', '.join('?' * len(cols))
    conn = db.get_conn()
    conn.execute(
        f'INSERT INTO {sensor} ({", ".join(cols)}) VALUES ({placeholders})',
        values,
    )
    conn.commit()


def main():
    db_dir = config.db_path.parent
    if not db_dir.exists():
        print(f'Creating database directory: {db_dir}')
        db_dir.mkdir(parents=True, exist_ok=True)
    conn = db.init_db()
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
        db.close_db()
        print('Disconnected from MQTT broker')


if __name__ == '__main__':
    main()
