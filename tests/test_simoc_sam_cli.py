"""Tests for simoc-sam CLI argument parsing and decorators."""

import pathlib
import importlib.util
from unittest.mock import patch, MagicMock, call, create_autospec

import pytest

# Import the module (this will be simoc-sam.py)
parent_dir = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("simoc_sam_cli", parent_dir / "simoc-sam.py")
simoc_sam_cli = importlib.util.module_from_spec(spec)

# Mock the imports that might not be available in test environment
with patch.dict('sys.modules', {
    'jinja2': MagicMock(),
    'simoc_sam': MagicMock(),
    'simoc_sam.config': MagicMock(),
}):
    spec.loader.exec_module(simoc_sam_cli)


@pytest.fixture
def clean_commands():
    """Reset COMMANDS dict between tests."""
    original_commands = simoc_sam_cli.COMMANDS.copy()
    simoc_sam_cli.COMMANDS.clear()
    yield
    simoc_sam_cli.COMMANDS = original_commands


@pytest.fixture
def mock_config(user_config):
    """Patch `simoc_config` with a fresh mock, isolated per test, with
    config_path() wired to a real (initially empty) config.toml path."""
    with patch.object(simoc_sam_cli, 'simoc_config') as mock:
        mock.config_path.return_value = user_config
        yield mock


def test_cmd_decorator(clean_commands):
    """Test that @cmd decorator adds function to COMMANDS dict."""
    @simoc_sam_cli.cmd
    def test_func():
        """Test function."""
        return True

    assert 'test_func' in simoc_sam_cli.COMMANDS
    assert simoc_sam_cli.COMMANDS['test_func'] is test_func


def test_parser_positional_args():
    """Test that positional args are parsed into named attributes."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['setup-hotspot', 'wlan0', 'MyNetwork', 'password123'])

    assert args.cmd == 'setup-hotspot'
    assert args.interface == 'wlan0'
    assert args.ssid == 'MyNetwork'
    assert args.password == 'password123'


def test_parser_named_args():
    """Test that --flag=value args are accepted for optional params."""
    parser = simoc_sam_cli.create_parser()
    # --flag is registered as a hidden named arg sharing the same dest as positional
    args = parser.parse_args(['setup-hotspot', '--interface=wlan0', '--ssid=MyNetwork'])

    assert args.cmd == 'setup-hotspot'
    assert args.interface == 'wlan0'
    assert args.ssid == 'MyNetwork'


def test_parser_mixed_args():
    """Test positional and --flag= args together."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['setup-hotspot', 'wlan0', '--password=secret'])

    assert args.cmd == 'setup-hotspot'
    assert args.interface == 'wlan0'
    assert args.password == 'secret'


def test_parser_spaces_in_args():
    """Test that spaces in positional arg values are preserved."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['setup-hotspot', 'wlan 0', 'My Network'])

    assert args.interface == 'wlan 0'
    assert args.ssid == 'My Network'


def test_parser_help_shows_commands(capsys):
    """Test that top-level --help lists all registered commands."""
    parser = simoc_sam_cli.create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['--help'])
    out = capsys.readouterr().out
    # Spot-check a few commands from different parts of the file
    assert 'create-venv' in out
    assert 'setup-hotspot' in out
    assert 'setup-sensors' in out
    assert 'services-info' in out


def test_parser_bool_keyword_only_conversion():
    """Test that boolean keyword-only flags are properly converted from strings.

    Without type= on the argparse argument, '--exclude-venv=False' would store
    the string 'False', which is truthy and silently ignored.
    """
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['copy-repo', 'pi@host', '--exclude-venv=False'])
    assert args.exclude_venv is False
    assert isinstance(args.exclude_venv, bool)

    args = parser.parse_args(['copy-repo', 'pi@host', '--exclude-venv=True'])
    assert args.exclude_venv is True

    args = parser.parse_args(['copy-repo', 'pi@host', '--exclude-git=0'])
    assert args.exclude_git is False


def test_subcommand_help_shows_description(capsys):
    """Test that a subcommand's --help shows docstring and positional args."""
    parser = simoc_sam_cli.create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['setup-hotspot', '--help'])
    out = capsys.readouterr().out
    # Docstring should appear as description
    assert 'Setup a hotspot' in out
    # Positional args should appear as lowercase metavars (matching the --flag names)
    assert 'interface' in out
    assert 'ssid' in out
    assert 'password' in out
    # Named --flags for these params should NOT appear in help (they're hidden)
    assert '--interface' not in out
    assert '--ssid' not in out
    assert '--password' not in out


