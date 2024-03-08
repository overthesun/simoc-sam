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
    def check(args, all, sensor, mqtt, sio):
        args = utils.parse_args(args)
        assert args.verbose is all
        assert args.verbose_sensor is sensor
        assert args.verbose_mqtt is mqtt
        assert args.verbose_sio is sio
    check([], all=False, sensor=False, mqtt=False, sio=False)
    check(['-v'], all=True, sensor=True, mqtt=True, sio=True)
    check(['--verbose'], all=True, sensor=True, mqtt=True, sio=True)
    check(['--verbose-sensor'], all=False, sensor=True, mqtt=False, sio=False)
    check(['--verbose-mqtt'], all=False, sensor=False, mqtt=True, sio=False)
    check(['--verbose-sio'], all=False, sensor=False, mqtt=False, sio=True)


def test_parse_args_sio_mqtt(capsys):
    with pytest.raises(SystemExit) as exc:
        utils.parse_args(['--mqtt', '--sio'])
    captured = capsys.readouterr()
    assert 'can not be used together' in captured.err


# mqtt

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


#sio

def test_parse_args_sio_default_ports():
    args = utils.parse_args(['--sio'])
    assert args.host == 'localhost'
    assert args.port == 8081

def test_parse_args_sio_custom_ports():
    args = utils.parse_args(['--sio', '--host=test', '--port=1234'])
    assert args.host == 'test'
    assert args.port == 1234

def test_parse_args_sio_envvar_ports(monkeypatch):
    monkeypatch.setenv('SIOSERVER_ADDR', 'test:4321')
    args = utils.parse_args(['--sio'])
    assert args.host == 'test'
    assert args.port == 4321
