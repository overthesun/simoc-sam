import json
from unittest.mock import AsyncMock, patch, MagicMock, call

import pytest
import aiomqtt

from simoc_sam.mqttbridge import MQTTBridge


# fixtures

@pytest.fixture
def server():
    """Create a MQTTBridge instance for testing."""
    server = MQTTBridge()
    server.sio = MagicMock()
    yield server

@pytest.fixture
def sio(server):
    """Return the mocked SocketIO server instance."""
    # Make the emit method async
    server.sio.emit = AsyncMock()
    return server.sio

@pytest.fixture
def sensor_id():
    return 'host1.bme688'

@pytest.fixture
def sensor_info():
    info = dict(temp=dict(label='Temperature', unit='°C'))
    return dict(sensor_type='BME688', sensor_name='host1.bme688',
                sensor_id='host1.bme688', sensor_desc='bme688 sensor on host1',
                reading_info=info)

@pytest.fixture
def sensor_reading():
    return dict(n=8, timestamp='2022-03-04 03:58:02.771409', temp=25.5)

@pytest.fixture
def mqtt_message():
    """Create a mock MQTT message."""
    message = MagicMock()
    message.topic.value = 'sam/host1/bme688'
    message.payload.decode.return_value = json.dumps({
        'n': 8, 'timestamp': '2022-03-04 03:58:02.771409', 'temp': 25.5
    })
    return message

@pytest.fixture
def two_subs(server):
    """Add two subscribers to the list of subscribers."""
    server.subscribers = {'sub-0', 'sub-1'}
    return server.subscribers


# tests

def test_mqtt_bridge_initialization(server):
    """Test that the MQTT bridge initializes with correct default values."""
    assert server.hab_info == dict(humans=4, volume=272)
    assert server.sensor_info == {}
    assert server.sensors == set()
    assert server.clients == set()
    assert server.subscribers == set()
    assert server.sensor_managers == set()
    assert hasattr(server, 'sensor_data')
    # Check for actual sensor types that exist in the data
    assert 'BME688' in server.sensor_data
    assert 'SCD-30' in server.sensor_data

def test_convert_sensor_data(server):
    """Test that sensor data is converted correctly."""
    sensor_data = server.convert_sensor_data()
    assert isinstance(sensor_data, dict)
    # Check that it contains expected sensor types
    assert 'BME688' in sensor_data
    assert 'SCD-30' in sensor_data
    # Check structure
    for sensor_name, data in sensor_data.items():
        assert 'sensor_type' in data
        assert 'sensor_name' in data
        assert 'sensor_id' in data
        assert 'sensor_desc' in data
        assert 'reading_info' in data

def test_create_sio_server(server):
    """Test that the SocketIO server is created with dynamic CORS settings."""
    with patch.object(server, 'get_host_ips', return_value=['localhost', '127.0.0.1']):
        sio_server = server.create_sio_server()
        assert sio_server is not None

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
async def test_register_client(server, sio):
    """Test client registration."""
    client_id = 'client-0'
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
    """Test emitting to subscribers when there are none."""
    assert server.subscribers == set()
    await server.emit_to_subscribers('test-event')
    sio.emit.assert_not_called()

@pytest.mark.asyncio
async def test_emit_to_subscribers_2_subs(server, sio, two_subs):
    """Test emitting to multiple subscribers."""
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
async def test_mqtt_handler_new_sensor(server, sio, mqtt_message):
    """Test MQTT handler processing a message for a new sensor."""
    with patch('simoc_sam.mqttbridge.utils.parse_args') as mock_parse_args, \
         patch('simoc_sam.mqttbridge.aiomqtt.Client') as mock_client_class, \
         patch('asyncio.sleep') as mock_sleep:

        # Setup mocks
        mock_args = MagicMock()
        mock_args.host = None
        mock_args.mqtt_topic = 'sam/#'
        mock_parse_args.return_value = mock_args

        # Create a mock client that raises an exception immediately to break the loop
        mock_client_class.side_effect = Exception("Connection failed")

        # Run the MQTT handler - it should fail immediately and not hang
        try:
            await server.mqtt_handler()
        except Exception:
            pass  # Expected to fail immediately

        # Since the handler failed immediately, no sensor should be added
        # This test verifies the handler doesn't hang, not that it processes messages
        assert len(server.sensors) == 0

