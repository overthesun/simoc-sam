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

# Display configuration
display = 'ssd1306_128x64'


# MQTT configuration
mqtt_host = 'localhost'
mqtt_port = 1883
mqtt_secure = False
mqtt_certs_dir = Path.home() / '.mqttcerts'
mqtt_reconnect_delay = 5.0


# SIMOC Web / SIO bridge configuration
sio_host = 'localhost'
sio_port = 8081
data_source = 'logs'  # 'mqtt' or 'logs'
mqtt_topic_sub = '#'
simoc_web_dist_dir = '/var/www/simoc'


# Verbosity and logging
verbose_sensor = False
verbose_mqtt = False
enable_jsonl_logging = True
log_dir = Path.home() / 'logs'
