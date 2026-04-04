"""Utilities for display drivers."""

import json
import pathlib
import asyncio

from collections import defaultdict
from dataclasses import dataclass

import tomli
import aiomqtt

from simoc_sam import utils
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


def format_values(sensor_readings_dict, max_rows=None):
    """Format sensor values for display using configured format string."""
    # flatten sensor readings: {'scd30': {'co2': 450}} -> {'scd30_co2': 450}
    flattened = {'uptime': utils.uptime()}  # add uptime
    for sensor, data in sensor_readings_dict.items():
        if not data:
            continue
        for key, val in data.items():
            flattened[f"{sensor}_{key}"] = val
    rows = []
    for line in config.display_format.splitlines():
        try:
            rows.append(line.format_map(flattened))
        except KeyError:
            continue  # skip lines without corresponding values
        except (ValueError, TypeError) as e:
            print(f"Error formatting line {line!r}: {e}")
            continue  # skip lines with formatting errors
    return rows[:max_rows] if max_rows else rows


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
                        sensor = topic.split('/')[-1]  # location/host/sensor
                        payload = json.loads(message.payload.decode())
                    except (AttributeError, json.JSONDecodeError) as e:
                        print(f'Error processing MQTT message: {e}')
                        continue
                    sensor_readings_dict[sensor] = payload
                    if config.verbose_mqtt:
                        print(f'Received from {sensor}: {payload}')
        except asyncio.CancelledError:
            raise
        except aiomqtt.MqttError as err:
            print(f'* Connection lost from <{mqtt_addr}>: {err}')
        except Exception as e:
            print(f'Unexpected error in MQTT handler: {e}')
        print(f'* Reconnecting in {reconnect_delay} seconds...')
        await asyncio.sleep(reconnect_delay)
