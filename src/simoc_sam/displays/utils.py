"""Utilities for display drivers."""

import json
import pathlib
import asyncio

from collections import defaultdict
from dataclasses import dataclass

import tomli
import aiomqtt

from simoc_sam import config


@dataclass
class DisplayData:
    name: str
    description: str
    module: str
    width: int
    height: int
    i2c_address: int
    reset_pin: str = None


DISPLAYS_TOML = pathlib.Path(__file__).with_name('displays.toml')


def load_display_data(file_path=DISPLAYS_TOML):
    """Load display configuration from displays.toml."""
    with open(file_path, 'rb') as f:
        displays = tomli.load(f)
    display_data = {}
    for display_key, display_info in displays.items():
        display_data[display_key] = DisplayData(
            name=display_info['name'],
            description=display_info['description'],
            module=display_info['module'],
            width=display_info['width'],
            height=display_info['height'],
            i2c_address=display_info['i2c_address'],
            reset_pin=display_info.get('reset_pin'),
        )
    return display_data


DISPLAY_DATA = load_display_data()
I2C_TO_DISPLAY_NAMES = defaultdict(list)
for name, info in DISPLAY_DATA.items():
    I2C_TO_DISPLAY_NAMES[info.i2c_address].append(name)


# Display configuration constants
MAX_ROWS = 9
DISPLAY_ORDER = ['scd30', 'sgp30', 'bme688', 'tsl2591', 'bno085']


def format_values(sensor_readings_dict):
    """Format sensor values for display from a sensor readings dictionary."""
    rows = []
    for sensor in DISPLAY_ORDER:
        data = sensor_readings_dict.get(sensor)
        if not data:
            continue
        if sensor == 'scd30':
            rows.append(f"CO2: {data.get('co2', 0):.0f}")
            rows.append(f"T: {data.get('temperature', 0):.2f}C")
            rows.append(f"RH: {data.get('humidity', 0):.2f}%")
        elif sensor == 'sgp30':
            rows.append(f"VOC: {data.get('tvoc', 0)}")
        elif sensor == 'bme688':
            rows.append(f"Pr: {data.get('pressure', 0):.2f}")
        elif sensor == 'tsl2591':
            rows.append(f"Lt: {data.get('light', 0):.2f}")
        elif sensor == 'bno085':
            for axis in ['linear_accel_x', 'linear_accel_y', 'linear_accel_z']:
                val = data.get(axis, 0)
                if isinstance(val, str):
                    val = 0
                rows.append(f"A-{axis[-1]}: {val:.2f}")
        if len(rows) >= MAX_ROWS:
            rows = rows[:MAX_ROWS]
            break
    return rows


async def mqtt_monitor(sensor_readings_dict):
    """Add sensor data received from MQTT to the given dictionary (in place)."""
    mqtt_host, mqtt_port = config.mqtt_host, config.mqtt_port
    mqtt_addr = f"{mqtt_host}:{mqtt_port}"
    mqtt_topic_sub = config.mqtt_topic_sub
    reconnect_delay = config.mqtt_reconnect_delay
    while True:
        try:
            print(f'* Connecting to MQTT broker <{mqtt_addr}>...')
            async with aiomqtt.Client(mqtt_host, mqtt_port) as client:
                await client.subscribe(mqtt_topic_sub)
                print(f'* Connected to <{mqtt_addr}>, '
                      f'subscribed to {mqtt_topic_sub!r}.')
                async for message in client.messages:
                    try:
                        topic = message.topic.value
                        sensor = topic.split('/')[-1] # location/host/sensor
                        payload = json.loads(message.payload.decode())
                        sensor_readings_dict[sensor] = payload
                        if config.verbose_mqtt:
                            print(f'Received {sensor}: {payload}')
                    except Exception as e:
                        print(f'Error processing MQTT message: {e}')
        except aiomqtt.MqttError as err:
            print(f'* Connection lost from <{mqtt_addr}>: {err}')
        except Exception as e:
            print(f'Unexpected error in MQTT handler: {e}')
        print(f'* Reconnecting in {reconnect_delay} seconds...')
        await asyncio.sleep(reconnect_delay)
