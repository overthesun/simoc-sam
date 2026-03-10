import os
import csv
import json

import paho.mqtt.client as mqtt

from simoc_sam import config


# Callback when the client connects to the broker
def on_connect(client, userdata, flags, rc, properties=None):
    print(f'Connected with result code {rc}')
    # Subscribe to the MQTT topic from config
    client.subscribe(config.mqtt_topic_sub)

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    topic = msg.topic
    print(f"Received message: {payload}")
    print(f"from topic: {topic}")
    # Parse the payload (assuming it's JSON, adjust as needed)
    data = json.loads(payload)

    # Define file name based on topic
    csv_file_path = "/home/sam/data/" + topic.replace("/", "_") + ".csv"

    # Append the data to the CSV file
    with open(csv_file_path, 'a', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        #field_names = sorted(data.keys())
        field_names = ['n', 'timestamp', *[k for k in data if k not in {'n', 'timestamp'}]]
        # Check if the CSV file is empty
        is_empty = os.stat(csv_file_path).st_size == 0

        # Write headers if the file is empty
        if is_empty:
            # Update the set of field names based on the payload keys
            csv_writer.writerow(field_names)

        # Write data to the CSV file
        csv_writer.writerow([data.get(field, '') for field in field_names])

    #print("Data logged to CSV")

# main

def main():
    # Create an MQTT client
    client = mqtt.Client()

    # Set callback functions
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the MQTT broker using config values
    client.connect(config.mqtt_host, config.mqtt_port)

    # Loop to handle MQTT communication
    client.loop_forever()
    print("Disconnected from MQTT broker")

if __name__ == '__main__':
    main()
