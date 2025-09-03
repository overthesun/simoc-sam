"""
Default settings for SIMOC Live.
This file is copied to ~/.config/simoc-sam/config.py for user overrides,
with a symlink pointing to it for easier editing/discoverability.
"""

from pathlib import Path


# Sensors and data collection
sensors = ['bme688', 'scd30', 'sgp30']
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


# remove non-config vars
del Path
