"""Tests for simoc_sam.displays.utils module."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from PIL import Image

from simoc_sam import config
from simoc_sam.displays import utils
from simoc_sam.displays.utils import DisplayData

from conftest import wait_until, terminate_task


@pytest.fixture
def mock_mqtt_message():
    """Factory fixture for creating mock MQTT messages."""
    def _create_message(topic, payload):
        mock_message = MagicMock()
        mock_message.topic.value = topic
        mock_message.payload.decode.return_value = payload
        return mock_message
    return _create_message


@pytest.fixture
def mock_mqtt_client(mock_mqtt_message):
    """Factory fixture for creating mock MQTT clients with messages."""
    def _create_client(messages):
        """Create a mock client that yields the given messages."""
        if isinstance(messages, list):
            async def mock_messages_gen():
                for topic, payload in messages:
                    yield mock_mqtt_message(topic, payload)
        else:
            mock_messages_gen = messages  # assume it's already an async gen
        mock_client = AsyncMock()
        mock_client.messages = mock_messages_gen()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        return mock_client
    return _create_client


@asynccontextmanager
async def mqtt_monitor_task(sensor_readings):
    """Context manager for running and cleaning up mqtt_monitor task."""
    async def monitor():
        await utils.mqtt_monitor(sensor_readings)
    task = asyncio.create_task(monitor())
    try:
        yield task
    finally:
        await terminate_task(task)


@pytest.fixture
def mock_displays_toml(tmp_path):
    """Create a temporary displays.toml file for testing."""
    toml_content = """
[test_display]
name = "Test Display"
description = "A test display"
module = "test.module"
width = 128
height = 64
i2c_address = 0x3C

