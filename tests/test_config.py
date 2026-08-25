"""Tests for the config module: schema, I/O, parsing, display helpers,
and module-level var exposure."""

import dataclasses
import importlib
import pathlib
from pathlib import Path
from typing import Literal

import pytest

from simoc_sam import config
from simoc_sam import defaults
from simoc_sam.config import (
    SimocConfig, get_field_type,
    get_schema, get_config, load_user_config, save_user_config,
    parse_value, format_value, print_all, print_one, print_defaults,
    generate_config,
)


@pytest.fixture(autouse=True)
def reload_config(tmp_path, monkeypatch):
    """Reload config with a clean tmp HOME before and after each test.

    Patching HOME here ensures every test starts from a blank-slate config
    (no real ~/.config/simoc-sam/config.toml leaks into the test suite).
    """
    monkeypatch.setenv('HOME', str(tmp_path))
    importlib.reload(config)
    yield
    importlib.reload(config)


@pytest.fixture
def user_config(tmp_path):
    """Create the config directory and return the config.toml path.

    HOME is already patched to tmp_path by the autouse reload_config fixture.
    """
    config_dir = tmp_path / '.config' / 'simoc-sam'
    config_dir.mkdir(parents=True)
    return config_dir / 'config.toml'



def test_default_vars():
    # All config vars must appear in exactly one of the lists below.
    unchanged_vars = [
        'humans', 'volume', 'sensors', 'sensor_read_delay',
        'display', 'display_refresh',
        'mqtt_host', 'mqtt_port', 'mqtt_secure', 'mqtt_reconnect_delay',
        'sio_host', 'sio_port', 'data_source', 'mqtt_topic_sub',
        'api_host', 'api_port',
        'verbose_sensor', 'verbose_mqtt', 'enable_jsonl_logging',
        'bno085_default_err_value', 'bno085_enabled_features',
    ]
    changed_vars = ['location', 'display_format']
    path_vars = sorted(SimocConfig._PATH_FIELDS)
    all_vars = set(unchanged_vars + path_vars + changed_vars)

    for var in dir(defaults):
        if var.startswith('_'):
            continue
        assert var in all_vars,     f'Untested config var: {var}'
        assert hasattr(config, var), f'config missing: {var}'
        assert hasattr(defaults, var)

        if var in unchanged_vars:
            assert getattr(config, var) == getattr(defaults, var)
        elif var in path_vars:
            default_path = getattr(defaults, var)
            config_path  = getattr(config, var)
            expected     = Path(default_path).expanduser().absolute()
            assert isinstance(default_path, str)
            assert isinstance(config_path, Path)
            assert config_path.is_absolute()
            assert '~' not in str(config_path)
            assert str(config_path) == str(expected)
        elif var == 'location':
            assert defaults.location is None
            assert config.location == 'testhost'
        elif var == 'display_format':
            assert config.display_format == defaults.display_format.strip()


def test_user_config_override(user_config):
    assert config.mqtt_host == defaults.mqtt_host
    assert config.location == 'testhost'
    user_config.write_text('mqtt_host = "overridden_host"\nlocation = "custom_location"\n')
    importlib.reload(config)
    assert config.mqtt_host == 'overridden_host'
    assert config.location == 'custom_location'
    # Falls back to defaults when config dir is absent
    import os
    os.environ['HOME'] = '/not/a/real/dir'
    importlib.reload(config)
    assert config.mqtt_host == defaults.mqtt_host
    assert config.location == 'testhost'


def test_path_variables_user_override(user_config, tmp_path):
    vars = sorted(SimocConfig._PATH_FIELDS)
    paths = ['/custom/certs', '/custom/dist', '/custom/logs',
             '/custom/data', '/custom/data/sensor_data.db']
    assert len(vars) == len(paths)
    user_config.write_text('\n'.join(f'{v} = {p!r}' for v, p in zip(vars, paths)))
    importlib.reload(config)
    for var, path in zip(vars, paths):
        value = getattr(config, var)
        assert isinstance(value, Path)
        assert str(value) == path


