import sys

from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from simoc_sam import admin


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.secret_key = b'test-secret'
    app.register_blueprint(admin.admin_bp, url_prefix='/api/admin')
    config_path = tmp_path / 'config.toml'
    with patch.object(admin.sam_config, 'config_path', return_value=config_path), \
         patch.object(admin, '_admin_enabled', return_value=True), \
         patch.object(admin, '_admin_secure', return_value=False):
        with app.test_client() as test_client:
            with test_client.session_transaction() as session:
                session['csrf_token'] = 'test-csrf-token'
            test_client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
            yield test_client, config_path


def test_get_config_returns_schema_and_values(client):
    test_client, config_path = client

    response = test_client.get('/api/admin/config')

    assert response.status_code == 200
    data = response.get_json()
    assert data['user_config_exists'] is False
    assert data['user_config_path'] == str(config_path)
    assert 'raw' not in data
    assert data['values']['mqtt_port'] == 1883
    sensors = next(field for field in data['schema'] if field['name'] == 'sensors')
    assert sensors['type'] == 'list'
    assert 'bme688' in sensors['options']


@pytest.mark.parametrize('payload', [[], 'text', 1])
def test_post_config_rejects_non_object_json(client, payload):
    test_client, _ = client

    response = test_client.post('/api/admin/config', json=payload)

    assert response.status_code == 400
    assert response.get_json()['error'] == 'JSON object required'


def test_get_visibility_defaults_to_hidden(client):
    test_client, _ = client

    with patch.object(admin, '_admin_enabled', return_value=False):
        response = test_client.get('/api/admin/visibility')

    assert response.status_code == 200
    assert response.get_json()['visible'] is False
    assert response.get_json()['enabled'] is False


def test_disabled_admin_returns_not_found(client):
    test_client, _ = client

    with patch.object(admin, '_admin_enabled', return_value=False):
        response = test_client.get('/api/admin/config')

    assert response.status_code == 404


def test_get_visibility_reflects_config(client):
    test_client, config_path = client
    config_path.write_text('admin_enabled = true\nadmin_visible = true\n')

    response = test_client.get('/api/admin/visibility')

    assert response.status_code == 200
    assert response.get_json()['visible'] is True


def test_insecure_visibility_bootstraps_csrf_token(client):
    test_client, config_path = client
    config_path.write_text('admin_enabled = true\nadmin_secure = false\n')

    response = test_client.get('/api/admin/visibility')

    assert response.status_code == 200
    assert response.get_json()['csrf_token']


def test_secure_admin_requires_authentication(client):
    test_client, _ = client

    with patch.object(admin, '_admin_secure', return_value=True):
        response = test_client.get('/api/admin/config')

    assert response.status_code == 401


def test_secure_admin_login_returns_csrf_token(client):
    test_client, config_path = client
    password_path = config_path.parent / 'admin-password.hash'
    password_path.write_text(generate_password_hash('test-password'))

    with patch.object(admin, '_admin_secure', return_value=True):
        response = test_client.post('/api/admin/login', json={'password': 'test-password'})

    assert response.status_code == 200
    assert response.get_json()['csrf_token']


def test_secure_admin_can_save_after_login(client):
    test_client, config_path = client
    password_path = config_path.parent / 'admin-password.hash'
    password_path.write_text(generate_password_hash('test-password'))

    with patch.object(admin, '_admin_secure', return_value=True):
        login_response = test_client.post(
            '/api/admin/login',
            json={'password': 'test-password'},
        )
        csrf_token = login_response.get_json()['csrf_token']
        response = test_client.post(
            '/api/admin/config',
            json={'fields': {'humans': 2}},
            headers={'X-CSRF-Token': csrf_token},
        )

    assert response.status_code == 200


def test_secure_admin_rejects_mutation_without_csrf(client):
    test_client, _ = client

    with patch.object(admin, '_admin_secure', return_value=False):
        response = test_client.post('/api/admin/config', json={'fields': {}},
                                    headers={'X-CSRF-Token': ''})

    assert response.status_code == 403


