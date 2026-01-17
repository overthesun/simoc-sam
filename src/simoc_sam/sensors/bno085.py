"""Driver for the BNO085 9-DOF Orientation IMU sensor."""
import time

from . import utils
from .basesensor import BaseSensor

board = utils.import_board()
busio = utils.import_busio()
import adafruit_bno08x
from adafruit_bno08x.i2c import BNO08X_I2C


# Note: this sensor seem to have several issues and often receives
# invalid packets and/or gets stuck.
# Multiple measures have been taken to avoid this:
# * while enabling features, 10 attempts will be made for each feature
#   * if a feature can't be enabled, the process will be terminated
#     (and restarted by systemd)
# * while reading values, 5 attempts will be made
#   * if no value is returned, 'EEE' is used instead
# * when certain RuntimeErrors happen the reading might stop updating
#   * to solve this the features are re-enabled again
#   * note that soft/hard-resetting doesn't seem to solve this problem


class BNO085(BaseSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
        self.bno = bno = BNO08X_I2C(self.i2c)
        self.enable_features()

    def enable_features(self, features=None):
        """Enable all requested features."""
        # some features are currently not enabled
        # uncomment them here and in read_sensor_data below to use them
        if features is None:
            features = [
                # 'RAW_ACCELEROMETER', 'RAW_GYROSCOPE', 'RAW_MAGNETOMETER',
                # 'ACCELEROMETER', 'GYROSCOPE', 'MAGNETOMETER',
                # 'GRAVITY',
                'LINEAR_ACCELERATION',
                # 'ROTATION_VECTOR', 'GAME_ROTATION_VECTOR',
                # 'GEOMAGNETIC_ROTATION_VECTOR',
                # 'STABILITY_CLASSIFIER', 'ACTIVITY_CLASSIFIER',
                # 'STEP_COUNTER', 'SHAKE_DETECTOR'
            ]
        enabled = 0
        print(f'Enabling {len(features)} features...')
        for feature in features:
            enabled += self.enable_feature(feature)
        print(f'{enabled} features enabled')
        # if we can't enable all requested features abort and quit
        assert enabled == len(features)

    def enable_feature(self, feature_name):
        """Enable a single feature (retrying in case of failure)."""
        feature = getattr(adafruit_bno08x, f'BNO_REPORT_{feature_name}')
        print(f'  Enabling {feature_name}...', end=' ')
        for attempt in range(10):
            try:
                self.bno.enable_feature(feature)
                print('done')
                return 1
            except Exception as err:
                print(f'\n  failed to enable {feature_name!r} (attempt {attempt}): '
                      f'{err.__class__.__name__}: {err}')
                time.sleep(1)  # sleep a bit and try again
        print(f'\n  failed to enable {feature_name} after {attempt} attempts.')
        return 0

    def read_attribute(self, attr_name):
        """Try to read an attribute (retrying in case of failure)."""
        # define placeholder value used when the attributes can't be read
        if attr_name in {'activity_classification', 'stability_classification',
                         'steps', 'shake'}:
            default = 0  # these attrs expect a scalar value (int/str)
        else:
            default = [0, 0, 0, 0]  # the others have 3/4 values
        for attempt in range(5):
            try:
                return getattr(self.bno, attr_name, default)
            except RuntimeError as err:
                print(f'RuntimeError while reading {attr_name!r}: {err}')
                if err.args == ('Unprocessable Batch bytes', 1):
                    # when this happens the readings stop updating
                    # re-enabling features seems to solve the issue
                    # soft/hard resetting doesn't seem to work
                    print('Re-enabling features...')
                    self.enable_features()
            except Exception as err:
                print(f'Error while reading {attr_name!r}: {err.__class__.__name__}: {err}')
        return default

    def read_sensor_data(self):
        # Raw Acceleration/Gyro/Magnetometer
        #raw_accel = self.read_attribute('raw_acceleration')
        #raw_gyro = self.read_attribute('raw_gyro')
        #raw_mag = self.read_attribute('raw_magnetic')
        # Acceleration (m/s^2), Gyroscope (rad/s), Magnetometer (uT)
        #accel = self.read_attribute('acceleration')
        #gyro = self.read_attribute('gyro')
        #mag = self.read_attribute('magnetic')
        # Gravity vector (m/s^2), equal to acceleration - linear_acceleration
        # gravity = self.read_attribute('gravity
        # Linear acceleration (m/s^2), equal to acceleration - gravity
        linear_accel = self.read_attribute('linear_acceleration')
        # Rotation vector (quaternion)
        #quat = self.read_attribute('quaternion')
        # Game Rotation Vector (quaternion)
        #game_quat = self.read_attribute('game_quaternion')
        # Geomagnetic Rotation Vector (quaternion)
        # geomag_quat = self.read_attribute('geomagnetic_quaternion')
        # Activity classification (string)
        # activity = self.read_attribute('activity_classification')
        # Stability classification (string)
        # stability = self.read_attribute('stability_classification')
        # Step counter (int)
        # steps = self.read_attribute('steps')
        # Shake detector (bool)
        # shake = self.read_attribute('shake')
        reading = dict(
            # raw acceleration/gyro/magnetomer
            #raw_accel_x=raw_accel[0], raw_accel_y=raw_accel[1], raw_accel_z=raw_accel[2],
            #raw_gyro_x=raw_gyro[0], raw_gyro_y=raw_gyro[1], raw_gyro_z=raw_gyro[2],
            #raw_mag_x=raw_mag[0], raw_mag_y=raw_mag[1], raw_mag_z=raw_mag[2],
            # acceleration/gyro/magnetomer
            #accel_x=accel[0], accel_y=accel[1], accel_z=accel[2],
            #gyro_x=gyro[0], gyro_y=gyro[1], gyro_z=gyro[2],
            #mag_x=mag[0], mag_y=mag[1], mag_z=mag[2],
            # gravity and linear acceleration
            # gravity_x=gravity[0], gravity_y=gravity[1], gravity_z=gravity[2],
            linear_accel_x=linear_accel[0],
            linear_accel_y=linear_accel[1],
            linear_accel_z=linear_accel[2],
            # quaternions (rotation/game/geomagnetic)
            #quat_i=quat[0],
            #quat_j=quat[1],
            #quat_k=quat[2],
            #quat_real=quat[3],
            #game_quat_i=game_quat[0],
            #game_quat_j=game_quat[1],
            #game_quat_k=game_quat[2],
            #game_quat_real=game_quat[3],
            # geomag_quat_i=geomag_quat[0],
            # geomag_quat_j=geomag_quat[1],
            # geomag_quat_k=geomag_quat[2],
            # geomag_quat_real=geomag_quat[3],
            # activity/stability/steps/shake
            # activity=activity,
            # stability=stability,
            # steps=steps,
            # shake=shake,
        )
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(BNO085)
