import json

from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from simoc_sam import mqttbridge


# fixtures

@pytest.fixture
def global_vars():
    """Return a list of module-level state vars."""
    return ['HAB_INFO', 'SENSOR_DATA', 'SENSOR_INFO', 'SENSOR_READINGS',
            'SENSORS', 'CLIENTS', 'SUBSCRIBERS']

@pytest.fixture(autouse=True)
def reset_global_vars(global_vars):
    """Create a copy of the module-level vars and restore it at the end."""
    with ExitStack() as stack:
        for var in global_vars:
            var_name = 'simoc_sam.mqttbridge.' + var
            new_value = deepcopy(getattr(mqttbridge, var))
            stack.enter_context(patch(var_name, new_value))
        yield

@pytest.fixture
def sio():
    """Replace mqttbridge.sio with an AsyncMock and return it."""
    with patch('simoc_sam.mqttbridge.sio', AsyncMock()) as mocksio:
        yield mocksio

@pytest.fixture
def sio_sleep_break(sio):
    """Patch sio.sleep to raise an exception to break an endless loop."""
    sio.sleep.side_effect = RuntimeError("Break loop")
    yield sio

@pytest.fixture
def client_id():
    return 'client-0'

@pytest.fixture
def sensor_id():
    return 'Mock'

@pytest.fixture
def sensor_info(sensor_id):
    return mqttbridge.SENSOR_DATA[sensor_id]

@pytest.fixture(autouse=True)
def patch_sensor_info():
    """Initialize SENSOR_INFO with test data for each test."""
    with patch('simoc_sam.mqttbridge.SENSOR_INFO', {}):
        yield

@pytest.fixture
def two_subs():
    """Add two subscribers to the list of subscribers."""
    with patch('simoc_sam.mqttbridge.SUBSCRIBERS', {'sub-0', 'sub-1'}) as subs:
        yield subs

@pytest.fixture
def mock_emit_to_subscribers():
    """Patch emit_to_subscribers and yield the mock."""
    with patch('simoc_sam.mqttbridge.emit_to_subscribers', new_callable=AsyncMock) as mock_emit:
        yield mock_emit

@pytest.fixture
def sensor_reading():
    return dict(n=8, timestamp='2022-03-04 03:58:02.771409', var=50)

@pytest.fixture
def step_batch(sensor_id, sensor_reading):
    """Create a step-batch bundle using the sensor reading."""
    return [{
        'n': 0,
        'timestamp': '2022-03-04 03:58:02',
        'readings': {sensor_id: sensor_reading}
    }]

@pytest.fixture
def mqtt_message(sensor_id):
    """Create a mock MQTT message."""
    message = MagicMock()
    message.topic.value = f'sam/samrpi1/{sensor_id}'
    message.payload = json.dumps({
        'n': 1,
        'timestamp': '2022-03-04 03:58:02.771409',
        'temperature': 25.5
    }).encode()
    return message

@pytest.fixture
def mock_get_timestamp():
    """Patch get_timestamp to return a predictable value."""
    with patch('simoc_sam.mqttbridge.get_timestamp', return_value='2022-03-04 03:58:02'):
        yield

@pytest.fixture
def mock_mqtt_client():
    """Patch aiomqtt.Client and yield the mock client instance."""
    with patch('simoc_sam.mqttbridge.aiomqtt.Client') as client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.subscribe = AsyncMock()
        client_cls.return_value = mock_client
        yield mock_client

@pytest.fixture
def break_after_message():
    """Create a message iterator that raises an exception after yielding messages."""
    def create_message_iter(*messages):
        async def message_iter():
            for message in messages:
                yield message
            # After yielding all messages, raise an exception to break the async for loop
            raise RuntimeError("break loop")
        return message_iter()
    return create_message_iter

@pytest.fixture(autouse=True)
def mock_parse_args():
    """Patch parse_args to return consistent test arguments."""
    with patch('simoc_sam.mqttbridge.utils.parse_args') as mock_args:
        mock_args.return_value.host = 'localhost'
        mock_args.return_value.mqtt_topic = 'sam/#'
        mock_args.return_value.delay = 1
        yield mock_args

@pytest.fixture(autouse=True)
def debug_emit_awaits(sio):
    """Print a list of sio.emit calls in case of failure."""
    yield
    print(sio.emit.await_args_list)


# tests for existing SocketIO functionality (clients still connect via SocketIO)

def test_global_variables(global_vars):
    for var in global_vars:
        # check that the module-level vars exist
        assert hasattr(mqttbridge, var)

@pytest.mark.asyncio
async def test_register_sensor_no_subs(sio, sensor_id, sensor_info):
    """Test SocketIO sensor registration (legacy functionality)."""
    assert mqttbridge.SENSORS == set()
    assert mqttbridge.SENSOR_INFO == {}
    await mqttbridge.register_sensor(sensor_id, sensor_info)
    # check that the sensor is in the sensors list
    assert mqttbridge.SENSORS == {sensor_id}
    assert mqttbridge.SENSOR_INFO[sensor_id] == sensor_info
    # with no subs, the server only asks the sensor to send data
    sio.emit.assert_awaited_once_with('send-data', to=sensor_id)

@pytest.mark.asyncio
async def test_register_sensor_2_subs(sio, sensor_id, sensor_info, two_subs):
    """Test SocketIO sensor registration with subscribers."""
    await mqttbridge.register_sensor(sensor_id, sensor_info)
    assert mqttbridge.SENSORS == {sensor_id}
    # check that the SENSOR_INFO are populated correctly
    info = {sensor_id: sensor_info}
    assert mqttbridge.SENSOR_INFO == info
    # check that sensor-info are forwarded to the subscribers
    for sub in two_subs:
        sio.emit.assert_any_await('sensor-info', info, to=sub)
    # check that the server asks the sensor to send data
    sio.emit.assert_awaited_with('send-data', to=sensor_id)