def test_post_config_structured_saves_valid_overrides(client):
    test_client, config_path = client

    response = test_client.post('/api/admin/config', json={
        'fields': {'humans': 3, 'sensors': ['scd30']},
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['changed_fields'] == ['humans', 'sensors']
    assert data['related_commands'] == ['setup-sensors']
    assert admin.sam_config.read_user_overrides() == {
        'humans': 3,
        'sensors': ['scd30'],
    }
    assert config_path.exists()


def test_post_config_structured_preserves_existing_overrides(client):
    test_client, _ = client

    first = test_client.post('/api/admin/config', json={
        'fields': {'humans': 3, 'sensors': ['scd30']},
    })
    assert first.status_code == 200

    second = test_client.post('/api/admin/config', json={
        'fields': {'humans': 4},
    })

    assert second.status_code == 200
    assert admin.sam_config.read_user_overrides() == {
        'humans': 4,
        'sensors': ['scd30'],
    }


def test_post_config_structured_removes_values_reset_to_defaults(client):
    test_client, _ = client

    response = test_client.post('/api/admin/config', json={
        'fields': {'humans': 3, 'sensors': ['scd30']},
    })
    assert response.status_code == 200

    response = test_client.post('/api/admin/config', json={
        'fields': {'humans': 0, 'sensors': ['bme688', 'scd30', 'sgp30']},
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['changed_fields'] == []
    assert data['related_commands'] == []
    assert admin.sam_config.read_user_overrides() == {}


def test_post_config_structured_rejects_unknown_field(client):
    test_client, config_path = client

    response = test_client.post('/api/admin/config', json={
        'fields': {'not_a_config_field': 'value'},
    })

    assert response.status_code == 400
    assert 'Unknown field' in response.get_json()['error']
    assert not config_path.exists()


def test_post_config_structured_rejects_invalid_combination(client):
    test_client, config_path = client

    response = test_client.post('/api/admin/config', json={
        'fields': {'data_source': 'logs', 'enable_jsonl_logging': False},
    })

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Config values are invalid or inconsistent'
    assert not config_path.exists()


def test_post_config_rejects_invalid_existing_config(client):
    test_client, config_path = client
    config_path.write_text('mqtt_port = "not an integer"\n')

    response = test_client.post('/api/admin/config', json={
        'fields': {'humans': 3},
    })

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Config values are invalid or inconsistent'


def test_post_run_rejects_unknown_command(client):
    test_client, _ = client

    response = test_client.post('/api/admin/run', json={
        'cmd': 'not-allowed',
        'args': [],
    })

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Unknown or disallowed command'


def test_get_commands_exposes_argument_metadata(client):
    test_client, _ = client

    response = test_client.get('/api/admin/commands')

    assert response.status_code == 200
    setup_wifi = response.get_json()['commands']['Network']['setup-wifi']
    assert [param['name'] for param in setup_wifi['params']] == [
        'ssid', 'password', 'interface',
    ]
    assert setup_wifi['params'][1]['secret'] is True
    assert setup_wifi['params'][2]['default'] == 'wlan0'


@pytest.mark.parametrize('payload', [
    {'cmd': []},
    {'cmd': 'safe-command', 'args': 'scd30'},
    {'cmd': 'safe-command', 'args': [None]},
])
def test_post_run_rejects_malformed_request(client, payload):
    test_client, _ = client

    response = test_client.post('/api/admin/run', json=payload)

    assert response.status_code == 400
    assert 'error' in response.get_json()


@pytest.mark.parametrize('argument', [
    '../../etc/evil',
    r'..\\evil',
    '--flag=value',
    '-x',
    'bad\x00value',
])
def test_post_run_rejects_unsafe_arguments(client, argument):
    test_client, _ = client

    with patch.dict(admin._ALL_COMMANDS, {
        'safe-command': {'name': 'safe-command', 'needs_root': False},
    }):
        response = test_client.post('/api/admin/run', json={
            'cmd': 'safe-command',
            'args': [argument],
        })

    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_post_run_executes_allowed_command(client):
    test_client, _ = client
    completed = (True, 'command output', '')

    command = {'name': 'safe-command', 'needs_root': False}
    with patch.dict(admin._ALL_COMMANDS, {'safe-command': command}):
        with patch.object(admin, '_run_command', return_value=completed) as run_command:
            response = test_client.post('/api/admin/run', json={
                'cmd': 'safe-command',
                'args': ['valid-value'],
            })

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'stdout': 'command output',
        'stderr': '',
    }
    run_command.assert_called_once_with(command, ['valid-value'])


def test_run_command_builds_root_command():
    completed = type('Completed', (), {
        'returncode': 0,
        'stdout': 'ok',
        'stderr': '',
    })()

    command = {'name': 'setup-sensors', 'needs_root': True}
    with patch.object(admin.subprocess, 'run', return_value=completed) as run:
        result = admin._run_command(command, ['scd30'])

    assert result == (True, 'ok', '')
    run.assert_called_once_with(
        [
            'sudo', '--preserve-env=HOME', sys.executable,
            str(admin.SIMOC_SAM_SCRIPT), 'setup-sensors', 'scd30',
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(admin.SIMOC_SAM_DIR),
    )


def test_run_command_returns_user_safe_errors():
    command = {'name': 'safe-command', 'needs_root': False}
    with patch.object(admin.subprocess, 'run', side_effect=OSError('not found')):
        with patch.dict(admin._ALL_COMMANDS, {'safe-command': command}):
            assert admin._run_command(command, []) == (
                False, '', 'Unable to start command.'
            )

    command = {'name': 'safe-command', 'needs_root': False}
    with patch.dict(admin._ALL_COMMANDS, {'safe-command': command}):
        with patch.object(admin.subprocess, 'run', side_effect=admin.subprocess.TimeoutExpired(
            cmd='safe-command', timeout=120,
        )):
            assert admin._run_command(command, []) == (
                False, '', 'Command timed out.'
            )


def test_run_command_hides_child_tracebacks():
    completed = type('Completed', (), {
        'returncode': 1,
        'stdout': '',
        'stderr': 'Traceback (most recent call last):\nsecret path\n',
    })()

    command = {'name': 'safe-command', 'needs_root': False}
    with patch.dict(admin._ALL_COMMANDS, {'safe-command': command}):
        with patch.object(admin.subprocess, 'run', return_value=completed):
            assert admin._run_command(command, []) == (
                False, '', 'Command failed. See the server logs for details.'
            )
