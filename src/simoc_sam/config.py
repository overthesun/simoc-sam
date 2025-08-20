"""
Configuration variables for SIMOC Live.

Edit this file to change the configuration.
"""

from pathlib import Path


# Data collection
sensor_read_delay = 10.0


# MQTT configuration
mqtt_topic_location = 'sam'
mqtt_host = 'localhost'
mqtt_port = 1883
mqtt_reconnect_delay = 5.0


# SIMOC Web / SIO bridge configuration
sio_host = 'localhost'
sio_port = 8081
mqtt_topic_sub = f'{mqtt_topic_location}/#'
simoc_web_port = 8080  # used for CORS validation
simoc_web_dist_dir = Path.home() / 'dist'


# Verbosity and logging
verbose_sensor = False
verbose_mqtt = False
enable_jsonl_logging = True
log_dir = Path.home() / 'logs'


# HAB info
humans = 4
volume = 272
