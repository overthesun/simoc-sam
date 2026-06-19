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
    """Test parsing with positional arguments only."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['test-uid', 'wlan0', 'MyNetwork', 'password123'])
    
    assert args.cmd == 'test-uid'
    assert args._positional == ['wlan0', 'MyNetwork', 'password123']


def test_parser_named_args():
    """Test parsing with named arguments only."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['test-uid', '--interface=wlan0', '--ssid=MyNetwork'])
    
    assert args.cmd == 'test-uid'
    assert args._positional == []
    assert args.interface == 'wlan0'
    assert args.ssid == 'MyNetwork'


def test_parser_mixed_args():
    """Test parsing with mixed positional and named arguments."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['test-uid', 'wlan0', '--password=secret'])
    
    assert args.cmd == 'test-uid'
    assert args._positional == ['wlan0']
    assert args.password == 'secret'


def test_parser_spaces_in_args():
    """Test parsing with spaces in argument values."""
    parser = simoc_sam_cli.create_parser()
    args = parser.parse_args(['test-uid', 'wlan 0', '--ssid=My Network'])
    
    assert args._positional == ['wlan 0']
    assert args.ssid == 'My Network'


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
    # Should only pass the arguments that were provided
    mock_func.assert_called_once_with(interface='wlan0', ssid='MyNetwork')


def test_main_named_args_only(clean_commands):
    """Test main() with named arguments only."""
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
    # interface is positional, password is named, ssid not provided (should use default)
    mock_func.assert_called_once_with(interface='wlan0', password='mysecret')


def test_main_defaults_not_passed(clean_commands):
    """Test that default values are not passed when argument not provided."""
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
    # No arguments should be passed - let Python handle defaults
    mock_func.assert_called_once_with()


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
