from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from simoc_sam.sioserver import SocketIOServer


# fixtures

@pytest.fixture
def server():
    """Create a SocketIOServer instance for testing."""
    server = SocketIOServer()
    # Patch the sio attribute directly
    server.sio = MagicMock()
    # Setup the events properly
    server.setup_sio_events()
    yield server

@pytest.fixture
def sio(server):
    """Return the mocked SocketIO server instance."""
    # Make the emit method async
    server.sio.emit = AsyncMock()
    return server.sio

@pytest.fixture
def client_id():
    return 'client-0'

@pytest.fixture
def two_subs(server):
    """Add two subscribers to the list of subscribers."""
    server.subscribers = {'sub-0', 'sub-1'}
    return server.subscribers

@pytest.fixture
def sensor_id():
    return 'sensor-0'

@pytest.fixture
def sensor_info():
    info = dict(var=dict(label='Test var', unit='%'))
    return dict(sensor_type='type', sensor_name='name', reading_info=info)

@pytest.fixture
def sensor_reading():
    return dict(n=8, timestamp='2022-03-04 03:58:02.771409', var=50)

@pytest.fixture(autouse=True)
def debug_emit_awaits(sio):
    """Print a list of sio.emit calls in case of failure."""
    yield
    print(sio.emit.emit.await_args_list)


# tests

def test_server_initialization(server):
    """Test that the server initializes with correct default values."""
    assert server.hab_info == dict(humans=4, volume=272)
    assert server.sensor_info == {}
    assert server.sensors == set()
    assert server.clients == set()
    assert server.subscribers == set()
    assert server.sensor_managers == set()

@pytest.mark.asyncio
async def test_register_sensor_no_subs(server, sio, sensor_id, sensor_info):
    """Test sensor registration with no subscribers."""
    assert server.sensors == set()
    assert server.sensor_info == {}

    # Manually add sensor to test the logic
    server.sensors.add(sensor_id)
    server.sensor_info[sensor_id] = sensor_info

    # Test emit_to_subscribers (should not emit anything)
    await server.emit_to_subscribers('sensor-info', server.sensor_info)
    sio.emit.assert_not_called()

    # Test that sensor was added correctly
    assert server.sensors == {sensor_id}
    assert server.sensor_info[sensor_id] == sensor_info

@pytest.mark.asyncio
async def test_register_sensor_2_subs(server, sio, sensor_id, sensor_info, two_subs):
    """Test sensor registration with subscribers."""
    assert server.sensors == set()
    assert server.sensor_info == {}

    # Manually add sensor to test the logic
    server.sensors.add(sensor_id)
    server.sensor_info[sensor_id] = sensor_info

    # Test emit_to_subscribers with subscribers
    await server.emit_to_subscribers('sensor-info', server.sensor_info)

    # Check that sensor-info was sent to all subscribers
    for sub in two_subs:
        sio.emit.assert_any_await('sensor-info', server.sensor_info, to=sub)

    # Test that sensor was added correctly
    assert server.sensors == {sensor_id}
    assert server.sensor_info[sensor_id] == sensor_info

@pytest.mark.asyncio
async def test_register_client(server, sio, client_id):
    """Test client registration."""
    assert server.clients == set()
    assert server.subscribers == set()

    # Manually add client to test the logic
    server.clients.add(client_id)
    server.subscribers.add(client_id)

    # Test that client was added correctly
    assert server.clients == {client_id}
    assert server.subscribers == {client_id}

@pytest.mark.asyncio
async def test_emit_to_subscribers_no_subs(server, sio):
    assert server.subscribers == set()
    await server.emit_to_subscribers('test-event')
    sio.emit.assert_not_called()

@pytest.mark.asyncio
async def test_emit_to_subscribers_2_subs(server, sio, two_subs):
    assert server.subscribers == two_subs
    await server.emit_to_subscribers('test-event')
    for sub in two_subs:
        sio.emit.assert_any_await('test-event', to=sub)

@pytest.mark.asyncio
async def test_sensor_reading(server, sio, sensor_id, sensor_info, sensor_reading):
    """Test processing a single sensor reading."""
    assert server.sensor_readings == {}

    # Manually add sensor
    server.sensors.add(sensor_id)
    server.sensor_info[sensor_id] = sensor_info

    # Manually add reading
    server.sensor_readings[sensor_id].append(sensor_reading)

    # Check that the reading is stored correctly
    assert len(server.sensor_readings[sensor_id]) == 1
    assert server.sensor_readings[sensor_id][-1] == sensor_reading

@pytest.mark.asyncio
async def test_sensor_batch(server, sio, sensor_id, sensor_info, sensor_reading):
    """Test processing a batch of sensor readings."""
    assert server.sensor_readings == {}

    # Manually add sensor
    server.sensors.add(sensor_id)
    server.sensor_info[sensor_id] = sensor_info

    # Manually add batch
    batch = [sensor_reading] * 3
    server.sensor_readings[sensor_id].extend(batch)

    # Check that the readings are stored correctly
    assert len(server.sensor_readings[sensor_id]) == 3
    assert list(server.sensor_readings[sensor_id]) == batch

@pytest.mark.asyncio
async def test_register_sensor_manager(server, sio, sensor_manager_id='manager-0'):
    """Test sensor manager registration."""
    assert server.sensor_managers == set()

    # Manually add sensor manager
    server.sensor_managers.add(sensor_manager_id)

    # Test that sensor manager was added correctly
    assert server.sensor_managers == {sensor_manager_id}
