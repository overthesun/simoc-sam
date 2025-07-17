import pytest

from simoc_sam.sensors import utils


def test_delay():
    args = utils.parse_args([])
    assert args.delay == 10
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
    check([], all=False, sensor=False, mqtt=False)
    check(['-v'], all=True, sensor=True, mqtt=True)
    check(['--verbose'], all=True, sensor=True, mqtt=True)
    check(['--verbose-sensor'], all=False, sensor=True, mqtt=False)
    check(['--verbose-mqtt'], all=False, sensor=False, mqtt=True)


def test_parse_args_mqtt_default_ports():
    args = utils.parse_args(['--mqtt'])
    assert args.host == 'sambridge1'
    assert args.port == 1883

def test_parse_args_mqtt_custom_ports():
    args = utils.parse_args(['--mqtt', '--host=test', '--port=1234'])
    assert args.host == 'test'
    assert args.port == 1234

def test_parse_args_mqtt_envvar_ports(monkeypatch):
    monkeypatch.setenv('MQTTSERVER_ADDR', 'test:4321')
    args = utils.parse_args(['--mqtt'])
    assert args.host == 'test'
    assert args.port == 4321
