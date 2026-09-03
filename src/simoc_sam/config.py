"""SIMOC Live configuration: schema, loading, saving, and module-level vars.

The ``sam config`` CLI command and the web admin interface use :func:`get_schema`,
:func:`load_user_config`, :func:`save_user_config`, :func:`parse_value`, and the
``print_*`` helpers defined here.

User overrides are stored as TOML at ``~/.config/simoc-sam/config.toml``.
Only changed fields are written; everything else falls back to defaults.
"""

import sys
import types
import typing
import socket
import pathlib
import tomllib
import functools
import dataclasses

import tomli_w


class InvalidConfig(ValueError):
    """Raised for an invalid config file, field value, or field combination."""


_GROUPS: list[tuple[str, list[str]]] = [
    ('HAB info', ['location', 'humans', 'volume']),
    ('Sensors', ['sensors', 'sensor_read_delay']),
    ('Display', ['display', 'display_refresh', 'display_format']),
    ('MQTT', ['mqtt_host', 'mqtt_port', 'mqtt_secure',
              'mqtt_certs_dir', 'mqtt_reconnect_delay']),
    ('SIMOC Web', ['sio_host', 'sio_port', 'data_source',
                   'mqtt_topic_sub', 'simoc_web_dist_dir']),
    ('Flask API', ['api_host', 'api_port']),
    ('Verbosity and logging', ['verbose_sensor', 'verbose_mqtt', 'enable_jsonl_logging',
                               'log_dir', 'data_dir', 'db_path']),
    ('BNO085', ['bno085_default_err_value', 'bno085_enabled_features']),
]
_GROUP_MAP: dict[str, str] = {n: g for g, ns in _GROUPS for n in ns}

_DEFAULT_DISPLAY_FORMAT = """
SIMOC LIVE
Up {uptime}

T: {bme688_temperature:.2f}C
RH: {bme688_humidity:.2f}%
CO2: {scd30_co2:.0f}
VOC: {sgp30_tvoc}
Lt: {tsl2591_light:.2f}
Pr: {bme688_pressure:.2f}
A-x: {bno085_linear_accel_x:.2f}
A-y: {bno085_linear_accel_y:.2f}
A-z: {bno085_linear_accel_z:.2f}
"""


@dataclasses.dataclass
class SimocConfig:
    """All SIMOC Live settings with defaults.

    ``Literal`` annotations define valid choices and drive ``sam config``
    validation and the web admin form (dropdowns / checkbox groups).

    Path fields are ``pathlib.Path`` objects, already expanded and absolute --
    ``__post_init__`` converts the raw strings that arrive from TOML.
    """

    # HAB info
    location: str | None = None
    humans: int = 0
    volume: int = 0

    # Sensors and data collection
    sensors: list[str] = dataclasses.field(default_factory=lambda: ['bme688', 'scd30', 'sgp30'])
    sensor_read_delay: float = 10.0

    # Display configuration
    display: str = 'ssd1306'
    display_refresh: float = 1.0
    display_format: str = _DEFAULT_DISPLAY_FORMAT

    # MQTT configuration
    mqtt_host: str = 'localhost'
    mqtt_port: int = 1883
    mqtt_secure: bool = False
    mqtt_certs_dir: pathlib.Path = pathlib.Path('~/.mqttcerts')
    mqtt_reconnect_delay: float = 5.0

    # SIMOC Web / SIO bridge configuration
    sio_host: str = 'localhost'
    sio_port: int = 8081
    data_source: typing.Literal['mqtt', 'logs'] = 'mqtt'
    mqtt_topic_sub: str = '#'
    simoc_web_dist_dir: pathlib.Path = pathlib.Path('/var/www/simoc')

    # Flask API configuration
    api_host: str = 'localhost'
    api_port: int = 8082

    # Verbosity and logging
    verbose_sensor: bool = False
    verbose_mqtt: bool = False
    enable_jsonl_logging: bool = True
    log_dir: pathlib.Path = pathlib.Path('~/logs')
    data_dir: pathlib.Path = pathlib.Path('~/data')
    db_path: pathlib.Path = pathlib.Path('~/data/sensor_data.db')

    # BNO085 configuration
    bno085_default_err_value: int = 0
    bno085_enabled_features: list[str] = dataclasses.field(default_factory=lambda: [
        'RAW_ACCELEROMETER', 'RAW_GYROSCOPE', 'RAW_MAGNETOMETER',
        'ACCELEROMETER', 'GYROSCOPE', 'MAGNETOMETER',
        'LINEAR_ACCELERATION', 'ROTATION_VECTOR', 'GAME_ROTATION_VECTOR',
    ])

    def __post_init__(self) -> None:
        # Validate field types and options against the schema
        current = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)
                   if not f.name.startswith('_')}
        validate_fields(current)

        # Expand ~ and absolutize all path fields (accepts both str and Path input)
        for fname in self._PATH_FIELDS:
            p = pathlib.Path(getattr(self, fname)).expanduser().absolute()
            setattr(self, fname, p)
        # Auto-derive location from hostname when not explicitly set
        if self.location is None:
            self.location = socket.gethostname().rstrip('0123456789')
        # Strip whitespace from the display format template
        self.display_format = self.display_format.strip()
        # Ensure display_refresh is positive
        if self.display_refresh <= 0:
            raise InvalidConfig(f"'display_refresh' must be > 0, got {self.display_refresh!r}")
        if self.mqtt_secure and not self.mqtt_certs_dir.exists():
            raise InvalidConfig("Set 'mqtt_certs_dir' to enable 'mqtt_secure'")
        if not self.enable_jsonl_logging and self.data_source == 'logs':
            raise InvalidConfig("Enable JSONL logging to use 'logs' as the data source")


