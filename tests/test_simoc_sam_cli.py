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
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_cmd

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd', 'pi@rpi.local']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    # target gets the positional value; keyword-only params absent from argv use their defaults
    mock_cmd.assert_called_once_with(target='pi@rpi.local')


def test_parser_required_named_form():
    """Test that required params (no default) can be passed as --flag=value."""
    parser = simoc_sam_cli.create_parser()
    # copy-repo has 'target' as a required param; --target= form must also work
    args = parser.parse_args(['copy-repo', '--target=pi@host'])
    assert args.target == 'pi@host'


def test_build_call_args_missing_required():
    """Test that build_call_args calls parser.error when a required param is absent."""
    import argparse

    def dummy(target): pass

    ns = argparse.Namespace(cmd='dummy')  # target not in namespace
    parser = simoc_sam_cli.create_parser()
    with pytest.raises(SystemExit):
        simoc_sam_cli.build_call_args(dummy, ns, parser)


def test_main_positional_args_only(clean_commands):
    """Test that positional arguments are passed as keyword args to the function."""
    def test_cmd(interface=None, ssid=None, password='default123'):
        """Test command."""
    mock_cmd = create_autospec(test_cmd, return_value=True)
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_cmd

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
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_cmd

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
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_cmd

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
    simoc_sam_cli.COMMANDS['test_cmd'] = mock_cmd

    with patch('sys.argv', ['simoc-sam.py', 'test-cmd']):
        with pytest.raises(SystemExit) as exc_info:
            simoc_sam_cli.main()

    assert exc_info.value.code == 0
    mock_cmd.assert_called_once_with(interface='wlan0', password='default123')
