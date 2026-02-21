import json
import asyncio

from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from simoc_sam import siobridge
from simoc_sam.sensors.basesensor import get_sensor_id
from conftest import wait_until, terminate_task


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
            var_name = 'simoc_sam.siobridge.' + var
            new_value = deepcopy(getattr(siobridge, var))
            stack.enter_context(patch(var_name, new_value))
        yield

@pytest.fixture
def sio():
    """Replace siobridge.sio with an AsyncMock and return it."""
    with patch('simoc_sam.siobridge.sio', AsyncMock()) as mocksio:
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
    return get_sensor_id('mock')

@pytest.fixture
def sensor_info(sensor_id):
    return siobridge.SENSOR_DATA[sensor_id]

@pytest.fixture(autouse=True)
def patch_sensor_info():
    """Initialize SENSOR_INFO with test data for each test."""
    with patch('simoc_sam.siobridge.SENSOR_INFO', {}):
        yield

@pytest.fixture
def two_subs():
    """Add two subscribers to the list of subscribers."""
    with patch('simoc_sam.siobridge.SUBSCRIBERS', {'sub-0', 'sub-1'}) as subs:
        yield subs

@pytest.fixture
def mock_emit_to_subscribers():
    """Patch emit_to_subscribers and yield the mock."""
    with patch('simoc_sam.siobridge.emit_to_subscribers', new_callable=AsyncMock) as mock_emit:
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
def mqtt_message():
    """Create a mock MQTT message."""
    message = MagicMock()
    # Topic format is location/hostname/sensor_name
    message.topic.value = get_sensor_id('mock', sep='/')
    message.payload = json.dumps({
        'n': 1,
        'timestamp': '2022-03-04 03:58:02.771409',
        'temperature': 25.5
    }).encode()
    return message

@pytest.fixture
def mock_get_timestamp():
    """Patch get_timestamp to return a predictable value."""
    with patch('simoc_sam.siobridge.get_timestamp', return_value='2022-03-04 03:58:02'):
        yield

@pytest.fixture
def mock_mqtt_client():
    """Patch aiomqtt.Client and yield the mock client instance."""
    with patch('simoc_sam.siobridge.aiomqtt.Client') as client_cls:
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
    with patch('simoc_sam.sensors.utils.parse_args') as mock_args:
        mock_args.return_value.host = 'localhost'
        mock_args.return_value.mqtt_topic = 'sam/#'
        mock_args.return_value.delay = 1
        yield mock_args

@pytest.fixture(autouse=True)
def debug_emit_awaits(sio):
    """Print a list of sio.emit calls in case of failure."""
    yield
    print(sio.emit.await_args_list)


# tests for SocketIO functionality (used by clients)

def test_global_variables(global_vars):
    for var in global_vars:
        # check that the module-level vars exist
        assert hasattr(siobridge, var)

@pytest.mark.asyncio
async def test_register_client(sio, client_id):
    """Test SocketIO client registration."""
    assert siobridge.CLIENTS == set()
    assert siobridge.SUBSCRIBERS == set()
    await siobridge.register_client(client_id)
    # check that the client is in the clients and subscribers lists
    assert siobridge.CLIENTS == {client_id}
    assert siobridge.SUBSCRIBERS == {client_id}
    # check that habitat and sensor info are sent to the client
    sio.emit.assert_any_await('hab-info', siobridge.HAB_INFO, to=client_id)
    sio.emit.assert_awaited_with('sensor-info', siobridge.SENSOR_INFO,
                                 to=client_id)

@pytest.mark.asyncio
async def test_emit_to_subscribers_no_subs(sio):
    """Test emitting to subscribers when none exist."""
    assert siobridge.SUBSCRIBERS == set()
    await siobridge.emit_to_subscribers('test-event')
    sio.emit.assert_not_awaited()

@pytest.mark.asyncio
async def test_emit_to_subscribers_2_subs(sio, two_subs):
    """Test emitting to multiple subscribers."""
    assert siobridge.SUBSCRIBERS == two_subs
    await siobridge.emit_to_subscribers('test-event')
    for sub in two_subs:
        sio.emit.assert_any_await('test-event', to=sub)


# tests for MQTT functionality

@pytest.mark.asyncio
async def test_convert_sensor_data():
    """Test the convert_sensor_data function."""
    # convert_sensor_data is called at the beginning and the result assigned to SENSOR_DATA
    assert siobridge.SENSOR_DATA
    for sensor_name, sensor_info in siobridge.SENSOR_DATA.items():
        assert sensor_name and isinstance(sensor_name, str)
        assert isinstance(sensor_info['sensor_type'], str)
        assert sensor_info['sensor_name'] == sensor_name
        assert sensor_info['sensor_id'] is None
        assert sensor_info['sensor_desc'] is None
        assert isinstance(sensor_info['reading_info'], dict)

