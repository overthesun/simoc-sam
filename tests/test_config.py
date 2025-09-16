import importlib

from simoc_sam import config
from simoc_sam import defaults


def test_default_vars():
    vars = [
        'humans', 'volume', 'sensors', 'sensor_read_delay',
        'mqtt_host', 'mqtt_port', 'mqtt_reconnect_delay', 'sio_host', 'sio_port',
        'mqtt_topic_sub', 'simoc_web_port', 'simoc_web_dist_dir',
        'verbose_sensor', 'verbose_mqtt', 'enable_jsonl_logging', 'log_dir',
    ]
    for var in vars:
        assert hasattr(config, var)
        assert hasattr(defaults, var)
        assert getattr(config, var) is getattr(defaults, var)
    # location is set from hostname when None
    assert defaults.location is None
    assert config.location == 'testhost'


def test_user_config_override(tmp_path, monkeypatch):
    from simoc_sam import defaults
    assert config.mqtt_host is defaults.mqtt_host
    assert config.location == 'testhost'
    # create an user config that overrides the mqtt_host
    user_config_dir = tmp_path / '.config' / 'simoc-sam'
    user_config_dir.mkdir(parents=True)
    user_config_path = user_config_dir / 'config.py'
    user_config_path.write_text('mqtt_host = "overridden_host"\n'
                                'location = "custom_location"\n')
    # Monkeypatch $HOME to tmp_path to test user config loading
    monkeypatch.setenv('HOME', str(tmp_path))
    importlib.reload(config)
    assert config.mqtt_host == "overridden_host"
    assert config.location == "custom_location"
    # test that it falls back on the default
    monkeypatch.setenv('HOME', '/not/a/real/dir')
    importlib.reload(config)
    assert config.mqtt_host is defaults.mqtt_host
    assert config.location == 'testhost'
    # test load_user_config directly
    config.load_user_config(user_config_path)
    assert config.mqtt_host == "overridden_host"
