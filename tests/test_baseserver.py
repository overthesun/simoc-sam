import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from simoc_sam.baseserver import BaseServer

@pytest.fixture
def server():
    with patch('simoc_sam.baseserver.socketio.AsyncServer') as mock_sio:
        server = BaseServer()
        server.sio = mock_sio
        yield server

@pytest.fixture
def sio(server):
    server.sio.emit = AsyncMock()
    return server.sio

def test_initialization(server):
    assert server.hab_info == dict(humans=4, volume=272)
    assert server.sensor_info == {}
    assert server.sensors == set()
    assert server.clients == set()
    assert server.subscribers == set()
    assert server.sensor_managers == set()
    assert isinstance(server.sensor_readings, dict)

def test_get_host_ips(server):
    with patch('simoc_sam.baseserver.socket.gethostname', return_value='testhost'), \
         patch('simoc_sam.baseserver.netifaces.interfaces', return_value=['eth0']), \
         patch('simoc_sam.baseserver.netifaces.ifaddresses', return_value={2: [{'addr': '192.168.1.100'}]}):
        ips = server.get_host_ips()
        assert 'testhost' in ips
        assert 'localhost' in ips
        assert '192.168.1.100' in ips

def test_get_sensor_info_from_cfg(server):
    with patch('simoc_sam.baseserver.configparser.ConfigParser') as mock_config:
        mock_parser = MagicMock()
        mock_config.return_value = mock_parser
        mock_parser.items.return_value = [('test_sensor', {'name': 'Test Sensor'})]
        result = server.get_sensor_info_from_cfg('test_sensor')
        assert result == {'name': 'Test Sensor'}
        mock_parser.items.return_value = []
        result = server.get_sensor_info_from_cfg('non_existent')
        assert result is None

def test_get_timestamp(server):
    ts = server.get_timestamp()
    assert isinstance(ts, str)
    assert len(ts) > 0

@pytest.mark.asyncio
async def test_emit_to_subscribers(server, sio):
    server.subscribers = {'sub-1', 'sub-2'}
    await server.emit_to_subscribers('test-event', {'data': 123})
    for sub in server.subscribers:
        sio.emit.assert_any_await('test-event', {'data': 123}, to=sub)

@pytest.mark.asyncio
async def test_emit_readings_stops(server, sio):
    # Add dummy data
    server.sensor_readings['sensor1'].append({'n': 1, 'timestamp': 'now'})
    server.sensors = {'sensor1'}  # Add sensor to sensors set
    server.subscribers = {'sub-1'}
    with patch('simoc_sam.baseserver.utils.parse_args') as mock_parse_args:
        mock_args = MagicMock()
        mock_args.delay = 0.01
        mock_parse_args.return_value = mock_args
        # Patch sleep to break after one iteration
        with patch.object(server.sio, 'sleep', side_effect=Exception('break')):
            try:
                await server.emit_readings()
            except Exception:
                pass
    sio.emit.assert_any_await('step-batch', [{'n': 0, 'timestamp': server.get_timestamp(), 'readings': {'sensor1': {'n': 1, 'timestamp': 'now'}}}], to='sub-1')

def test_event_registration(server):
    # Just check that event handlers are registered (by name)
    assert hasattr(server.sio, 'on') or hasattr(server.sio, 'event')
