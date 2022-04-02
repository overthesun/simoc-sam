from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

import sioserver


# fixtures

@pytest.fixture
def global_vars():
    """Return a list of module-level state vars."""
    return ['HAB_INFO', 'SENSOR_INFO', 'SENSOR_READINGS',
            'SENSORS', 'CLIENTS', 'SUBSCRIBERS']

@pytest.fixture(autouse=True)
def reset_global_vars(global_vars):
    """Create a copy of the module-level vars and restore it at the end."""
    with ExitStack() as stack:
        for var in global_vars:
            var_name = 'sioserver.' + var
            new_value = deepcopy(getattr(sioserver, var))
            stack.enter_context(patch(var_name, new_value))
        yield

@pytest.fixture
def sio():
    """Replace sioserver.sio with an AsyncMock and return it."""
    with patch('sioserver.sio', AsyncMock()) as mocksio:
        yield mocksio

@pytest.fixture
def client_id():
    return 'client-0'

@pytest.fixture
def two_subs():
    """Add two subscribers to the list of subscribers."""
    with patch('sioserver.SUBSCRIBERS', {'sub-0', 'sub-1'}) as subs:
        yield subs

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
    print(sio.emit.await_args_list)


# tests

def test_global_variables(global_vars):
    for var in global_vars:
        # check that the module-level vars exist
        assert hasattr(sioserver, var)

@pytest.mark.asyncio
async def test_register_sensor_no_subs(sio, sensor_id, sensor_info):
    assert sioserver.SENSORS == set()
    assert sioserver.SENSOR_INFO == {}
    await sioserver.register_sensor(sensor_id, sensor_info)
    # check that the sensor is in the sensors list
    assert sioserver.SENSORS == {sensor_id}
    assert sioserver.SENSOR_INFO[sensor_id] == sensor_info
    # with no subs, the server only asks the sensor to send data
    sio.emit.assert_awaited_once_with('send-data', to=sensor_id)

@pytest.mark.asyncio
async def test_register_sensor_2_subs(sio, sensor_id, sensor_info, two_subs):
    await sioserver.register_sensor(sensor_id, sensor_info)
    assert sioserver.SENSORS == {sensor_id}
    # check that the SENSOR_INFO are populated correctly
    info = {sensor_id: sensor_info}
    assert sioserver.SENSOR_INFO == info
    # check that sensor-info are forwarded to the subscribers
    for sub in two_subs:
        sio.emit.assert_any_await('sensor-info', info, to=sub)
    # check that the server asks the sensor to send data
    sio.emit.assert_awaited_with('send-data', to=sensor_id)

@pytest.mark.asyncio
async def test_register_client(sio, client_id):
    assert sioserver.CLIENTS == set()
    assert sioserver.SUBSCRIBERS == set()
    await sioserver.register_client(client_id)
    # check that the client is in the clients and subscribers lists
    assert sioserver.CLIENTS == {client_id}
    assert sioserver.SUBSCRIBERS == {client_id}
    # check that habitata and sensor info are sent to the client
    sio.emit.assert_any_await('hab-info', sioserver.HAB_INFO, to=client_id)
    sio.emit.assert_awaited_with('sensor-info', sioserver.SENSOR_INFO,
                                 to=client_id)

@pytest.mark.asyncio
async def test_emit_to_subscribers_no_subs(sio):
    assert sioserver.SUBSCRIBERS == set()
    await sioserver.emit_to_subscribers('test-event')
    sio.emit.assert_not_awaited()

@pytest.mark.asyncio
async def test_emit_to_subscribers_2_subs(sio, two_subs):
    assert sioserver.SUBSCRIBERS == two_subs
    await sioserver.emit_to_subscribers('test-event')
    for sub in two_subs:
        sio.emit.assert_any_await('test-event', to=sub)


@pytest.mark.asyncio
async def test_sensor_reading(sio, sensor_id, sensor_info, sensor_reading):
    assert sioserver.SENSOR_READINGS == {}
    # register sensor
    # TODO: turn this into a fixture?
    await sioserver.register_sensor(sensor_id, sensor_info)
    # send a reading to the server
    await sioserver.sensor_reading(sensor_id, sensor_reading)
    # check that the reading is stored in SENSOR_READINGS
    assert len(sioserver.SENSOR_READINGS[sensor_id]) == 1
    assert sioserver.SENSOR_READINGS[sensor_id][-1] == sensor_reading


@pytest.mark.asyncio
async def test_sensor_batch(sio, sensor_id, sensor_info, sensor_reading):
    assert sioserver.SENSOR_READINGS == {}
    # register sensor
    await sioserver.register_sensor(sensor_id, sensor_info)
    # send a batch to the server
    batch = [sensor_reading] * 3
    await sioserver.sensor_batch(sensor_id, batch)
    # check that the readings are stored in SENSOR_READINGS
    assert len(sioserver.SENSOR_READINGS[sensor_id]) == 3
    assert list(sioserver.SENSOR_READINGS[sensor_id]) == batch