def test_path_conversion_and_expansion(user_config):
    user_config.write_text('log_dir = "logs"\ndata_dir = "~/my_data"\n')
    importlib.reload(config)
    for var in ['log_dir', 'data_dir']:
        value = getattr(config, var)
        assert isinstance(value, Path)
        assert value.is_absolute()


def test_config_warning_logs_without_jsonl(user_config, capsys):
    user_config.write_text('enable_jsonl_logging = false\ndata_source = "logs"\n')
    importlib.reload(config)
    assert 'Warning: JSONL logging is disabled' in capsys.readouterr().err



def test_simoc_config_defaults():
    cfg = SimocConfig()
    assert cfg.humans == 0
    assert cfg.volume == 0
    assert cfg.sensors == ['bme688', 'scd30', 'sgp30']
    assert cfg.sensor_read_delay == 10.0
    assert cfg.display == 'ssd1306'
    assert cfg.mqtt_host == 'localhost'
    assert cfg.mqtt_port == 1883
    assert cfg.mqtt_secure is False
    assert cfg.data_source == 'mqtt'
    assert cfg.api_port == 8082
    assert cfg.enable_jsonl_logging is True


def test_simoc_config_path_fields_are_expanded():
    cfg = SimocConfig()
    for fname in SimocConfig._PATH_FIELDS:
        val = getattr(cfg, fname)
        assert isinstance(val, Path),     f'{fname} should be a Path'
        assert val.is_absolute(),          f'{fname} should be absolute'
        assert '~' not in str(val),        f'{fname} should be expanded'


def test_simoc_config_path_from_string():
    cfg = SimocConfig(log_dir='/custom/logs', data_dir='~/mydata')
    assert str(cfg.log_dir) == '/custom/logs'
    assert '~' not in str(cfg.data_dir)
    assert cfg.data_dir.is_absolute()


def test_simoc_config_location_auto_set():
    cfg = SimocConfig()    # conftest patches gethostname → 'testhost1'
    assert cfg.location == 'testhost'


def test_simoc_config_location_override():
    assert SimocConfig(location='lab42').location == 'lab42'


def test_simoc_config_display_format_stripped():
    cfg = SimocConfig()
    assert not cfg.display_format.startswith('\n')
    assert not cfg.display_format.endswith('\n')


def test_simoc_config_display_refresh_validation(capsys):
    cfg = SimocConfig(display_refresh=-1.0)
    assert cfg.display_refresh == 1.0
    assert 'Warning' in capsys.readouterr().err


def test_simoc_config_data_source_validation(capsys):
    cfg = SimocConfig(data_source='invalid')
    assert cfg.data_source == 'logs'
    assert 'Warning' in capsys.readouterr().err


def test_simoc_config_jsonl_consistency_warning(capsys):
    SimocConfig(enable_jsonl_logging=False, data_source='logs')
    assert 'Warning' in capsys.readouterr().err


def test_simoc_config_constructor_override():
    cfg = SimocConfig(mqtt_host='remote.host', mqtt_port=9883)
    assert cfg.mqtt_host == 'remote.host'
    assert cfg.mqtt_port == 9883



def test_hint_to_ftype_primitives():
    assert get_field_type(bool, False)[0] == 'bool'
    assert get_field_type(int, 0)[0] == 'int'
    assert get_field_type(float, 0.0)[0] == 'float'
    assert get_field_type(str, 'x')[0] == 'str'


def test_hint_to_ftype_multiline_str():
    ftype, _ = get_field_type(str, 'line1\nline2')
    assert ftype == 'multiline_str'


def test_hint_to_ftype_nullable():
    ftype, opts = get_field_type(str | None, None)
    assert ftype == 'nullable_str'
    assert opts == ()


def test_hint_to_ftype_literal():
    ftype, opts = get_field_type(Literal['a', 'b', 'c'], 'a')
    assert ftype == 'literal'
    assert set(opts) == {'a', 'b', 'c'}


def test_hint_to_ftype_plain_list():
    ftype, opts = get_field_type(list[str], [])
    assert ftype == 'list'
    assert opts == ()


