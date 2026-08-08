#!/usr/bin/env python
import paho.mqtt.client as mqtt

KEEPALIVE = 10  # in seconds
TOPIC = "sam/#"

LOCAL_BROKER ='localhost'
LOCAL_PORT = 1883

REMOTE_BROKER ='mqtt.simoc.space' # this must match the CNAME in your server-cert!
REMOTE_PORT = 8883

# Callback when the client connects to the broker
def on_local_connect(local_client, userdata, flags, rc, properties=None):
    print(f'Locally connected with result code {rc}')
    # Subscribe to the MQTT topic
    local_client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    topic = msg.topic
    print(f"Received message: {payload}")
    print(f"from topic: {topic}")
    forward_message(topic, payload)

# Function to forward the message to the remote broker
def forward_message(topic, payload):
    remote_client.publish(topic, payload)
    print(f"Message forwarded to remote broker: {topic} -> {payload}")

# Create an MQTT client
local_client = mqtt.Client()
remote_client = mqtt.Client()

# Set callback functions
local_client.on_connect = on_local_connect
local_client.on_message = on_message

remote_client.tls_set(ca_certs="/etc/mosquitto/certs/ca.crt", certfile="/etc/mosquitto/certs/client.crt", keyfile="/etc/mosquitto/certs/client.key")
remote_client.tls_insecure_set(True)

# Connect to the local MQTT broker
local_client.connect(LOCAL_BROKER, LOCAL_PORT, KEEPALIVE)
# Connect to the remote MQTT broker
remote_client.connect(REMOTE_BROKER, REMOTE_PORT, KEEPALIVE)

# Start the loop to process received messages and maintain connections
local_client.loop_start()
remote_client.loop_start()

try:
    while True:
        pass  # Keep the script running
except KeyboardInterrupt:
    print("Exiting bridge server...")
    local_client.loop_stop()
    remote_client.loop_stop()
    local_client.disconnect()
    remote_client.disconnect()
  
