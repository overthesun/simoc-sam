"""Script to setup and run SIMOC-SAM."""

import sys
import shutil
import pathlib
import argparse
import functools
import subprocess


SIMOC_SAM_DIR = pathlib.Path(__file__).resolve().parent
VENV_DIR = SIMOC_SAM_DIR / 'venv'
VENV_PY = str(VENV_DIR / 'bin' / 'python3')
DEPS = ['python-socketio', 'aiohttp']
DEV_DEPS = ['pytest', 'pytest-asyncio']

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
        run([VENV_PY, '-m', 'pip', 'install', *DEPS, *DEV_DEPS]) and
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
    """Run the tmux script."""
    run(['./tmux.sh'])


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
