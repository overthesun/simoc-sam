import pytest

from simoc_sam.sensors import utils
from simoc_sam import config


def test_delay():
    # Test that config default is used when no args provided
    args = utils.parse_args([])
    assert args.delay == config.sensor_read_delay
    # Test that command line args override config defaults
    args = utils.parse_args(['-d', '5'])
    assert args.delay == 5.0
    args = utils.parse_args(['--read-delay', '5.5'])
    assert args.delay == 5.5


def test_verbose():
    def check(args, all, sensor, mqtt):
        args = utils.parse_args(args)
        assert args.verbose is all
        assert args.verbose_sensor is sensor
        assert args.verbose_mqtt is mqtt
    # Test that config defaults are used when no verbose flags provided
    check([], all=False, sensor=config.verbose_sensor, mqtt=config.verbose_mqtt)
    # Test that verbose flags override config defaults
    check(['-v'], all=True, sensor=True, mqtt=True)
    check(['--verbose'], all=True, sensor=True, mqtt=True)
    check(['--verbose-sensor'], all=False, sensor=True, mqtt=False)
    check(['--verbose-mqtt'], all=False, sensor=False, mqtt=True)


def test_parse_args_mqtt_default_ports():
    """Test that MQTT uses config defaults when no host/port specified."""
    args = utils.parse_args(['--mqtt'])
    assert args.host == config.mqtt_host
    assert args.port == config.mqtt_port


def test_parse_args_mqtt_custom_ports():
    """Test that custom host/port override config defaults."""
    args = utils.parse_args(['--mqtt', '--host=test', '--port=1234'])
    assert args.host == 'test'
    assert args.port == 1234


def test_parse_args_mqtt_with_partial_override():
    """Test that partial overrides work correctly."""
    # Only override host, port should use config default
    args = utils.parse_args(['--mqtt', '--host=customhost'])
    assert args.host == 'customhost'
    assert args.port == config.mqtt_port
    # Only override port, host should use config default
    args = utils.parse_args(['--mqtt', '--port=9999'])
    assert args.host == config.mqtt_host
    assert args.port == 9999


def test_parse_args_no_mqtt():
    """Test that when --mqtt is not used, host/port are None by default."""
    args = utils.parse_args([])
    assert args.host is None
    assert args.port is None


def test_parse_args_mqtt_topic_sub():
    """Test that MQTT topic sub uses config default when not specified."""
    args = utils.parse_args([])
    assert args.mqtt_topic_sub == config.mqtt_topic_sub
    args = utils.parse_args(['--mqtt-topic-sub', 'test/#'])
    assert args.mqtt_topic_sub == 'test/#'