@pytest.mark.asyncio
async def test_register_client(sio, client_id):
    """Test SocketIO client registration."""
    assert mqttbridge.CLIENTS == set()
    assert mqttbridge.SUBSCRIBERS == set()
    await mqttbridge.register_client(client_id)
    # check that the client is in the clients and subscribers lists
    assert mqttbridge.CLIENTS == {client_id}
    assert mqttbridge.SUBSCRIBERS == {client_id}
    # check that habitat and sensor info are sent to the client
    sio.emit.assert_any_await('hab-info', mqttbridge.HAB_INFO, to=client_id)
    sio.emit.assert_awaited_with('sensor-info', mqttbridge.SENSOR_INFO,
                                 to=client_id)

@pytest.mark.asyncio
async def test_emit_to_subscribers_no_subs(sio):
    """Test emitting to subscribers when none exist."""
    assert mqttbridge.SUBSCRIBERS == set()
    await mqttbridge.emit_to_subscribers('test-event')
    sio.emit.assert_not_awaited()

@pytest.mark.asyncio
async def test_emit_to_subscribers_2_subs(sio, two_subs):
    """Test emitting to multiple subscribers."""
    assert mqttbridge.SUBSCRIBERS == two_subs
    await mqttbridge.emit_to_subscribers('test-event')
    for sub in two_subs:
        sio.emit.assert_any_await('test-event', to=sub)

@pytest.mark.asyncio
async def test_sensor_reading(sio, sensor_id, sensor_info, sensor_reading):
    """Test receiving sensor reading via SocketIO."""
    assert mqttbridge.SENSOR_READINGS == {}
    # register sensor
    await mqttbridge.register_sensor(sensor_id, sensor_info)
    # send a reading to the server
    await mqttbridge.sensor_reading(sensor_id, sensor_reading)
    # check that the reading is stored in SENSOR_READINGS
    assert len(mqttbridge.SENSOR_READINGS[sensor_id]) == 1
    assert mqttbridge.SENSOR_READINGS[sensor_id][-1] == sensor_reading

@pytest.mark.asyncio
async def test_sensor_batch(sio, sensor_id, sensor_info, sensor_reading):
    """Test receiving sensor batch via SocketIO."""
    assert mqttbridge.SENSOR_READINGS == {}
    # register sensor
    await mqttbridge.register_sensor(sensor_id, sensor_info)
    # send a batch to the server
    batch = [sensor_reading] * 3
    await mqttbridge.sensor_batch(sensor_id, batch)
    # check that the readings are stored in SENSOR_READINGS
    assert len(mqttbridge.SENSOR_READINGS[sensor_id]) == 3
    assert list(mqttbridge.SENSOR_READINGS[sensor_id]) == batch


# tests for new MQTT functionality

@pytest.mark.asyncio
async def test_mqtt_handler_new_sensor(mqtt_message, mock_mqtt_client,
                                       break_after_message, mock_emit_to_subscribers):
    """Test MQTT handler registering a new sensor, using real handler logic."""
    def assert_globals_count(expected_count):
        assert len(mqttbridge.SENSORS) == expected_count
        assert len(mqttbridge.SENSOR_INFO) == expected_count
        assert len(mqttbridge.SENSOR_READINGS) == expected_count
    assert_globals_count(expected_count=0)
    # set up the mock client's messages to yield our test message, then break
    mock_mqtt_client.messages = break_after_message(mqtt_message)
    with pytest.raises(RuntimeError, match="break loop"):
        await mqttbridge.mqtt_handler()
    # check that the sensor was registered
    assert_globals_count(expected_count=1)
    mock_emit_to_subscribers.assert_awaited_once_with('sensor-info', mqttbridge.SENSOR_INFO)
    mock_emit_to_subscribers.reset_mock()
    # check that receiving another message from the same sensor doesn't re-register it
    mock_mqtt_client.messages = break_after_message(mqtt_message)
    with pytest.raises(RuntimeError, match="break loop"):
        await mqttbridge.mqtt_handler()
    assert_globals_count(expected_count=1)
    mock_emit_to_subscribers.assert_not_awaited()

@pytest.mark.asyncio
async def test_convert_sensor_data():
    """Test the convert_sensor_data function."""
    # convert_sensor_data is called at the beginning and the result assigned to SENSOR_DATA
    assert mqttbridge.SENSOR_DATA
    for sensor_name, sensor_info in mqttbridge.SENSOR_DATA.items():
        assert sensor_name and isinstance(sensor_name, str)
        assert isinstance(sensor_info['sensor_type'], str)
        assert sensor_info['sensor_name'] is None
        assert sensor_info['sensor_id'] is None
        assert sensor_info['sensor_desc'] is None
        assert isinstance(sensor_info['reading_info'], dict)

@pytest.mark.asyncio
async def test_emit_readings(sio, sio_sleep_break, sensor_id, two_subs, sensor_reading,
                             step_batch, mock_get_timestamp):
    """Test the emit_readings function with one message and two subscribers."""
    # add a sensor readings to emit
    mqttbridge.SENSOR_READINGS[sensor_id].append(sensor_reading)
    with pytest.raises(RuntimeError, match="Break loop"):
        await mqttbridge.emit_readings()
    # Check that step-batch was emitted to both subscribers
    for sub in two_subs:
        sio.emit.assert_any_await('step-batch', step_batch, to=sub)
