import traceback

from .baseserver import BaseServer
from .sensors import utils


class SocketIOServer(BaseServer):
    """SocketIO server for sensor data"""

    def setup_sio_events(self):
        """Set up SocketIO event handlers with sensor manager support."""
        super().setup_sio_events()

        # Override disconnect to handle sensors and sensor managers
        @self.sio.event
        def disconnect(sid):
            print('DISCONNECTED:', sid)
            if sid in self.subscribers:
                print('Removing disconnected client:', sid)
                self.subscribers.remove(sid)
            # remove the sid from the other groups if present
            self.clients.discard(sid)
            if sid in self.sensors:
                print('Removing disconnected sensor:', sid)
                self.sensors.remove(sid)
                del self.sensor_info[sid]
                del self.sensor_readings[sid]
            if sid in self.sensor_managers:
                print('Removing disconnected sensor manager:', sid)
                self.sensor_managers.remove(sid)

        @self.sio.on('register-sensor')
        async def register_sensor(sid, sensor_info):
            """Handle new sensors and request sensor data."""
            print('New sensor connected:', sid)
            # TODO: Index by sensor_id rather than sid (socketio address) so that
            # we can save and re-use the info, despite updated sid.
            self.sensors.add(sid)
            # Load sensor metadata from config file
            sensor_id = sensor_info.get('sensor_id')
            if sensor_id:
                sensor_meta = self.get_sensor_info_from_cfg(sensor_id)
                if sensor_meta:
                    for attr in ['name', 'desc']:
                        if attr in sensor_meta and not sensor_info[f'sensor_{attr}']:
                            sensor_info[f'sensor_{attr}'] = sensor_meta[attr]
            print('Sensor info:', sensor_info)
            self.sensor_info[sid] = sensor_info
            await self.emit_to_subscribers('sensor-info', self.sensor_info)
            # sensor is added once we set up a room
            print('Requesting sensor data from', sid)
            # request data from the sensor
            await self.sio.emit('send-data', to=sid)

        @self.sio.on('sensor-batch')
        async def sensor_batch(sid, batch):
            """Get a batch of readings and add it to SENSOR_READINGS."""
            #print(f'Received a batch of {len(batch)} readings from sensor {sid}:')
            self.sensor_readings[sid].extend(batch)
            # sensor_info = self.sensor_info[sid]
            #for reading in batch:
                #print(utils.format_reading(reading, sensor_info=sensor_info))

        @self.sio.on('sensor-reading')
        async def sensor_reading(sid, reading):
            """Get a single sensor reading and add it to SENSOR_READINGS."""
            #print(f'Received a reading from sensor {sid}:')
            self.sensor_readings[sid].append(reading)
            # sensor_info = self.sensor_info[sid]
            #print(utils.format_reading(reading, sensor_info=sensor_info))

        @self.sio.on('refresh-sensors')
        async def refresh_sensors(sid, sensor_manager_id=None):
            """Forward the refresh-sensor call to one or all sensor managers"""
            print('Refreshing sensors (from server)')
            for sm_id in self.sensor_managers:
                if sensor_manager_id is None or sm_id == sensor_manager_id:
                    await self.sio.emit('refresh-sensors', to=sm_id)


if __name__ == '__main__':
    server = SocketIOServer(port=8081)
    server.run()
