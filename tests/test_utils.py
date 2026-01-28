"""Tests for simoc_sam.utils module."""

import asyncio
import pathlib

from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from simoc_sam import utils
from simoc_sam.sensors import utils as sensor_utils
from simoc_sam.sensors.basesensor import get_sensor_id
from conftest import wait_until, terminate_task


@pytest.fixture
def mock_board():
    """Fixture that mocks the board module."""
    mock_board = MagicMock()
    mock_board.SCL = MagicMock()
    mock_board.SDA = MagicMock()
    with patch.object(sensor_utils, 'import_board', return_value=mock_board):
        yield mock_board

@pytest.fixture
def mock_busio(mock_board):
    """Fixture that mocks the busio module."""
    mock_busio = MagicMock()
    with patch.object(sensor_utils, 'import_busio', return_value=mock_busio):
        yield mock_busio

@pytest.fixture
def mock_i2c(mock_busio):
    """Fixture that mocks the I2C object."""
    mock_i2c = MagicMock()
    mock_busio.I2C.return_value = mock_i2c
    yield mock_i2c

@pytest.fixture(autouse=True)
def clear_i2c_cache():
    """Automatically clear the I2C cache before each test."""
    utils._i2c_cache.clear()


def test_get_i2c_addresses_init_error(mock_busio):
    """Test that RuntimeError is raised when I2C initialization fails."""
    for exception in [AttributeError, ValueError]:
        mock_busio.I2C.side_effect = exception()
        with pytest.raises(RuntimeError, match='I2C scan failed'):
            utils.get_i2c_addresses()

def test_get_i2c_addresses_scan_failure(mock_i2c):
    """Test that RuntimeError is raised when I2C scan fails."""
    for exception in [OSError, RuntimeError]:
        mock_i2c.scan.side_effect = exception()
        with pytest.raises(RuntimeError, match='I2C scan failed'):
            utils.get_i2c_addresses()


def test_get_i2c_names_known_sensor(mock_i2c):
    """Test that known sensors are correctly identified."""
    mock_i2c.scan.return_value = [0x61, 0x58, 0x29]
    result = utils.get_i2c_names()
    assert result == ['tsl2591', 'sgp30', 'scd30']

def test_get_i2c_names_unknown_address(mock_i2c):
    """Test that unknown addresses return '<unknown>'."""
    unknown_addr = 0x99  # Not in sensors.toml
    mock_i2c.scan.return_value = [unknown_addr]
    result = utils.get_i2c_names()
    assert result == ['<unknown>']

def test_get_i2c_names_empty(mock_i2c):
    """Test that empty list is returned when no devices found."""
    mock_i2c.scan.return_value = []
    result = utils.get_i2c_names()
    assert result == []


def test_i2c_to_device_name_known_sensor(mock_i2c):
    """Test that known sensor is correctly identified by address."""
    result = utils.i2c_to_device_name(0x61)  # scd30
    assert result == 'scd30'

def test_i2c_to_device_name_unknown_address(mock_i2c):
    """Test that unknown address returns '<unknown>'."""
    result = utils.i2c_to_device_name(0x99)  # Not in sensors.toml
    assert result == '<unknown>'

@pytest.mark.parametrize("chip_id_register,chip_id,expected_name,should_warn", [
    (0xD0, 0x61, 'bme688', False),  # BME688 register with BME688 chip ID
    (0x00, 0x50, 'bmp388', False),  # BMP388 register with BMP388 chip ID
    (0xD0, 0x50, 'bme688', True),   # Wrong chip ID - warns and falls back
    (0x00, 0x61, 'bme688', True),   # Wrong chip ID - warns and falls back
])
def test_i2c_to_device_name_multiple_candidates(
    mock_i2c, chip_id_register, chip_id, expected_name, should_warn):
    """Test chip ID disambiguation for sensors sharing address 0x77."""
    addr = 0x77  # Shared by BME688 and BMP388
    # Simulate device responding with the specified chip ID
    def mock_read(address, reg_bytes, result):
        if address == addr and reg_bytes == bytes([chip_id_register]):
            result[0] = chip_id
    mock_i2c.writeto_then_readfrom.side_effect = mock_read
    if should_warn:
        with pytest.warns(RuntimeWarning, match="Failed to disambiguate sensor"):
            result = utils.i2c_to_device_name(addr)
    else:
        result = utils.i2c_to_device_name(addr)
    assert result == expected_name


# Tests for async read_jsonl_file functionality

