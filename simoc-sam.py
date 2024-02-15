"""Script to setup and run SIMOC-SAM."""

import sys
import shutil
import pathlib
import argparse
import functools
import subprocess

import hostinfo


SIMOC_SAM_DIR = pathlib.Path(__file__).resolve().parent
VENV_DIR = SIMOC_SAM_DIR / 'venv'
VENV_PY = str(VENV_DIR / 'bin' / 'python3')
DEPS = 'requirements.txt'
DEV_DEPS = 'dev-requirements.txt'
TMUX_SNAME = 'SAM'  # tmux session name

COMMANDS = {}

def cmd(func):
    """Decorator to add commands to the COMMANDS dict."""
    COMMANDS[func.__name__] = func
    return func

def run(args):
    print('>>', ' '.join(args))
    print('-'*80)
    result = subprocess.run(args)
    print('-'*80)
    print('<<', result)
    print()
    return not result.returncode

def needs_venv(func):
    """Ensure that the venv exist before calling func."""
    @functools.wraps(func)
    def inner(*args, **kwargs):
        if not VENV_DIR.exists():
            print('venv dir missing -- creating it')
            create_venv()
        return func(*args, **kwargs)
    return inner


@cmd
def create_venv():
    """Create and set up a virtualenv."""
    if VENV_DIR.exists():
        print('venv already exists -- aborting.')
        return
    return (
        run([sys.executable, '-m', 'venv', 'venv']) and
        run([VENV_PY, '-m', 'pip', 'install', '--upgrade', 'pip']) and
        run([VENV_PY, '-m', 'pip', 'install', '-r', DEPS]) and
        run([VENV_PY, '-m', 'pip', 'install', '-r', DEV_DEPS]) and
        run([VENV_PY, '-m', 'pip', 'install', '-e', '.'])
    )

@cmd
def clean_venv():
    """Remove the venv dir."""
    if not VENV_DIR.exists():
        print(f'No venv dir found -- aborting.')
        return
    print(f'Removing venv dir: {VENV_DIR}')
    shutil.rmtree(VENV_DIR)
    print('venv dir removed.')

@cmd
@needs_venv
def test(*args):
    """Run the tests."""
    pytest = str(VENV_DIR / 'bin' / 'pytest')
    return run([pytest, '-v', *args])

@cmd
@needs_venv
def run_server():
    """Run the sioserver."""
    run([VENV_PY, '-m', 'simoc_sam.sioserver'])

@cmd
@needs_venv
def run_tmux():
    """Run the tmux script (or attach to an existing session)."""
    if run(['tmux', 'has-session', '-t', TMUX_SNAME]):
        run(['tmux', 'attach-session', '-t', TMUX_SNAME])  # attach to sessions
    else:
        run(['./tmux.sh', TMUX_SNAME])  # start new sessions


@cmd
@needs_venv
def info():
    """Print host info about the network and sensors."""
    hostinfo.print_info()

@cmd
@needs_venv
def network_info():
    """Print info about the network (hostname, addresses)."""
    hostinfo.print_network_info()

@cmd
@needs_venv
def sensors_info():
    """Print info about the connected sensors."""
    hostinfo.print_sensors_info()


VERNIER_USB_RULES = """\
SUBSYSTEM=="usb", ATTRS{idVendor}=="08f7", MODE="0666"
SUBSYSTEM=="usb_device", ATTRS{idVendor}=="08f7", MODE="0666"
"""
MCP2221_RULE = """\
SUBSYSTEM=="usb", ATTRS{idVendor}=="04d8", ATTR{idProduct}=="00dd", MODE="0666"
"""
USB_RULES_DIR = '/etc/udev/rules.d/'

@cmd
def add_vernier_rules():
    """Add Linux-specific USB rules for Vernier sensors access."""
    vernier_fname = 'vstlibusb.rules'
    with open(vernier_fname, 'w') as f:
        f.write(VERNIER_USB_RULES)
    return run(['sudo', 'mv', vernier_fname, USB_RULES_DIR])

@cmd
def add_mcp_rules():
    """Add Linux-specific USB rules for Adafruit MCP2221 access."""
    mcp_fname = '99-mcp2221.rules'
    with open(mcp_fname, 'w') as f:
        f.write(MCP2221_RULE)
    return run(['sudo', 'mv', mcp_fname, USB_RULES_DIR])

@cmd
def add_usb_rules():
    """Add Linux-specific rules for USB devices access."""
    return add_vernier_rules() and add_mcp_rules()


def create_help(cmds):
    help = ['Full list of available commands:']
    for cmd, func in cmds.items():
        help.append(f'{cmd.replace("_", "-"):18} {func.__doc__}')
    return '\n'.join(help)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Setup and run SIMOC-SAM.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('cmd', metavar='CMD', help=create_help(COMMANDS))
    parser.add_argument('args', metavar='*ARGS', nargs='*',
                        help='Additional optional args to be passed to CMD.')
    args = parser.parse_args()

    cmd = args.cmd.replace('-', '_')
    if cmd in COMMANDS:
        result = COMMANDS[cmd](*args.args)
        parser.exit(not result)
    else:
        cmds = ', '.join(cmd.replace('_', '-') for cmd in COMMANDS.keys())
        parser.error(f'Command not found.  Available commands: {cmds}')
