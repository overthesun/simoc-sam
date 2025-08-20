from simoc_sam import config

def test_vars_defined():
    vars = [
        'mqtt_host', 'mqtt_port', 'sio_host', 'sio_port', 'simoc_web_port',
        'mqtt_topic_location', 'log_dir', 'simoc_web_dist_dir', 'sensor_read_delay',
        'mqtt_reconnect_delay', 'verbose_sensor', 'verbose_mqtt',
        'enable_jsonl_logging', 'humans', 'volume',
    ]
    for var in vars:
        assert hasattr(config, var)