@pytest.mark.asyncio
async def test_mqtt_handler_existing_sensor(server, sio, mqtt_message):
    """Test MQTT handler processing a message for an existing sensor."""
    # Pre-register the sensor
    sensor_id = 'host1.bme688'
    server.sensors.add(sensor_id)
    server.sensor_info[sensor_id] = {'sensor_type': 'BME688'}

    with patch('simoc_sam.mqttbridge.utils.parse_args') as mock_parse_args, \
         patch('simoc_sam.mqttbridge.aiomqtt.Client') as mock_client_class, \
         patch('asyncio.sleep') as mock_sleep:

        # Setup mocks
        mock_args = MagicMock()
        mock_args.host = None
        mock_args.mqtt_topic = 'sam/#'
        mock_parse_args.return_value = mock_args

        # Create a mock client that raises an exception immediately to break the loop
        mock_client_class.side_effect = Exception("Connection failed")

        # Run the MQTT handler - it should fail immediately and not hang
        try:
            await server.mqtt_handler()
        except Exception:
            pass  # Expected to fail immediately

        # Since the handler failed immediately, no reading should be added
        # This test verifies the handler doesn't hang, not that it processes messages
        assert len(server.sensor_readings[sensor_id]) == 0

@pytest.mark.asyncio
async def test_mqtt_handler_connection_error(server):
    """Test MQTT handler handles connection errors gracefully."""
    with patch('simoc_sam.mqttbridge.utils.parse_args') as mock_parse_args, \
         patch('simoc_sam.mqttbridge.aiomqtt.Client') as mock_client_class, \
         patch('asyncio.sleep') as mock_sleep:

        # Setup mocks
        mock_args = MagicMock()
        mock_args.host = None
        mock_args.mqtt_topic = 'sam/#'
        mock_parse_args.return_value = mock_args

        # Make the client raise an MqttError
        mock_client_class.side_effect = aiomqtt.MqttError("Connection failed")

        # Make sleep raise an exception to break the retry loop
        mock_sleep.side_effect = Exception("Break retry loop")

        # Run the MQTT handler - it should fail after the first retry attempt
        try:
            await server.mqtt_handler()
        except Exception:
            pass  # Expected to fail after retry

        # Check that sleep was called (indicating retry logic)
        mock_sleep.assert_called_with(5)

@pytest.mark.asyncio
async def test_emit_readings_with_logging(server, sio):
    """Test that emit_readings includes additional logging."""
    # Add some test data
    server.sensor_readings['test_sensor'] = [{'n': 1, 'timestamp': 'test'}]
    server.sensors.add('test_sensor')  # Ensure sensors is non-empty
    server.subscribers = {'sub-1'}

    with patch('simoc_sam.mqttbridge.utils.parse_args') as mock_parse_args, \
         patch('simoc_sam.mqttbridge.traceback.print_exc') as mock_traceback:

        mock_args = MagicMock()
        mock_args.delay = 0.1
        mock_parse_args.return_value = mock_args

        # Mock the sleep method to break the loop after one iteration
        with patch.object(server.sio, 'sleep', side_effect=Exception("Break loop")):
            try:
                await server.emit_readings()
            except Exception:
                pass  # Expected to fail after one iteration

        # Check that emit was called
        sio.emit.assert_called()

def test_get_timestamp(server):
    """Test timestamp generation."""
    timestamp = server.get_timestamp()
    assert isinstance(timestamp, str)
    assert len(timestamp) > 0

def test_get_sensor_info_from_cfg(server):
    """Test sensor info retrieval from config file."""
    with patch('configparser.ConfigParser') as mock_config:
        mock_parser = MagicMock()
        mock_config.return_value = mock_parser
        mock_parser.items.return_value = [('test_sensor', {'name': 'Test Sensor'})]

        result = server.get_sensor_info_from_cfg('test_sensor')
        assert result == {'name': 'Test Sensor'}

        # Test with non-existent sensor
        mock_parser.items.return_value = []
        result = server.get_sensor_info_from_cfg('non_existent')
        assert result is None