@pytest.fixture
def jsonl_log_path(temp_log_dir):
    """Create a JSONL log file path using sensor ID format."""
    sensor_id = get_sensor_id('test', sep='_')
    return temp_log_dir / f"{sensor_id}.jsonl"

@asynccontextmanager
async def wait_until_eof_seek():
    """Context manager that waits until a file seeks to EOF."""
    eof_reached = {'value': False}
    original_open = open
    def patched_open(*args, **kwargs):
        file_obj = original_open(*args, **kwargs)
        original_seek = file_obj.seek
        def seek_wrapper(cookie, whence=0):
            result = original_seek(cookie, whence)
            if whence == 2:  # SEEK_END
                eof_reached['value'] = True
            return result
        file_obj.seek = seek_wrapper
        return file_obj
    with patch('simoc_sam.utils.open', patched_open):
        yield
        await wait_until(lambda: eof_reached['value'])

@asynccontextmanager
async def wait_until_file_checked():
    """Context manager that waits until Path.exists() is called."""
    exists_checked = {'value': False}
    original_exists = pathlib.Path.exists
    def exists_wrapper(self):
        exists_checked['value'] = True
        return original_exists(self)
    with patch.object(pathlib.Path, 'exists', exists_wrapper):
        yield
        await wait_until(lambda: exists_checked['value'])

@pytest.mark.asyncio
async def test_read_jsonl_file_skips_invalid_json(jsonl_log_path, capfd):
    """Test that read_jsonl_file skips invalid JSON and continues."""
    # create file with initial content (skipped by tail -f)
    with open(jsonl_log_path, 'w') as f:
        f.write('{"n": -2}\n{"n": -1}\n')
    readings = []
    async def collect_readings():
        async for line in utils.read_jsonl_file(jsonl_log_path):
            readings.append(line)
    # create task and wait until read_jsonl_file seeks to EOF
    async with wait_until_eof_seek():
        read_task = asyncio.create_task(collect_readings())
    # append valid, invalid, and valid JSON
    with open(jsonl_log_path, 'a') as f:
        f.write('{"n": 0}\ninvalid json\n{"n": 1}\n')
    # wait for read_jsonl_file to read and yield the valid lines
    await wait_until(lambda: len(readings) >= 2)
    # verify only valid JSON was yielded
    assert len(readings) == 2
    assert readings[0] == {'n': 0}
    assert readings[1] == {'n': 1}
    # verify error was printed
    captured = capfd.readouterr()
    assert 'Error parsing JSON' in captured.out
    # clean up
    await terminate_task(read_task)

@pytest.mark.asyncio
async def test_read_jsonl_file_waits_for_file(jsonl_log_path):
    """Test that read_jsonl_file waits for file creation."""
    readings = []
    async def collect_readings():
        async for line in utils.read_jsonl_file(jsonl_log_path):
            readings.append(line)
    # start reading before file exists and wait until it checks for the file
    async with wait_until_file_checked():
        read_task = asyncio.create_task(collect_readings())
    # create file with initial content (skipped)
    with open(jsonl_log_path, 'w') as f:
        f.write('{"n": -2}\n{"n": -1}\n')
    # wait until read_jsonl_file detects the file and seeks to EOF
    async with wait_until_eof_seek():
        pass
    # append new data
    with open(jsonl_log_path, 'a') as f:
        f.write('{"n": 0}\n')
    # wait for read_jsonl_file to read and yield the new line
    await wait_until(lambda: len(readings) >= 1)
    # verify reading was captured
    assert len(readings) == 1
    assert readings[0] == {'n': 0}
    # clean up
    await terminate_task(read_task)

@pytest.mark.asyncio
async def test_read_jsonl_file_tails_appended_lines(jsonl_log_path):
    """Test that read_jsonl_file acts like tail -f (skips existing content)."""
    # create file with initial content
    with open(jsonl_log_path, 'w') as f:
        f.write('{"n": -2}\n{"n": -1}\n')
    readings = []
    async def collect_readings():
        async for line in utils.read_jsonl_file(jsonl_log_path):
            readings.append(line)
    # create task and wait until read_jsonl_file seeks to EOF
    async with wait_until_eof_seek():
        read_task = asyncio.create_task(collect_readings())
    # append new lines
    with open(jsonl_log_path, 'a') as f:
        f.write('{"n": 0}\n{"n": 1}\n')
    # wait for read_jsonl_file to read and yield the new lines
    await wait_until(lambda: len(readings) >= 2)
    # verify only new lines were read, not initial content
    assert len(readings) == 2
    assert readings[0] == {'n': 0}
    assert readings[1] == {'n': 1}
    # clean up
    await terminate_task(read_task)
