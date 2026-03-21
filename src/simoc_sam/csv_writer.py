import os
import csv
import json

import paho.mqtt.client as mqtt

from simoc_sam import config
from simoc_sam.sensors.utils import SENSOR_DATA


def on_connect(client, userdata, flags, rc, properties=None):
    print(f'Connected with result code {rc}')
    client.subscribe(config.mqtt_topic_sub)

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    topic = msg.topic
    print(f"Received message <{topic}>: {payload}")
    data = json.loads(payload)
    location, host, sensor = topic.split('/')
    csv_file_path = config.data_dir / f'{location}_{host}_{sensor}.csv'
    # append the data to the CSV file
    with open(csv_file_path, 'a', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        field_names = ['n', 'timestamp', *SENSOR_DATA[sensor].data.keys()]
        # add headers if the CSV is empty
        if os.stat(csv_file_path).st_size == 0:
            csv_writer.writerow(field_names)
        # append data row to the CSV file
        csv_writer.writerow([data.get(field, '') for field in field_names])

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.mqtt_host, config.mqtt_port)
    client.loop_forever()
    print("Disconnected from MQTT broker")

if __name__ == '__main__':
    main()