SimocConfig._PATH_FIELDS = frozenset(
    name for name, hint in typing.get_type_hints(SimocConfig).items()
    if hint is pathlib.Path
)

# Maps Python types and generic origins to their config field type string.
_TYPES: dict = {
    bool: 'bool', int: 'int', float: 'float', str: 'str', list: 'list',
    pathlib.Path: 'str', types.UnionType: 'nullable_str',
}

def get_field_default(f: dataclasses.Field):
    """Return a dataclass field's default value, calling default_factory if needed."""
    return f.default_factory() if f.default is dataclasses.MISSING else f.default


def get_field_type(hint, default) -> tuple[str, tuple]:
    """Return ``(type, options)`` from a resolved type hint.

    *options* is a tuple of valid values, or an empty tuple if unconstrained.
    """
    origin = typing.get_origin(hint)
    if origin is typing.Literal:
        return 'literal', typing.get_args(hint)
    if isinstance(default, str) and '\n' in default:
        return 'multiline_str', ()
    return _TYPES.get(origin, _TYPES.get(hint, 'str')), ()


def validate_field(name, value, field_type, options=()) -> bool:
    """Check a Python value against a schema field type and options."""
    if field_type == 'bool':
        return isinstance(value, bool)
    if field_type == 'int':
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == 'float':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == 'nullable_str':
        return value is None or isinstance(value, str)
    if field_type == 'list':
        return isinstance(value, list) and (not options or all(v in options for v in value))
    if field_type == 'literal':
        return not options or value in options
    if name in SimocConfig._PATH_FIELDS:
        return isinstance(value, (str, pathlib.Path))
    return isinstance(value, str)  # str, multiline_str


def validate_fields(values: dict) -> None:
    """Raise InvalidConfig listing every invalid or unknown field."""
    schema = get_schema()
    errors = {}
    for name, value in values.items():
        if name not in schema:
            errors[name] = f'{name!r} is not a known config field'
            continue
        info = schema[name]
        if not validate_field(name, value, info['type'], info['options']):
            hint = f' (valid: {", ".join(map(str, info["options"]))})' if info['options'] else ''
            errors[name] = f'{name!r} should be {info["type"]!r}{hint}, got {value!r}'
    if errors:
        raise InvalidConfig('Invalid config values:\n' + '\n'.join(f'  {e}'
                            for e in errors.values()))


def validate_overrides(overrides: dict) -> None:
    """Validate *overrides* and raise :exc:`InvalidConfig` on errors."""
    try:
        SimocConfig(**overrides)  # validates the overrides in __post_init__
    except TypeError as exc:
        raise InvalidConfig(str(exc)) from exc


