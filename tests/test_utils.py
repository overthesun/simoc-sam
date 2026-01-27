"""Tests for simoc_sam.utils module."""

from unittest.mock import MagicMock, patch

import pytest

from simoc_sam import utils
from simoc_sam.sensors import utils as sensor_utils

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