def test_main_keyword_only_not_positional(clean_commands):
    """Test that KEYWORD_ONLY params (after *) are never assigned from positional args."""
    def test_cmd(target, *, exclude_venv=True, exclude_git=True):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.cmd(mock_cmd)

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'pi@rpi.local']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # target is a required positional — passed positionally, not as a keyword
    mock_cmd.assert_called_once_with('pi@rpi.local')


def test_main_required_positional_not_keyword_only(clean_commands):
    """Test that required KEYWORD_ONLY params (no default) are rejected.

    Guards the call_args simplification: param.default is empty iff the param
    is a required positional (KEYWORD_ONLY with empty default raises TypeError).
    """
    def test_cmd(pos_arg, *, kw_arg):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.cmd(mock_cmd)

    with pytest.raises(TypeError, match='keyword-only'):
        simoc_sam_cli.create_parser()


def test_main_positional_args_only(clean_commands):
    """Test that positional arguments are passed as keyword args to the function."""
    def test_cmd(interface=None, ssid=None, password='default123'):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.cmd(mock_cmd)

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'wlan0', 'MyNetwork']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    mock_cmd.assert_called_once_with(interface='wlan0', ssid='MyNetwork', password='default123')


def test_main_named_args_only(clean_commands):
    """Test that --flag=value args are correctly passed to the function."""
    def test_cmd(interface=None, password='default123'):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.cmd(mock_cmd)

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', '--interface=wlan2', '--password=secret']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    mock_cmd.assert_called_once_with(interface='wlan2', password='secret')


def test_main_mixed_positional_and_named(clean_commands):
    """Test that positional and --flag=value args can be mixed freely."""
    def test_cmd(interface=None, ssid=None, password='default123'):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.cmd(mock_cmd)

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'wlan0', '--password=mysecret']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # interface from positional, ssid uses its default (None), password from --flag
    mock_cmd.assert_called_once_with(interface='wlan0', ssid=None, password='mysecret')


def test_main_defaults_passed_explicitly(clean_commands):
    """Test that optional params are always passed explicitly with their defaults.

    The --flag registration always has default=param.default, so args.X is always
    set even when not provided on the command line.
    """
    def test_cmd(interface='wlan0', password='default123'):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.cmd(mock_cmd)

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    mock_cmd.assert_called_once_with(interface='wlan0', password='default123')


@patch('os.geteuid', return_value=1000)  # Not root
@patch('subprocess.run')
def test_needs_root_not_root_positional_args(mock_run, mock_geteuid):
    """Test needs_root decorator re-invokes with sudo when not root."""
    mock_run.return_value = MagicMock(returncode=0)

    @simoc_sam_cli.needs_root
    def test_func(interface, ssid, password='default'):
        return True

    result = test_func('wlan0', 'MySSID', password='secret')

    assert result is True
    mock_run.assert_called_once()

    # Check the command that was executed
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == 'sudo'
    assert '--preserve-env=HOME' in cmd
    assert 'test-func' in cmd
    # interface and ssid are required positionals — passed positionally, not as flags
    assert 'wlan0' in cmd
    assert 'MySSID' in cmd
    # password is an explicit kwarg — passed as --flag=value
    assert '--password=secret' in cmd