def test_hint_to_ftype_path():
    ftype, _ = get_field_type(pathlib.Path, pathlib.Path('~/foo'))
    assert ftype == 'str'



def test_get_schema_covers_all_fields():
    expected = {f.name for f in dataclasses.fields(SimocConfig) if not f.name.startswith('_')}
    assert set(get_schema().keys()) == expected


def test_get_schema_entries_have_required_keys():
    for name, info in get_schema().items():
        assert 'default' in info, f'{name}: missing default'
        assert 'type' in info, f'{name}: missing type'
        assert 'group' in info, f'{name}: missing group'
        assert 'options' in info, f'{name}: missing options'


def test_get_schema_literal_fields_have_options():
    schema = get_schema()
    # display options come from DISPLAY_DATA (whatever is registered in displays.toml)
    opts = schema['display']['options']
    assert 'ssd1306' in opts
    assert 'ssd1327' in opts
    # data_source is a fixed Literal — always exactly these two choices
    assert set(schema['data_source']['options']) == {'mqtt', 'logs'}


def test_get_schema_list_fields():
    schema = get_schema()
    assert schema['sensors']['type'] == 'list'
    assert 'bme688' in schema['sensors']['options']
    assert schema['bno085_enabled_features']['type'] == 'list'


def test_get_schema_path_defaults_are_strings():
    schema = get_schema()
    for fname in SimocConfig._PATH_FIELDS:
        assert isinstance(schema[fname]['default'], str), \
            f'{fname}: schema default should be str'


def test_get_schema_groups():
    schema = get_schema()
    assert schema['sensors']['group']   == 'Sensors'
    assert schema['display']['group']   == 'Display'
    assert schema['mqtt_host']['group'] == 'MQTT'
    assert schema['log_dir']['group']   == 'Verbosity and logging'


def test_get_schema_is_cached():
    assert get_schema() is get_schema()


def test_generate_config_template_is_valid_toml():
    import tomllib
    result = tomllib.loads(generate_config())
    assert result == {}  # all lines are commented out


def test_generate_config_template_contains_all_fields():
    template = generate_config()
    for name in get_schema():
        assert name in template, f'{name!r} missing from config template'


def test_generate_config_skips_none_override():
    # None means "unset" -- TOML has no null, so it must not be serialized
    result = generate_config({'location': None})
    import tomllib
    assert tomllib.loads(result) == {}
    assert '# location' in result   # falls back to the commented default line


def test_load_user_config_missing(user_config):
    assert load_user_config() == {}


def test_load_user_config_invalid_toml(user_config):
    user_config.write_text('this is not [valid toml')
    with pytest.raises(ValueError, match='Invalid TOML'):
        load_user_config()
    user_config.unlink()


def test_save_and_load_roundtrip(user_config):
    overrides = {'mqtt_host': 'remote.host', 'mqtt_port': 1884,
                 'sensors': ['scd30', 'bme688'], 'mqtt_secure': False}
    save_user_config(overrides)
    loaded = load_user_config()
    assert loaded['mqtt_host']   == 'remote.host'
    assert loaded['mqtt_port']   == 1884
    assert loaded['sensors']     == ['scd30', 'bme688']
    assert loaded['mqtt_secure'] is False


def test_save_user_config_creates_directory(tmp_path):
    save_user_config({'mqtt_port': 9999})
    assert (tmp_path / '.config' / 'simoc-sam' / 'config.toml').exists()


def test_save_user_config_writes_full_template(user_config):
    save_user_config({'mqtt_port': 9999})
    content = user_config.read_text()
    assert 'mqtt_port = 9999' in content   # override is live (not commented)
    assert '# sensors' in content          # other fields remain as commented template
    import tomllib
    assert tomllib.loads(content) == {'mqtt_port': 9999}


def test_save_user_config_has_comment_header(user_config):
    save_user_config({'mqtt_port': 9999})
    assert user_config.read_text().startswith('#')



def test_get_config_returns_simoc_config(user_config):
    # type name check — robust against importlib.reload() redefining the class
    assert type(get_config()).__name__ == 'SimocConfig'


