"""Admin Flask Blueprint for SIMOC-SAM.

Provides endpoints for:
- Reading and writing the user configuration file (structured or raw).
- Running whitelisted simoc-sam.py management commands.
"""

import re
import sys
import inspect
import pathlib
import secrets
import subprocess
import importlib.util

from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash
from flask import Blueprint, abort, jsonify, request, session

from simoc_sam import config as sam_config


# ─── paths ────────────────────────────────────────────────────────────────────

_HERE = pathlib.Path(__file__).resolve().parent
SIMOC_SAM_DIR = _HERE.parents[1]           # repository root (src/simoc_sam → src → repo)
SIMOC_SAM_SCRIPT = SIMOC_SAM_DIR / 'simoc-sam.py'


# ─── command loading ─────────────────────────────────────────────────────────

# Preferred display order for command groups in the admin UI.
_GROUP_ORDER = ['Info', 'Services', 'Frontend', 'Network', 'System']


def _load_commands():
    """Import simoc-sam.py and build a grouped commands dict.

    Only @cmd(admin=True) functions are included; group names, docstrings,
    needs_root, and args_hint are taken directly from function attributes set
    by the @cmd / @needs_root / @needs_venv decorators in simoc-sam.py.
    """
    try:
        spec = importlib.util.spec_from_file_location('_simoc_sam', SIMOC_SAM_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        raw = module.COMMANDS
    except Exception as exc:
        return {'Error': {'load-error': {'doc': str(exc), 'needs_root': False}}}

    ungrouped: dict = {}
    for name, func in raw.items():
        if not getattr(func, 'admin', False):
            continue
        cat = getattr(func, 'category', None) or 'Uncategorized'
        entry: dict = {
            'doc': (func.__doc__ or '').strip().split('\n')[0],
            'needs_root': bool(getattr(func, 'needs_root', False)),
        }
        params = getattr(func, 'params', {})
        entry['params'] = [
            {
                'name': param_name,
                'required': param.default is inspect.Parameter.empty,
                'default': (None if param.default is inspect.Parameter.empty
                             else param.default),
                'type': ('bool' if isinstance(param.default, bool)
                         else type(param.default).__name__),
                'secret': 'password' in param_name.lower(),
            }
            for param_name, param in params.items()
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        ]
        hint = getattr(func, 'args_hint', None)
        if hint:
            entry['args_hint'] = hint
        ungrouped.setdefault(cat, {})[name.replace('_', '-')] = entry

    # Return groups in preferred UI order; append any unexpected categories last.
    groups = {cat: ungrouped[cat] for cat in _GROUP_ORDER if cat in ungrouped}
    groups.update({cat: cmds for cat, cmds in ungrouped.items() if cat not in groups})
    return groups


COMMANDS = _load_commands()
_ALL_COMMANDS = {
    cmd_name: meta
    for group_cmds in COMMANDS.values()
    for cmd_name, meta in group_cmds.items()
}


# ─── config value helpers ──────────────────────────────────────────────────────

def _json_safe(value):
    """Convert a config value to something JSON-serialisable (e.g. Path → str)."""
    return str(value) if isinstance(value, pathlib.Path) else value


# ─── command execution ─────────────────────────────────────────────────────────

# Blocks path traversal / directory separators and flag-like args, since some
# commands (e.g. setup-sensors, setup-display) interpolate these into
# root-owned filesystem paths and unit names.
_UNSAFE_ARG_RE = re.compile(r'[\\/\x00]')


def _validate_args(extra_args):
    """Raise ValueError if any extra arg looks unsafe to forward to simoc-sam.py."""
    for arg in extra_args:
        if not isinstance(arg, str) or not arg:
            raise ValueError(f'Invalid argument: {arg!r}')
        if arg.startswith('-'):
            raise ValueError(f"Argument may not start with '-': {arg!r}")
        if _UNSAFE_ARG_RE.search(arg):
            raise ValueError(f'Argument contains unsafe characters: {arg!r}')


def _run_command(cmd_name, extra_args, needs_root):
    """Run `simoc-sam.py CMD [args]` in a subprocess.

    Returns (success: bool, stdout: str, stderr: str).
    Uses the current venv Python (sys.executable) so that simoc_sam imports work.
    For root commands, prefixes with sudo --preserve-env=HOME.
    """
    cmd_list = [sys.executable, str(SIMOC_SAM_SCRIPT), cmd_name, *extra_args]
    if needs_root:
        cmd_list = ['sudo', '--preserve-env=HOME', *cmd_list]
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(SIMOC_SAM_DIR),
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', 'Command timed out after 120 seconds.'
    except OSError as exc:
        return False, '', str(exc)


# ─── Blueprint ─────────────────────────────────────────────────────────────────

admin_bp = Blueprint('admin', __name__)


@admin_bp.errorhandler(BadRequest)
def handle_bad_request(error):
    return jsonify({'error': error.description}), 400


def _json_object():
    """Return the request JSON object or raise a JSON 400 error."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise BadRequest('JSON object required')
    return payload


def _admin_enabled():
    try:
        return sam_config.get_config().admin_enabled
    except sam_config.InvalidConfig:
        return False


def _admin_secure():
    try:
        return sam_config.get_config().admin_secure
    except sam_config.InvalidConfig:
        return True


def _login_required():
    return _admin_secure() and not session.get('admin_authenticated', False)


@admin_bp.before_request
def protect_admin():
    if request.endpoint == 'admin.get_visibility':
        return None
    if not _admin_enabled():
        abort(404)
    if request.endpoint == 'admin.login':
        return None
    if _login_required():
        return jsonify({'error': 'Admin authentication required'}), 401
    if request.method == 'POST':
        token = request.headers.get('X-CSRF-Token')
        if not token or not secrets.compare_digest(token, session.get('csrf_token', '')):
            return jsonify({'error': 'Invalid CSRF token'}), 403
    return None


@admin_bp.get('/visibility')
def get_visibility():
    """Return admin availability and navigation visibility."""
    try:
        cfg = sam_config.get_config()
    except sam_config.InvalidConfig:
        return jsonify({'enabled': False, 'visible': False, 'secure': True})
    csrf_token = session.get('csrf_token')
    if cfg.admin_enabled and not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        session['csrf_token'] = csrf_token
    return jsonify({
        'enabled': cfg.admin_enabled,
        'visible': cfg.admin_enabled and cfg.admin_visible,
        'secure': cfg.admin_secure,
        'csrf_token': csrf_token if cfg.admin_enabled and not cfg.admin_secure else None,
    })


@admin_bp.post('/login')
def login():
    """Authenticate the local admin session."""
    if not _admin_enabled():
        abort(404)
    payload = _json_object()
    password = payload.get('password')
    password_path = sam_config.admin_password_path()
    if not isinstance(password, str) or not password_path.is_file():
        return jsonify({'error': 'Invalid admin credentials'}), 401
    try:
        password_hash = password_path.read_text().strip()
        valid = check_password_hash(password_hash, password)
    except (OSError, ValueError):
        valid = False
    if not valid:
        return jsonify({'error': 'Invalid admin credentials'}), 401
    session.clear()
    session['admin_authenticated'] = True
    session['csrf_token'] = secrets.token_urlsafe(32)
    return jsonify({'success': True, 'csrf_token': session['csrf_token']})


@admin_bp.post('/logout')
def logout():
    """End the current local admin session."""
    session.clear()
    return jsonify({'success': True})


@admin_bp.get('/config')
def get_config():
    """Return the config schema, current values, and I2C-detected devices."""
    schema = sam_config.get_schema()
    cfg = sam_config.get_config(sam_config.read_user_overrides())
    values = {name: _json_safe(getattr(cfg, name)) for name in schema}
    path = sam_config.config_path()
    # Best-effort I2C scan; returns None when not running on RPi hardware.
    try:
        from simoc_sam.utils import get_i2c_names
        i2c_devices = get_i2c_names()
    except Exception:
        i2c_devices = None
    return jsonify({
        'schema': [{'name': name, **info} for name, info in schema.items()],
        'values': values,
        'user_config_exists': path.exists(),
        'user_config_path': str(path),
        'i2c_devices': i2c_devices,
    })


@admin_bp.post('/config')
def post_config():
    """Save structured config changes from the schema-backed form."""
    payload = _json_object()
    schema = sam_config.get_schema()
    submitted = payload.get('fields', {})
    if not isinstance(submitted, dict):
        return jsonify({'error': '"fields" must be an object'}), 400
    for name, value in submitted.items():
        if name not in schema:
            return jsonify({'error': f'Unknown field: {name!r}'}), 400
        info = schema[name]
        if not sam_config.validate_field(name, value, info['type'], info['options']):
            return jsonify({'error': f'Invalid value for {name!r}: {value!r}'}), 400
    current_overrides = sam_config.read_user_overrides()
    current_config = sam_config.get_config(current_overrides)
    desired_values = {
        name: getattr(current_config, name)
        for name in schema
    }
    desired_values.update(submitted)
    try:
        desired_config = sam_config.get_config(desired_values)
        default_config = sam_config.get_config({})
    except sam_config.InvalidConfig as exc:
        return jsonify({'error': str(exc)}), 400
    changed_fields = [
        name for name in schema
        if getattr(desired_config, name) != getattr(default_config, name)
    ]
    overrides = {
        name: submitted.get(name, current_overrides.get(name))
        for name in changed_fields
    }
    sam_config.save_user_config(overrides)
    related_commands = sorted({
        command
        for name in changed_fields
        for command in sam_config.RELATED_COMMANDS.get(name, ())
    })
    return jsonify({
        'success': True,
        'changed_fields': changed_fields,
        'related_commands': related_commands,
        'message': 'Config saved. Restart services to apply changes.',
    })


@admin_bp.get('/commands')
def get_commands():
    """Return the grouped command whitelist."""
    return jsonify({'commands': COMMANDS})


@admin_bp.post('/run')
def post_run():
    """Run a whitelisted simoc-sam.py command.

    Body: { cmd: str, args?: [str] }
    """
    payload = _json_object()
    cmd_name = payload.get('cmd', '')
    extra_args = payload.get('args', [])
    if not isinstance(cmd_name, str) or not cmd_name:
        return jsonify({'error': '"cmd" must be a non-empty string'}), 400
    if not isinstance(extra_args, list):
        return jsonify({'error': '"args" must be an array of strings'}), 400
    if not all(isinstance(arg, str) for arg in extra_args):
        return jsonify({'error': '"args" must be an array of strings'}), 400
    if cmd_name not in _ALL_COMMANDS:
        return jsonify({'error': f'Unknown or disallowed command: {cmd_name!r}'}), 400
    try:
        _validate_args(extra_args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    meta = _ALL_COMMANDS[cmd_name]
    success, stdout, stderr = _run_command(cmd_name, extra_args, meta['needs_root'])
    return jsonify({'success': success, 'stdout': stdout, 'stderr': stderr})