@patch('os.geteuid', return_value=1000)  # Not root
@patch('subprocess.run')
def test_needs_root_skips_none_values(mock_run, mock_geteuid):
    """Test needs_root decorator skips None values when building command."""
    mock_run.return_value = MagicMock(returncode=0)

    @simoc_sam_cli.needs_root
    def test_func(interface=None, ssid=None, password='default'):
        return True

    result = test_func(interface='wlan0', ssid=None, password='secret')

    assert result is True
    mock_run.assert_called_once()

    # Check the command that was executed
    cmd = mock_run.call_args[0][0]
    assert '--interface=wlan0' in cmd
    assert '--password=secret' in cmd
    # ssid should NOT be in the command because it's None
    assert not any('--ssid' in arg for arg in cmd)


@patch('os.geteuid', return_value=1000)  # Not root
@patch('subprocess.run')
def test_needs_root_required_args_passed_positionally(mock_run, mock_geteuid):
    """Test needs_root passes required (positional) args positionally."""
    mock_run.return_value = MagicMock(returncode=0)

    @simoc_sam_cli.needs_root
    def test_func(interface, ssid, password='default'):
        return True

    # Call with positional args
    result = test_func('wlan0', 'MyNetwork')

    assert result is True
    mock_run.assert_called_once()

    # Required positionals are passed positionally, not as --flags
    cmd = mock_run.call_args[0][0]
    assert 'wlan0' in cmd
    assert 'MyNetwork' in cmd


@patch('os.geteuid', return_value=0)  # Root
def test_needs_root_when_root(mock_geteuid):
    """Test needs_root decorator calls function directly when already root."""
    mock_func = MagicMock(return_value=True)
    mock_func.__name__ = 'test_func'  # Add __name__ attribute for decorator

    decorated = simoc_sam_cli.needs_root(mock_func)
    result = decorated('arg1', kwarg='value')

    assert result is True
    mock_func.assert_called_once_with('arg1', kwarg='value')


@patch('os.geteuid', return_value=1000)  # Not root
@patch('subprocess.run')
def test_needs_root_kwargs_take_precedence(mock_run, mock_geteuid):
    """Test that kwargs take precedence over positional args."""
    mock_run.return_value = MagicMock(returncode=0)

    @simoc_sam_cli.needs_root
    def test_func(interface, password='default'):
        return True

    # Call with positional and kwargs - kwargs should win
    result = test_func('wlan0', interface='wlan1')

    assert result is True
    mock_run.assert_called_once()

    cmd = mock_run.call_args[0][0]
    # Should use wlan1 (from kwargs), not wlan0 (from positional)
    assert '--interface=wlan1' in cmd


@patch('os.geteuid', return_value=1000)  # Not root
@patch('subprocess.run')
def test_needs_root_converts_underscores_to_hyphens(mock_run, mock_geteuid):
    """Test needs_root converts underscores to hyphens in arg names."""
    mock_run.return_value = MagicMock(returncode=0)

    @simoc_sam_cli.needs_root
    def test_func(my_interface, wifi_ssid):
        return True

    result = test_func(my_interface='wlan0', wifi_ssid='Network')

    assert result is True
    mock_run.assert_called_once()

    cmd = mock_run.call_args[0][0]
    assert '--my-interface=wlan0' in cmd
    assert '--wifi-ssid=Network' in cmd


@patch('os.geteuid', return_value=1000)  # Not root
@patch('subprocess.run')
def test_needs_root_failure(mock_run, mock_geteuid):
    """Test needs_root returns False when subprocess fails."""
    mock_run.return_value = MagicMock(returncode=1)

    @simoc_sam_cli.needs_root
    def test_func(arg):
        return True

    result = test_func('value')

    assert result is False


# -- `sam config` dispatch/control-flow tests --
# These test simoc-sam.py's own `config()` routing logic (which flag calls
# which simoc_config function, in what order, with what args) using a mocked
# simoc_config -- the underlying config.py behavior itself (parse_value,
# print_all, load_user_config, ...) is already covered in test_config.py.

