import sys

from unittest.mock import patch

import pytest
from flask import Flask

from simoc_sam import admin


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    app.register_blueprint(admin.admin_bp, url_prefix='/api/admin')
    config_path = tmp_path / 'config.toml'
    with patch.object(admin.sam_config, 'config_path', return_value=config_path):
        with app.test_client() as test_client:
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


def test_post_config_structured_saves_valid_overrides(client):
    test_client, config_path = client

    response = test_client.post('/api/admin/config', json={
        'mode': 'fields',
        'fields': {'humans': 3, 'sensors': ['scd30']},
    })

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert admin.sam_config.read_user_overrides() == {
        'humans': 3,
        'sensors': ['scd30'],
    }
    assert config_path.exists()


def test_post_config_structured_rejects_unknown_field(client):
    test_client, config_path = client

    response = test_client.post('/api/admin/config', json={
        'mode': 'fields',
        'fields': {'not_a_config_field': 'value'},
    })

    assert response.status_code == 400
    assert 'Unknown field' in response.get_json()['error']
    assert not config_path.exists()


def test_post_config_structured_rejects_invalid_combination(client):
    test_client, config_path = client

    response = test_client.post('/api/admin/config', json={
        'mode': 'fields',
        'fields': {'data_source': 'logs', 'enable_jsonl_logging': False},
    })

    assert response.status_code == 400
    assert 'Enable JSONL logging' in response.get_json()['error']
    assert not config_path.exists()


def test_post_run_rejects_unknown_command(client):
    test_client, _ = client

    response = test_client.post('/api/admin/run', json={
        'cmd': 'not-allowed',
        'args': [],
    })

    assert response.status_code == 400
    assert 'Unknown or disallowed command' in response.get_json()['error']


@pytest.mark.parametrize('argument', [
    '../../etc/evil',
    r'..\\evil',
    '--flag=value',
    '-x',
    'bad\x00value',
])
def test_post_run_rejects_unsafe_arguments(client, argument):
    test_client, _ = client

    with patch.dict(admin._ALL_COMMANDS, {'safe-command': {'needs_root': False}}):
        response = test_client.post('/api/admin/run', json={
            'cmd': 'safe-command',
            'args': [argument],
        })

    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_post_run_executes_allowed_command(client):
    test_client, _ = client
    completed = (True, 'command output', '')

    with patch.dict(admin._ALL_COMMANDS, {'safe-command': {'needs_root': False}}):
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
    run_command.assert_called_once_with('safe-command', ['valid-value'], False)


def test_run_command_builds_root_command():
    completed = type('Completed', (), {
        'returncode': 0,
        'stdout': 'ok',
        'stderr': '',
    })()

    with patch.object(admin.subprocess, 'run', return_value=completed) as run:
        result = admin._run_command('setup-sensors', ['scd30'], True)

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
    with patch.object(admin.subprocess, 'run', side_effect=OSError('not found')):
        assert admin._run_command('safe-command', [], False) == (False, '', 'not found')

    with patch.object(admin.subprocess, 'run', side_effect=admin.subprocess.TimeoutExpired(
        cmd='safe-command', timeout=120,
    )):
        assert admin._run_command('safe-command', [], False) == (
            False, '', 'Command timed out after 120 seconds.'
        )