def test_get_config_applies_overrides(user_config):
    save_user_config({'mqtt_host': 'custom.host', 'mqtt_port': 5555})
    cfg = get_config()
    assert cfg.mqtt_host == 'custom.host'
    assert cfg.mqtt_port == 5555


def test_get_config_ignores_unknown_keys(user_config):
    user_config.write_text('mqtt_host = "ok"\nunknown_key = "ignored"\n')
    cfg = get_config()
    assert cfg.mqtt_host == 'ok'


def test_get_config_empty_file_uses_defaults(user_config):
    user_config.write_text('')
    assert get_config().mqtt_host == 'localhost'



def test_parse_value_int():
    assert parse_value('1884', get_schema()['mqtt_port']) == 1884


def test_parse_value_float():
    assert parse_value('5.5', get_schema()['sensor_read_delay']) == 5.5


def test_parse_value_bool_truthy():
    s = get_schema()['mqtt_secure']
    for v in ('true', 'yes', '1', 'on'):
        assert parse_value(v, s) is True


def test_parse_value_bool_falsy():
    s = get_schema()['mqtt_secure']
    for v in ('false', 'no', '0', 'off'):
        assert parse_value(v, s) is False


def test_parse_value_bool_invalid():
    with pytest.raises(ValueError, match='expected true/false'):
        parse_value('maybe', get_schema()['mqtt_secure'])


def test_parse_value_literal_valid():
    assert parse_value('ssd1327', get_schema()['display']) == 'ssd1327'


def test_parse_value_literal_invalid():
    with pytest.raises(ValueError, match='invalid value'):
        parse_value('notadisplay', get_schema()['display'])


def test_parse_value_list_literal_valid():
    assert parse_value('scd30,bme688', get_schema()['sensors']) == ['scd30', 'bme688']


def test_parse_value_list_literal_whitespace():
    assert parse_value(' scd30 , bme688 ', get_schema()['sensors']) == ['scd30', 'bme688']


def test_parse_value_list_literal_invalid():
    with pytest.raises(ValueError, match='invalid values'):
        parse_value('scd30,not_a_sensor', get_schema()['sensors'])


def test_parse_value_nullable_empty():
    assert parse_value('', get_schema()['location']) is None


def test_parse_value_nullable_value():
    assert parse_value('lab1', get_schema()['location']) == 'lab1'


def test_parse_value_str():
    assert parse_value('custom.host', get_schema()['mqtt_host']) == 'custom.host'



def test_fmt_list():         assert format_value(['a', 'b', 'c']) == 'a, b, c'
def test_fmt_empty_list():   assert format_value([]) == '(empty list)'
def test_fmt_multiline():    assert 'multiline' in format_value('line1\nline2')
def test_fmt_none():         assert format_value(None) == '(none)'
def test_fmt_scalars():
    assert format_value('hello') == 'hello'
    assert format_value(42)      == '42'
    assert format_value(3.14)    == '3.14'



def test_print_all_shows_customised_marker(user_config, capsys):
    save_user_config({'mqtt_port': 9999})
    print_all(get_schema(), load_user_config())
    out = capsys.readouterr().out
    assert 'mqtt_port' in out
    assert '9999' in out
    assert '*' in out


def test_print_all_no_marker_when_clean(capsys):
    print_all(get_schema(), {})
    assert '*' not in capsys.readouterr().out


def test_print_one_shows_override_and_default(user_config, capsys):
    save_user_config({'mqtt_port': 9999})
    print_one('mqtt_port', get_schema(), load_user_config())
    out = capsys.readouterr().out
    assert '9999' in out
    assert 'default' in out


def test_print_one_default_state(capsys):
    print_one('mqtt_port', get_schema(), {})
    out = capsys.readouterr().out
    assert '1883' in out
    assert 'default' in out


def test_print_one_shows_options_for_literal(capsys):
    print_one('display', get_schema(), {})
    out = capsys.readouterr().out
    assert 'ssd1306' in out
    assert 'options' in out


def test_print_defaults_covers_all_fields(capsys):
    print_defaults(get_schema())
    out = capsys.readouterr().out
    for name in get_schema():
        assert name in out, f'{name} missing from print_defaults output'