@pytest.mark.asyncio
async def test_mqtt_handler_new_sensor(mqtt_message, mock_mqtt_client,
                                       break_after_message, mock_emit_to_subscribers):
    """Test MQTT handler registering a new sensor, using real handler logic."""
    def assert_globals_count(expected_count):
        assert len(siobridge.SENSORS) == expected_count
        assert len(siobridge.SENSOR_INFO) == expected_count
        assert len(siobridge.SENSOR_READINGS) == expected_count
    assert_globals_count(expected_count=0)
    # set up the mock client's messages to yield our test message, then break
    mock_mqtt_client.messages = break_after_message(mqtt_message)
    with pytest.raises(RuntimeError, match="break loop"):
        await siobridge.mqtt_handler()
    # check that the sensor was registered
    assert_globals_count(expected_count=1)
    mock_emit_to_subscribers.assert_awaited_once_with('sensor-info', siobridge.SENSOR_INFO)
    mock_emit_to_subscribers.reset_mock()
    # check that receiving another message from the same sensor doesn't re-register it
    mock_mqtt_client.messages = break_after_message(mqtt_message)
    with pytest.raises(RuntimeError, match="break loop"):
        await siobridge.mqtt_handler()
    assert_globals_count(expected_count=1)
    mock_emit_to_subscribers.assert_not_awaited()

@pytest.mark.asyncio
async def test_emit_readings(sio, sio_sleep_break, sensor_id, two_subs, sensor_reading,
                             step_batch, mock_get_timestamp):
    """Test the emit_readings function with one message and two subscribers."""
    # add a sensor readings to emit
    siobridge.SENSOR_READINGS[sensor_id].append(sensor_reading)
    with pytest.raises(RuntimeError, match="Break loop"):
        await siobridge.emit_readings()
    # Check that step-batch was emitted to both subscribers
    for sub in two_subs:
        sio.emit.assert_any_await('step-batch', step_batch, to=sub)



# tests for log file functionality

@pytest.mark.asyncio
async def test_process_sensor_log(mock_emit_to_subscribers):
    """Test that process_sensor_log registers sensor in SENSOR_INFO."""
    sensor_name = 'scd30'
    sensor_id = get_sensor_id(sensor_name)
    # verify sensor not registered yet
    assert sensor_id not in siobridge.SENSORS
    assert sensor_id not in siobridge.SENSOR_INFO
    # mock read_jsonl_file to avoid actual file I/O
    async def mock_read_jsonl():
        yield {'n': 0, 'co2': 400}  # yield one reading then stop
    with patch('simoc_sam.utils.read_jsonl_file', return_value=mock_read_jsonl()):
        # start processing the log
        process_task = asyncio.create_task(siobridge.process_sensor_log(sensor_name))
        # wait for sensor to be registered
        await wait_until(lambda: sensor_id in siobridge.SENSORS)
        # verify sensor was registered
        assert sensor_id in siobridge.SENSOR_INFO
        assert siobridge.SENSOR_INFO[sensor_id]['sensor_name'] == sensor_name
        mock_emit_to_subscribers.assert_awaited_once_with('sensor-info',
                                                          siobridge.SENSOR_INFO)
        # verify reading was added
        readings = siobridge.SENSOR_READINGS[sensor_id]
        assert len(readings) == 1
        assert readings[0] == {'n': 0, 'co2': 400}
        # wait for task to complete
        await process_task

@pytest.mark.asyncio
async def test_log_handler_creates_tasks(temp_log_dir):
    """Test that log_handler creates processing tasks for configured sensors."""
    async def mock_process_sensor_log(sensor):
        await asyncio.sleep(10)
    with patch('simoc_sam.siobridge.config') as mock_config, \
         patch('simoc_sam.siobridge.process_sensor_log') as mock_process:
        mock_config.log_dir = temp_log_dir
        mock_config.sensors = ['scd30', 'bme688']
        mock_process.side_effect = mock_process_sensor_log
        # start log_handler
        handler_task = asyncio.create_task(siobridge.log_handler())
        # wait for tasks to be created
        await wait_until(lambda: mock_process.call_count == 2)
        # verify process_sensor_log was called for each sensor
        mock_process.assert_any_call('scd30')
        mock_process.assert_any_call('bme688')
        # clean up
        await terminate_task(handler_task)

@pytest.mark.asyncio
async def test_log_handler_missing_directory():
    """Test that log_handler raises FileNotFoundError for missing directory."""
    with patch('simoc_sam.siobridge.config') as mock_config:
        mock_config.log_dir = '/nonexistent/directory'
        with pytest.raises(FileNotFoundError, match='Log directory does not exist'):
            await siobridge.log_handler()