def test_config_two_standalone_flags_rejected(mock_config):
    with pytest.raises(SystemExit) as exc_info:
        simoc_sam_cli.config(path=True, clean=True)
    assert 'cannot be used together' in str(exc_info.value)
    mock_config.load_user_config.assert_not_called()


def test_config_standalone_flag_with_reset_rejected(mock_config):
    with pytest.raises(SystemExit) as exc_info:
        simoc_sam_cli.config(path=True, reset=True)
    assert '--path and --reset cannot be used together' in str(exc_info.value)
    mock_config.load_user_config.assert_not_called()


def test_config_standalone_flag_with_key_rejected(mock_config):
    with pytest.raises(SystemExit) as exc_info:
        simoc_sam_cli.config('mqtt_port', '9999', clean=True)
    assert 'cannot be combined' in str(exc_info.value)
    mock_config.load_user_config.assert_not_called()


def test_config_reset_without_key_rejected(mock_config):
    with pytest.raises(SystemExit) as exc_info:
        simoc_sam_cli.config(reset=True)
    assert '--reset requires a key' in str(exc_info.value)
    mock_config.load_user_config.assert_not_called()


def test_config_reset_with_value_rejected(mock_config):
    with pytest.raises(SystemExit) as exc_info:
        simoc_sam_cli.config('mqtt_port', '9999', reset=True)
    assert '--reset requires a key and no value' in str(exc_info.value)
    mock_config.load_user_config.assert_not_called()


def test_config_path_prints_path_only(mock_config, user_config, capsys):
    simoc_sam_cli.config(path=True)
    assert capsys.readouterr().out == f'{user_config}\n'
    mock_config.load_user_config.assert_not_called()
    mock_config.get_schema.assert_not_called()


def test_config_create_new_file(mock_config, user_config, capsys):
    mock_config.generate_config.return_value = '# template\n'
    simoc_sam_cli.config(create=True)
    assert user_config.read_text() == '# template\n'
    assert f'Created: {user_config}' in capsys.readouterr().out


def test_config_create_existing_file_is_untouched(mock_config, user_config, capsys):
    user_config.write_text('# already here\n')
    simoc_sam_cli.config(create=True)
    assert user_config.read_text() == '# already here\n'  # not overwritten
    assert 'already exists' in capsys.readouterr().out


def test_config_clean_removes_existing_file(mock_config, user_config, capsys):
    user_config.write_text('# bye\n')
    simoc_sam_cli.config(clean=True)
    assert not user_config.exists()
    assert not user_config.parent.exists()  # emptied parent dir also removed
    assert f'Removed: {user_config}' in capsys.readouterr().out


def test_config_clean_missing_file(mock_config, capsys):
    simoc_sam_cli.config(clean=True)  # config.toml was never created
    assert 'No user config file found.' in capsys.readouterr().out


def test_config_edit_creates_missing_file_before_opening_editor(mock_config, user_config):
    mock_config.generate_config.return_value = '# template\n'
    mock_config.load_user_config.return_value = {}  # valid on first try
    with patch('subprocess.run') as mock_run:
        simoc_sam_cli.config(edit=True)
    assert user_config.read_text() == '# template\n'
    mock_run.assert_called_once()
    assert str(user_config) in mock_run.call_args[0][0]


def test_config_edit_retries_until_valid(mock_config, user_config):
    user_config.write_text('# existing\n')
    mock_config.load_user_config.side_effect = [ValueError('bad toml'), {}]
    with patch('subprocess.run') as mock_run, patch('builtins.input') as mock_input:
        simoc_sam_cli.config(edit=True)
    assert mock_run.call_count == 2  # editor re-opened after the failed attempt
    mock_input.assert_called_once()
    assert mock_config.load_user_config.call_count == 2


