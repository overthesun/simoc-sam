"""
Default settings for SIMOC Live.
This file is copied to ~/.config/simoc-sam/config.py for user overrides,
with a symlink pointing to it for easier editing/discoverability.
"""

from pathlib import Path


# HAB info
location = None
humans = 0
volume = 0


# Sensors and data collection
sensors = ['bme688', 'scd30', 'sgp30']
sensor_read_delay = 10.0


# MQTT configuration
mqtt_host = 'localhost'
mqtt_port = 1883
mqtt_reconnect_delay = 5.0


# SIMOC Web / SIO bridge configuration
sio_host = 'localhost'
sio_port = 8081
mqtt_topic_sub = f'{location}/#'
simoc_web_port = 8080  # used for CORS validation
simoc_web_dist_dir = Path.home() / 'dist'


# Verbosity and logging
verbose_sensor = False
verbose_mqtt = False
enable_jsonl_logging = True
log_dir = Path.home() / 'logs'
