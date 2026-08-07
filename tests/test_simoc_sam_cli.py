"""Tests for simoc-sam CLI argument parsing and decorators."""

import sys
import pathlib
from unittest.mock import patch, MagicMock, call

import pytest


# Add parent directory to path to import simoc-sam.py as a module
parent_dir = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import the module (this will be simoc-sam.py)
import importlib.util
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
    """Test that --flag= args for optional params are accepted natively."""
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
    # Positional args should appear as UPPERCASE metavars
    assert 'INTERFACE' in out
    assert 'SSID' in out
    assert 'PASSWORD' in out
    # Named --flags for these params should NOT appear (they're positional)
    assert '--interface' not in out
    assert '--ssid' not in out
    assert '--password' not in out


def test_main_keyword_only_not_positional(clean_commands):
    """Test that KEYWORD_ONLY params (after *) are never assigned from positional args."""
    mock_func = MagicMock(return_value=True)
    mock_func.__name__ = 'test_cmd'
    mock_func.__doc__ = 'Test command'
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_func

    import inspect
    sig = inspect.Signature([
        inspect.Parameter('target', inspect.Parameter.POSITIONAL_OR_KEYWORD),
        inspect.Parameter('exclude_venv', inspect.Parameter.KEYWORD_ONLY, default=True),
        inspect.Parameter('exclude_git', inspect.Parameter.KEYWORD_ONLY, default=True),
    ])

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'pi@rpi.local']):
        with patch.object(inspect, 'signature', return_value=sig):
            with pytest.raises(SystemExit) as exc_info:
                simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # Only 'target' should be passed; keyword-only params use their defaults
    mock_func.assert_called_once_with('pi@rpi.local')


def test_main_positional_args_only(clean_commands):
    """Test main() with positional arguments distributes correctly."""
    # Create a test command
    mock_func = MagicMock(return_value=True)
    mock_func.__name__ = 'test_cmd'
    mock_func.__doc__ = 'Test command'
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_func

    # Mock the function signature
    import inspect
    sig = inspect.Signature([
        inspect.Parameter('interface', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        inspect.Parameter('ssid', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        inspect.Parameter('password', inspect.Parameter.POSITIONAL_OR_KEYWORD, default='default123'),
    ])

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'wlan0', 'MyNetwork']):
        with patch.object(inspect, 'signature', return_value=sig):
            with pytest.raises(SystemExit) as exc_info:
                simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # ssid and password also passed explicitly (with their defaults) since optional
    # params are always set via the hidden --flag's default=param.default.
    mock_func.assert_called_once_with(interface='wlan0', ssid='MyNetwork', password='default123')


def test_main_named_args_only(clean_commands):
    """Test main() with named arguments only (via hidden --flag)."""
    mock_func = MagicMock(return_value=True)
    mock_func.__name__ = 'test_cmd'
    mock_func.__doc__ = 'Test command'
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_func

    import inspect
    sig = inspect.Signature([
        inspect.Parameter('interface', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        inspect.Parameter('password', inspect.Parameter.POSITIONAL_OR_KEYWORD, default='default123'),
    ])

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', '--interface=wlan2', '--password=secret']):
        with patch.object(inspect, 'signature', return_value=sig):
            with pytest.raises(SystemExit) as exc_info:
                simoc_sam_cli.main()

    assert exc_info.value.code == 0
    mock_func.assert_called_once_with(interface='wlan2', password='secret')


def test_main_mixed_positional_and_named(clean_commands):
    """Test main() with mixed positional and named arguments."""
    mock_func = MagicMock(return_value=True)
    mock_func.__name__ = 'test_cmd'
    mock_func.__doc__ = 'Test command'
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_func

    import inspect
    sig = inspect.Signature([
        inspect.Parameter('interface', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        inspect.Parameter('ssid', inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        inspect.Parameter('password', inspect.Parameter.POSITIONAL_OR_KEYWORD, default='default123'),
    ])

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'wlan0', '--password=mysecret']):
        with patch.object(inspect, 'signature', return_value=sig):
            with pytest.raises(SystemExit) as exc_info:
                simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # interface from positional, ssid uses default (None), password from --flag
    mock_func.assert_called_once_with(interface='wlan0', ssid=None, password='mysecret')


def test_main_defaults_passed_explicitly(clean_commands):
    """Test that optional params are always passed with their defaults (new behaviour).

    The dual-registration trick means args.X is always set to param.default when not
    provided, so the function always receives every optional kwarg explicitly.
    """
    mock_func = MagicMock(return_value=True)
    mock_func.__name__ = 'test_cmd'
    mock_func.__doc__ = 'Test command'
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_func

    import inspect
    sig = inspect.Signature([
        inspect.Parameter('interface', inspect.Parameter.POSITIONAL_OR_KEYWORD, default='wlan0'),
        inspect.Parameter('password', inspect.Parameter.POSITIONAL_OR_KEYWORD, default='default123'),
    ])

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd']):
        with patch.object(inspect, 'signature', return_value=sig):
            with pytest.raises(SystemExit) as exc_info:
                simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # All optional params passed explicitly with their defaults
    mock_func.assert_called_once_with(interface='wlan0', password='default123')


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
    assert '--interface=wlan0' in cmd
    assert '--ssid=MySSID' in cmd
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
def test_needs_root_converts_positional_to_kwargs(mock_run, mock_geteuid):
    """Test needs_root converts positional args to kwargs using signature."""
    mock_run.return_value = MagicMock(returncode=0)

    @simoc_sam_cli.needs_root
    def test_func(interface, ssid, password='default'):
        return True

    # Call with positional args
    result = test_func('wlan0', 'MyNetwork')

    assert result is True
    mock_run.assert_called_once()

    # Check that positionals were converted to named args
    cmd = mock_run.call_args[0][0]
    assert '--interface=wlan0' in cmd
    assert '--ssid=MyNetwork' in cmd


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
