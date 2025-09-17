import importlib
from pathlib import Path

import pytest

from simoc_sam import config
from simoc_sam import defaults


@pytest.fixture
def user_config(tmp_path, monkeypatch):
    """Fixture that sets up user config directory and monkeypatches HOME."""
    user_config_dir = tmp_path / '.config' / 'simoc-sam'
    user_config_dir.mkdir(parents=True)
    user_config_path = user_config_dir / 'config.py'
    # set the home to tmp_path so that Path().home() points to tmp_path
    monkeypatch.setenv('HOME', str(tmp_path))
    return user_config_path


def test_default_vars():
    vars = [
        'humans', 'volume', 'sensors', 'sensor_read_delay', 'mqtt_host',
        'mqtt_port', 'mqtt_secure', 'mqtt_certs_dir', 'mqtt_reconnect_delay',
        'sio_host', 'sio_port', 'mqtt_topic_sub', 'simoc_web_port', 'simoc_web_dist_dir',
        'verbose_sensor', 'verbose_mqtt', 'enable_jsonl_logging', 'log_dir',
    ]
    for var in vars:
        assert hasattr(config, var)
        assert hasattr(defaults, var)
        assert getattr(config, var) is getattr(defaults, var)
    # location is set from hostname when None
    assert defaults.location is None
    assert config.location == 'testhost'


def test_user_config_override(user_config, monkeypatch):
    from simoc_sam import defaults
    assert config.mqtt_host is defaults.mqtt_host
    assert config.location == 'testhost'
    # create an user config that overrides the mqtt_host
    user_config.write_text('mqtt_host = "overridden_host"\n'
                           'location = "custom_location"\n')
    importlib.reload(config)
    assert config.mqtt_host == "overridden_host"
    assert config.location == "custom_location"
    # test that it falls back on the default
    monkeypatch.setenv('HOME', '/not/a/real/dir')
    importlib.reload(config)
    assert config.mqtt_host is defaults.mqtt_host
    assert config.location == 'testhost'
    # test load_user_config directly
    config.load_user_config(user_config)
    assert config.mqtt_host == "overridden_host"


def test_path_variables_user_override(user_config):
    """Test that string paths are converted to Path objects."""
    # create user config that sets path vars with strings
    user_config.write_text('mqtt_certs_dir = "/custom/certs"\n'
                           'simoc_web_dist_dir = "/custom/dist"\n'
                           'log_dir = "/custom/logs"\n')
    importlib.reload(config)
    # verify they are converted to Path objects
    path_vars = ['mqtt_certs_dir', 'simoc_web_dist_dir', 'log_dir']
    expected_values = ['/custom/certs', '/custom/dist', '/custom/logs']
    for var, expected in zip(path_vars, expected_values):
        value = getattr(config, var)
        assert isinstance(value, Path)
        assert str(value) == expected