def test_config_bare_list_calls_print_all(mock_config):
    mock_config.get_schema.return_value = {'mqtt_port': {'default': 1883}}
    mock_config.load_user_config.return_value = {'mqtt_port': 9999}
    simoc_sam_cli.config()
    mock_config.print_all.assert_called_once_with(
        {'mqtt_port': {'default': 1883}}, {'mqtt_port': 9999})


def test_config_defaults_flag_calls_print_defaults(mock_config):
    schema = {'mqtt_port': {'default': 1883}}
    mock_config.get_schema.return_value = schema
    simoc_sam_cli.config(defaults=True)
    mock_config.print_defaults.assert_called_once_with(schema)
    mock_config.print_all.assert_not_called()


def test_config_unknown_key_returns_false(mock_config, capsys):
    mock_config.get_schema.return_value = {'mqtt_port': {'default': 1883}}
    mock_config.load_user_config.return_value = {}
    result = simoc_sam_cli.config(key='not_a_real_key')
    assert result is False
    assert 'unknown config key' in capsys.readouterr().out


def test_config_key_without_value_calls_print_one(mock_config):
    schema = {'mqtt_port': {'default': 1883}}
    overrides = {}
    mock_config.get_schema.return_value = schema
    mock_config.load_user_config.return_value = overrides
    simoc_sam_cli.config(key='mqtt_port')
    mock_config.print_one.assert_called_once_with('mqtt_port', schema, overrides)


def test_config_key_accepts_hyphens(mock_config):
    """Test that hyphenated keys (e.g. from --flag style input) are normalized."""
    schema = {'mqtt_port': {'default': 1883}}
    mock_config.get_schema.return_value = schema
    mock_config.load_user_config.return_value = {}
    simoc_sam_cli.config(key='mqtt-port')
    mock_config.print_one.assert_called_once_with('mqtt_port', schema, {})


def test_config_reset_when_overridden(mock_config, capsys):
    schema = {'mqtt_port': {'default': 1883}}
    mock_config.get_schema.return_value = schema
    mock_config.load_user_config.return_value = {'mqtt_port': 9999}
    mock_config.format_value.return_value = '1883'
    simoc_sam_cli.config(key='mqtt_port', reset=True)
    mock_config.save_user_config.assert_called_once_with({})  # key removed
    assert 'Reset mqtt_port to default: 1883' in capsys.readouterr().out


def test_config_reset_when_not_overridden(mock_config, capsys):
    mock_config.get_schema.return_value = {'mqtt_port': {'default': 1883}}
    mock_config.load_user_config.return_value = {}
    simoc_sam_cli.config(key='mqtt_port', reset=True)
    mock_config.save_user_config.assert_not_called()
    assert 'already at its default value' in capsys.readouterr().out


def test_config_set_value_success(mock_config, capsys):
    mock_config.get_schema.return_value = {'mqtt_port': {'default': 1883}}
    mock_config.load_user_config.return_value = {}
    mock_config.parse_value.return_value = 9999
    mock_config.format_value.return_value = '9999'
    mock_config.RELATED_COMMANDS = {'mqtt_port': 'setup-mosquitto'}
    simoc_sam_cli.config(key='mqtt_port', value='9999')
    mock_config.save_user_config.assert_called_once_with({'mqtt_port': 9999})
    out = capsys.readouterr().out
    assert 'mqtt_port = 9999' in out
    assert 'sam setup-mosquitto' in out


def test_config_set_value_parse_error_returns_false(mock_config, capsys):
    mock_config.get_schema.return_value = {'mqtt_port': {'default': 1883}}
    mock_config.load_user_config.return_value = {}
    mock_config.parse_value.side_effect = ValueError('not an int')
    result = simoc_sam_cli.config(key='mqtt_port', value='not_a_number')
    assert result is False
    mock_config.save_user_config.assert_not_called()
    assert 'Error: not an int' in capsys.readouterr().out