@functools.cache
def get_schema() -> dict[str, dict]:
    """Return a schema dict for every config field (result is cached).

    Each entry has ``default``, ``type``, ``group``, and ``options``.
    *type* is one of: ``str``, ``multiline_str``, ``nullable_str``,
    ``bool``, ``int``, ``float``, ``list``, ``literal``.
    """
    hints = typing.get_type_hints(SimocConfig)
    schema: dict[str, dict] = {}
    for f in dataclasses.fields(SimocConfig):
        if f.name.startswith('_'):
            continue
        default = get_field_default(f)
        field_type, options = get_field_type(hints[f.name], default)
        if isinstance(default, pathlib.Path):
            default = str(default)
        schema[f.name] = {
            'default': default,
            'type': field_type,
            'group': _GROUP_MAP.get(f.name, 'General'),
            'options': options,
        }
    # set options for fields that depend on runtime data
    from simoc_sam.sensors.utils import SENSOR_DATA
    schema['sensors']['options'] = tuple(sorted(SENSOR_DATA))
    from simoc_sam.displays.utils import DISPLAY_DATA
    schema['display']['options'] = tuple(sorted(DISPLAY_DATA))
    schema['display']['type'] = 'literal'  # str annotation, but constrained by registry
    schema['bno085_enabled_features']['options'] = tuple(SENSOR_DATA['bno085'].features)
    return schema


def generate_config(overrides: dict = {}) -> str:
    """Return a TOML config template; overrides appear as live values."""
    schema = get_schema()
    lines = [
        '# SIMOC Live configuration',
        '# Uncomment and change a line to override its default.',
        '# CLI: sam config               -- list all values',
        '#      sam config KEY           -- show field details and options',
        '#      sam config KEY VALUE     -- set a value',
        '#      sam config --edit        -- open this file in $EDITOR',
        '',
    ]
    current_group = None
    for name, info in schema.items():
        if info['group'] != current_group:
            if current_group is not None:
                lines.append('')
            current_group = info['group']
            lines.append(f'# -- {current_group} --')
        # None means "unset" (TOML has no null) -- fall back to the commented default
        if name in overrides and overrides[name] is not None:
            value = overrides[name]
            if isinstance(value, pathlib.Path):
                value = str(value)  # tomli_w can't serialize Path objects
            lines.append(tomli_w.dumps({name: value}).rstrip())
        elif info['type'] == 'multiline_str':
            toml_block = f'{name} = """\n{info["default"].strip()}\n"""'
            lines.append('\n'.join(f'# {line}' for line in toml_block.splitlines()))
        else:
            default = info['default'] if info['default'] is not None else ''
            toml_line = tomli_w.dumps({name: default}).rstrip()
            commented = '\n'.join(f'# {line}' for line in toml_line.splitlines())
            lines.append(commented)
        if opts := info['options']:
            lines.append(f'### valid options: {", ".join(map(str, opts))}')
    return '\n'.join(lines) + '\n'


def config_path() -> pathlib.Path:
    """Return the config file path (re-evaluated each call so test monkeypatching works)."""
    return pathlib.Path.home() / '.config/simoc-sam/config.toml'


def load_user_config() -> dict:
    """Load and validate user overrides from ``~/.config/simoc-sam/config.toml``."""
    path = config_path()
    if not path.exists():
        return {}
    try:
        with open(path, 'rb') as f:
            overrides = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise InvalidConfig(f'Invalid TOML syntax in <{path}>: {exc}') from exc
    validate_overrides(overrides)
    return overrides


def save_user_config(overrides: dict) -> None:
    """Validate, then write the config template with overrides as live TOML values."""
    validate_overrides(overrides)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_config(overrides))


def get_config() -> SimocConfig:
    """Return a :class:`SimocConfig` merging defaults with user overrides."""
    return SimocConfig(**load_user_config())