[test_display_with_reset]
name = "Test Display with Reset"
description = "A test display with reset pin"
module = "test.module2"
width = 256
height = 128
i2c_address = 0x3D
reset_pin = "D5"
"""
    toml_file = tmp_path / "test_displays.toml"
    toml_file.write_text(toml_content)
    return toml_file


def test_load_display_data_default():
    """Test loading display data from the default displays.toml."""
    display_data = utils.load_display_data()
    # check that some known displays are loaded
    assert 'ssd1306' in display_data
    assert 'mockdisplay' in display_data
    # verify data structure
    ssd1306 = display_data['ssd1306']
    assert isinstance(ssd1306, DisplayData)
    assert ssd1306.name == "SSD1306"
    assert ssd1306.width == 128
    assert ssd1306.height == 64
    assert ssd1306.i2c_address == 0x3D
    assert ssd1306.reset_pin == "D4"


def test_load_display_data_custom_file(mock_displays_toml):
    """Test loading display data from a custom TOML file."""
    display_data = utils.load_display_data(mock_displays_toml)
    assert 'test_display' in display_data
    assert 'test_display_with_reset' in display_data
    # verify display without reset pin
    test_display = display_data['test_display']
    assert test_display.name == "Test Display"
    assert test_display.description == "A test display"
    assert test_display.module == "test.module"
    assert test_display.width == 128
    assert test_display.height == 64
    assert test_display.i2c_address == 0x3C
    assert test_display.reset_pin is None
    # verify display with reset pin
    test_reset = display_data['test_display_with_reset']
    assert test_reset.reset_pin == "D5"


def test_display_data_i2c_mapping():
    """Test that I2C_TO_DISPLAY_NAMES is correctly populated."""
    assert 0x3D in utils.I2C_TO_DISPLAY_NAMES
    assert 'ssd1306' in utils.I2C_TO_DISPLAY_NAMES[0x3D]
    assert 0x00 in utils.I2C_TO_DISPLAY_NAMES
    assert 'mockdisplay' in utils.I2C_TO_DISPLAY_NAMES[0x00]


def test_format_values_basic():
    """Test basic formatting of sensor values."""
    sensor_readings = {
        'bme688': {'temperature': 25.5, 'humidity': 60.0},
        'scd30': {'co2': 450},
    }
    format_string = "T: {bme688_temperature:.1f}C\nCO2: {scd30_co2:.0f}"
    with patch.object(config, 'display_format', format_string):
        result = utils.format_values(sensor_readings)
    assert len(result) == 2
    assert result[0] == "T: 25.5C"
    assert result[1] == "CO2: 450"


def test_format_values_includes_uptime():
    """Test that format_values includes uptime."""
    sensor_readings = {}
    format_string = "Up {uptime}"
    with patch.object(config, 'display_format', format_string), \
         patch('simoc_sam.displays.utils.utils.uptime', return_value='01:23:45'):
        result = utils.format_values(sensor_readings)
    assert len(result) == 1
    assert result[0] == 'Up 01:23:45'


def test_format_values_missing_data():
    """Test that lines with missing data are skipped."""
    sensor_readings = {
        'bme688': {'temperature': 25.5},
    }
    format_string = "T: {bme688_temperature:.1f}C\nCO2: {scd30_co2:.0f}\nOK"
    with patch.object(config, 'display_format', format_string):
        result = utils.format_values(sensor_readings)
    # only lines with available data should be returned
    assert len(result) == 2
    assert result[0] == "T: 25.5C"
    assert result[1] == "OK"


def test_format_values_invalid_format():
    """Test that lines with invalid format strings are skipped."""
    sensor_readings = {
        'scd30': {'co2': 450},
        'bme688': {'temperature': 'invalid'},
    }
    # format expects float but value is string
    format_string = "CO2: {scd30_co2:.0f}\nT: {bme688_temperature:.1f}C\nEnd"
    with patch.object(config, 'display_format', format_string):
        result = utils.format_values(sensor_readings)
    # only the valid line should be returned
    assert len(result) == 2
    assert result[0] == "CO2: 450"
    assert result[1] == "End"


def test_format_values_empty_sensor_data():
    """Test handling of empty sensor data dictionaries."""
    sensor_readings = {
        'bme688': {},  # Empty data
        'scd30': None,  # None data (shouldn't be used)
        'sgp30': {'tvoc': 100},
    }
    format_string = "VOC: {sgp30_tvoc}"
    with patch.object(config, 'display_format', format_string):
        result = utils.format_values(sensor_readings)
    assert len(result) == 1
    assert result[0] == "VOC: 100"


@pytest.mark.parametrize("max_rows,expected_count", [
    (2, 2),
    (None, 3),
])
def test_format_values_max_rows(max_rows, expected_count):
    """Test that max_rows parameter limits the output."""
    sensor_readings = {
        'sensor1': {'val1': 1, 'val2': 2, 'val3': 3},
    }
    format_string = "L1: {sensor1_val1}\nL2: {sensor1_val2}\nL3: {sensor1_val3}"
    with patch.object(config, 'display_format', format_string):
        result = utils.format_values(sensor_readings, max_rows=max_rows)
    assert len(result) == expected_count
    assert result[0] == "L1: 1"
    assert result[1] == "L2: 2"
    if expected_count == 3:
        assert result[2] == "L3: 3"


@pytest.mark.asyncio
async def test_mqtt_monitor_basic(mock_mqtt_client):
    """Test basic MQTT monitoring functionality."""
    sensor_readings = {}
    client = mock_mqtt_client([('location/testhost1/scd30',
                                '{"co2": 450, "temp": 25.5}')])
    with patch('simoc_sam.displays.utils.aiomqtt.Client', return_value=client):
        async with mqtt_monitor_task(sensor_readings):
            await wait_until(lambda: 'scd30' in sensor_readings)
            assert sensor_readings['scd30'] == {'co2': 450, 'temp': 25.5}

@pytest.mark.asyncio
async def test_mqtt_monitor_override(mock_mqtt_client):
    """Test that MQTT monitor overrides previous sensor readings with new data."""
    sensor_readings = {}
    client = mock_mqtt_client([
        ('location/testhost1/scd30', '{"co2": 450, "temp": 25.5}'),
        ('location/testhost1/scd30', '{"co2": 500, "temp": 26.0}'),
        ('location/testhost1/bme688', '{"temp": 24.0}'),
    ])
    with patch('simoc_sam.displays.utils.aiomqtt.Client', return_value=client):
        async with mqtt_monitor_task(sensor_readings):
            await wait_until(lambda: 'bme688' in sensor_readings)
            assert sensor_readings['scd30'] == {'co2': 500, 'temp': 26.0}

@pytest.mark.asyncio
async def test_mqtt_monitor_handles_json_error(mock_mqtt_message, mock_mqtt_client):
    """Test that MQTT monitor handles JSON decoding errors gracefully."""
    sensor_readings = {}
    processed = {'value': False}
    # create a message gen that sets the flag after yielding the message
    async def mock_messages_gen():
        yield mock_mqtt_message('location/testhost1/sensor1', 'invalid json')
        processed['value'] = True
        await asyncio.sleep(100)
    mock_client = mock_mqtt_client(mock_messages_gen)
    with patch('simoc_sam.displays.utils.aiomqtt.Client', return_value=mock_client):
        async with mqtt_monitor_task(sensor_readings):
            await wait_until(lambda: processed['value'])
            assert sensor_readings == {}

@pytest.mark.asyncio
async def test_mqtt_monitor_verbose_mode(mock_mqtt_client, capfd):
    """Test that verbose MQTT mode prints received messages."""
    sensor_readings = {}
    client = mock_mqtt_client([
        ('location/testhost1/scd30', '{"co2": 450}')
    ])
    with patch.object(config, 'verbose_mqtt', True), \
        patch('simoc_sam.displays.utils.aiomqtt.Client', return_value=client):
        async with mqtt_monitor_task(sensor_readings):
            await wait_until(lambda: 'scd30' in sensor_readings)
            captured = capfd.readouterr()
            assert "Received from scd30: {'co2': 450}\n" in captured.out

@pytest.mark.asyncio
async def test_mqtt_monitor_reconnects_on_error(mock_mqtt_client, mock_mqtt_message, capfd):
    """Test that MQTT monitor attempts to reconnect on connection errors."""
    sensor_readings = {}
    attempts = {'count': 0}
    # mock client factory that simulates a connection error on the first attempt
    def mock_client_factory(*args, **kwargs):
        attempts['count'] += 1
        async def mock_msg_gen():
            if attempts['count'] == 1:
                raise Exception("Connection lost")  # raise error first time
            else:
                yield mock_mqtt_message('location/testhost1/scd30', '{"co2": 450}')
        return mock_mqtt_client(mock_msg_gen)
    with patch.object(config, 'mqtt_reconnect_delay', 0.1), \
        patch.object(config, 'verbose_mqtt', True), \
        patch('simoc_sam.displays.utils.aiomqtt.Client', side_effect=mock_client_factory):
        async with mqtt_monitor_task(sensor_readings):
            await wait_until(lambda: attempts['count'] >= 2, timeout=2.0)
            assert attempts['count'] >= 2
            captured = capfd.readouterr()
            assert captured.out.count('Connecting to MQTT broker') >= 2
            assert captured.out.count('Connection lost') == 1
            assert captured.out.count('Reconnecting in') >= 1
            assert "Received from scd30: {'co2': 450}\n" in captured.out


def test_draw_image_returns_none_for_empty_rows():
    """Test that draw_image returns None when given no rows."""
    assert utils.draw_image(128, 128, []) is None
    assert utils.draw_image(128, 128, None) is None

def test_draw_image_returns_1bit_image():
    """Test that draw_image returns a 1-bit PIL image of the correct size."""
    width, height = 128, 64
    image = utils.draw_image(width, height, ["Test"])
    assert isinstance(image, Image.Image)
    assert image.size == (width, height)
    assert image.mode == "1"

def test_draw_image_black_background():
    """Test that draw_image renders a black background."""
    image = utils.draw_image(128, 64, [" "])  # empty line with no text
    pixels = set(image.getdata())
    assert pixels == {0}  # all pixels should be black (0)

def test_draw_image_has_white_pixels_for_text():
    """Test that draw_image renders text as white pixels on black background."""
    image = utils.draw_image(128, 64, ["Test"])
    pixels = list(image.getdata())
    # should only have black (0) and white (255) pixels
    assert set(pixels) == {0, 255}
    assert pixels.count(0) > pixels.count(255)  # more black than white

def test_draw_image_blank_rows_add_space():
    """Test that blank rows add spacing but no text pixels."""
    image_no_blank = utils.draw_image(128, 64, ["Row 1", "Row 2"])
    image_with_blank = utils.draw_image(128, 64, ["Row 1", "   ", "Row 2"])
    white_no_blank = sum(1 for p in image_no_blank.getdata() if p)
    white_with_blank = sum(1 for p in image_with_blank.getdata() if p)
    # same text so the same white pixel count, but different images
    assert white_no_blank == white_with_blank
    assert image_no_blank.getdata() != image_with_blank.getdata()

def test_draw_image_respects_dimensions():
    """Test that draw_image works with different display dimensions."""
    one_row = ["Test"]
    many_rows = ["Test" * 100] * 100  # shouldn't affect image size
    for width, height in [(128, 64), (128, 128), (64, 32)]:
        image = utils.draw_image(width, height, one_row)
        assert image.size == (width, height)
        image = utils.draw_image(width, height, many_rows)
        assert image.size == (width, height)
