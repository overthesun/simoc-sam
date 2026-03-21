import importlib
from pathlib import Path

import pytest

from simoc_sam import config
from simoc_sam import defaults


@pytest.fixture(autouse=True)
def reload_config():
    """Reload config before and after each test to ensure clean state."""
    importlib.reload(config)
    yield
    importlib.reload(config)


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
    # all config vars should be included in one of the 3 lists below and tested
    unchanged_vars = [
        'humans', 'volume', 'sensors', 'sensor_read_delay',
        'display', 'display_refresh',
        'mqtt_host', 'mqtt_port', 'mqtt_secure', 'mqtt_reconnect_delay',
        'sio_host', 'sio_port', 'data_source', 'mqtt_topic_sub',
        'verbose_sensor', 'verbose_mqtt', 'enable_jsonl_logging',
    ]
    changed_vars = ['location', 'display_format']
    path_vars = config._path_vars
    all_vars = set(unchanged_vars + path_vars + changed_vars)
    for var in dir(defaults):
        if var.startswith("_"):
            continue  # skip private/special vars
        assert var in all_vars, f'Untested config var: {var}'
        assert hasattr(config, var)
        assert hasattr(defaults, var)
        if var in unchanged_vars:
            assert getattr(config, var) is getattr(defaults, var)
        elif var in path_vars:
            default_path = getattr(defaults, var)
            config_path = getattr(config, var)
            expected_path = Path(default_path).expanduser().absolute()
            assert isinstance(default_path, str)  # always a str
            assert isinstance(config_path, Path)  # always converted to Path
            assert config_path.is_absolute()
            assert '~' not in str(config_path)  # should be expanded
            assert str(config_path) == str(expected_path)
        elif var == 'location':
            assert defaults.location is None
            assert config.location == 'testhost'
        elif var == 'display_format':
            assert config.display_format == defaults.display_format.strip()


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
    vars = config._path_vars
    paths = ['/custom/certs', '/custom/dist', '/custom/logs']
    config_text = '\n'.join(f'{var} = {path!r}' for var, path in zip(vars, paths))
    user_config.write_text(config_text)
    importlib.reload(config)
    # verify they are converted to Path objects
    for var, path in zip(vars, paths):
        value = getattr(config, var)
        assert isinstance(value, Path)
        assert str(value) == path

def test_path_conversion_and_expansion(user_config):
    """Test that path variables are converted to absolute paths."""
    user_config.write_text('log_dir = "logs"\ndata_dir = "~/my_data"\n')
    importlib.reload(config)
    for var in ['log_dir', 'data_dir']:
        value = getattr(config, var)
        assert isinstance(value, Path)
        assert value.is_absolute()
        assert str(value).startswith((str(Path.home()), str(Path.cwd())))

def test_config_warning_logs_without_jsonl(user_config, capsys):
    """Test that config warns if data_source is 'logs' but logging is disabled."""
    user_config.write_text('enable_jsonl_logging = False\ndata_source = "logs"\n')
    importlib.reload(config)
    captured = capsys.readouterr()
    assert 'Warning: JSONL logging is disabled' in captured.out