def parse_value(raw: str, schema_entry: dict):
    """Parse a CLI string into the correct Python type for a config field.

    Raises :exc:`ValueError` on invalid input.
    """
    field_type = schema_entry['type']
    options = schema_entry['options']
    if field_type == 'bool':
        if raw.lower() in ('true', '1', 'yes', 'on'):
            return True
        if raw.lower() in ('false', '0', 'no', 'off'):
            return False
        raise ValueError(f'expected true/false, got {raw!r}')
    if field_type == 'int':
        return int(raw)
    if field_type == 'float':
        return float(raw)
    if field_type == 'nullable_str':
        return None if raw.strip() == '' else raw
    if field_type == 'list':
        values = [v.strip() for v in raw.split(',') if v.strip()]
        if options:
            invalid = [v for v in values if v not in options]
            if invalid:
                raise ValueError(f'invalid values: {invalid!r}\n'
                                 f'valid options: {", ".join(options)}')
        return values
    if field_type == 'literal':
        if options and raw not in options:
            raise ValueError(f'invalid value: {raw!r}\n'
                             f'valid options: {", ".join(options)}')
        return raw
    return raw  # str, multiline_str (kept as string for round-trip)


def format_value(value) -> str:
    """Format a value for one-line CLI display."""
    if isinstance(value, list):
        return ', '.join(str(v) for v in value) if value else '(empty list)'
    if isinstance(value, str) and '\n' in value:
        return '(multiline -- run `sam config KEY` to view)'
    return str(value) if value is not None else '(none)'


def print_all(schema: dict, user_overrides: dict) -> None:
    """Print all config values grouped by section; mark customised values."""
    cfg = SimocConfig(**user_overrides)
    current_group = None
    has_overrides = False
    for name, info in schema.items():
        if info['group'] != current_group:
            current_group = info['group']
            print(f'\n{current_group}:')
        current = getattr(cfg, name)
        marker = '*' if name in user_overrides else ' '
        if name in user_overrides:
            has_overrides = True
        opts = info['options']
        hint = '  [' + '|'.join(opts[:5]) + ('|...' if len(opts) > 5 else '') + ']' if opts else ''
        print(f'  {marker} {name:32}= {format_value(current)}{hint}')
    if has_overrides:
        print('\n  * = set in user config')


def print_one(name: str, schema: dict, user_overrides: dict) -> None:
    """Print the value and metadata for a single config key."""
    info = schema[name]
    current = getattr(SimocConfig(**user_overrides), name)
    print(f'{name} =\n{current}' if info['type'] == 'multiline_str'
          else f'{name} = {format_value(current)}')
    overridden = ' (overridden)' if name in user_overrides else ''
    print(f'  default: {format_value(info["default"])}{overridden}')
    if opts := info['options']:
        print(f'  options: {", ".join(opts)}')


def print_defaults(schema: dict) -> None:
    """Print all default values grouped by section."""
    current_group = None
    for name, info in schema.items():
        if info['group'] != current_group:
            current_group = info['group']
            print(f'\n{current_group}:')
        print(f'  {name:32}= {format_value(info["default"])}')


# Maps config field names to the sam command that applies the change.
# Shown as a hint by `sam config KEY VALUE` after saving.
RELATED_COMMANDS: dict[str, str] = {
    'sensors': 'setup-sensors',
    'display': 'setup-display',
    'mqtt_host': 'setup-mosquitto',
    'mqtt_port': 'setup-mosquitto',
    'mqtt_secure': 'setup-mosquitto',
    'mqtt_certs_dir': 'setup-mosquitto',
    'data_source': 'setup-siobridge',
    'sio_host': 'setup-siobridge',
    'sio_port': 'setup-siobridge',
    'api_host': 'setup-flask',
    'api_port': 'setup-flask',
    'simoc_web_dist_dir': 'setup-nginx',
}


# Expose SimocConfig fields as module-level attributes.
# If the user config is invalid (bad TOML syntax or a wrong-typed value), the
# attributes below are left unset -- `import simoc_sam.config` still succeeds
# (so `sam config --edit`/`--clean`/`--path` keep working to fix the file),
# but any command that reads e.g. `simoc_config.sensors` fails loudly with an
# AttributeError instead of silently running with the wrong defaults.
try:
    _cfg = get_config()
except InvalidConfig as exc:
    print(f'Warning: {exc}', file=sys.stderr)
else:
    for _f in dataclasses.fields(_cfg):
        if not _f.name.startswith('_'):
            setattr(sys.modules[__name__], _f.name, getattr(_cfg, _f.name))

# Convenience alias (used by tests and the admin interface)
user_config_path = config_path()
