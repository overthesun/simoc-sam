"""Driver for the BNO085 9-DOF Orientation IMU sensor."""
import time

from . import utils
from .. import config
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
#   * if no value is returned, config.bno085_default_err_value is used
# * when certain RuntimeErrors happen the reading might stop updating
#   * to solve this the features are re-enabled again
#   * note that soft/hard-resetting doesn't seem to solve this problem

ERR_VALUE = getattr(config, 'bno085_default_err_value', 0)

# map feature names to the corresponding BNO085 attributes
feature_to_attr = {
    'RAW_ACCELEROMETER': 'raw_acceleration',
    'RAW_GYROSCOPE': 'raw_gyro',
    'RAW_MAGNETOMETER': 'raw_magnetic',
    'ACCELEROMETER': 'acceleration',
    'GYROSCOPE': 'gyro',
    'MAGNETOMETER': 'magnetic',
    'GRAVITY': 'gravity',
    'LINEAR_ACCELERATION': 'linear_acceleration',
    'ROTATION_VECTOR': 'quaternion',
    'GAME_ROTATION_VECTOR': 'game_quaternion',
    'GEOMAGNETIC_ROTATION_VECTOR': 'geomagnetic_quaternion',
    'STABILITY_CLASSIFIER': 'stability_classification',
    'ACTIVITY_CLASSIFIER': 'activity_classification',
    'STEP_COUNTER': 'steps',
    'SHAKE_DETECTOR': 'shake',
}

class BNO085(BaseSensor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
        self.bno = BNO08X_I2C(self.i2c)
        self.enable_features()

    def enable_features(self, features=None):
        """Enable all requested features."""
        # some features are currently not enabled
        # uncomment them here and in read_sensor_data below to use them
        if features is None:
            features = getattr(config, 'bno085_enabled_features',
                               ['LINEAR_ACCELERATION'])
        enabled = 0
        print(f'Enabling {len(features)} features...')
        for feature in features:
            enabled += self.enable_feature(feature)
        print(f'{enabled} features enabled')
        # if we can't enable all requested features abort and quit
        assert enabled == len(features)
        self.enabled_features = features

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
            default = ERR_VALUE  # these attrs expect a scalar value (int/str)
        else:
            default = [ERR_VALUE] * 4  # the others have 3/4 values
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
        enabled_features = self.enabled_features
        attrs = {}
        for feature in enabled_features:
            attrs[feature] = self.read_attribute(feature_to_attr[feature])
        reading = {}
        # Raw Acceleration/Gyro/Magnetometer
        if 'RAW_ACCELERATION' in enabled_features:
            v = attrs['RAW_ACCELERATION']
            reading.update(raw_accel_x=v[0], raw_accel_y=v[1], raw_accel_z=v[2])
        if 'RAW_GYROSCOPE' in enabled_features:
            v = attrs['RAW_GYROSCOPE']
            reading.update(raw_gyro_x=v[0], raw_gyro_y=v[1], raw_gyro_z=v[2])
        if 'RAW_MAGNETOMETER' in enabled_features:
            v = attrs['RAW_MAGNETOMETER']
            reading.update(raw_mag_x=v[0], raw_mag_y=v[1], raw_mag_z=v[2])
        # Acceleration (m/s^2), Gyroscope (rad/s), Magnetometer (uT)
        if 'ACCELEROMETER' in enabled_features:
            v = attrs['ACCELEROMETER']
            reading.update(accel_x=v[0], accel_y=v[1], accel_z=v[2])
        if 'GYROSCOPE' in enabled_features:
            v = attrs['GYROSCOPE']
            reading.update(gyro_x=v[0], gyro_y=v[1], gyro_z=v[2])
        if 'MAGNETOMETER' in enabled_features:
            v = attrs['MAGNETOMETER']
            reading.update(mag_x=v[0], mag_y=v[1], mag_z=v[2])
        # Gravity vector (m/s^2), equal to acceleration - linear_acceleration
        if 'GRAVITY' in enabled_features:
            v = attrs['GRAVITY']
            reading.update(gravity_x=v[0], gravity_y=v[1], gravity_z=v[2])
        # Linear acceleration (m/s^2), equal to acceleration - gravity
        if 'LINEAR_ACCELERATION' in enabled_features:
            v = attrs['LINEAR_ACCELERATION']
            reading.update(linear_accel_x=v[0], linear_accel_y=v[1], linear_accel_z=v[2])
        # Rotation / Game Rotation / Geomagnetic Rotation vectors (quaternions)
        if 'ROTATION_VECTOR' in enabled_features:
            v = attrs['ROTATION_VECTOR']
            reading.update(quat_i=v[0], quat_j=v[1],
                           quat_k=v[2], quat_real=v[3])
        if 'GAME_ROTATION_VECTOR' in enabled_features:
            v = attrs['GAME_ROTATION_VECTOR']
            reading.update(game_quat_i=v[0], game_quat_j=v[1],
                           game_quat_k=v[2], game_quat_real=v[3])
        if 'GEOMAGNETIC_ROTATION_VECTOR' in enabled_features:
            v = attrs['GEOMAGNETIC_ROTATION_VECTOR']
            reading.update(geomag_quat_i=v[0], geomag_quat_j=v[1],
                           geomag_quat_k=v[2], geomag_quat_real=v[3])
        # Stability classification (string)
        if 'STABILITY_CLASSIFIER' in enabled_features:
            reading.update(stability=attrs['STABILITY_CLASSIFIER'])
        # Activity classification (string)
        if 'ACTIVITY_CLASSIFIER' in enabled_features:
            reading.update(activity=attrs['ACTIVITY_CLASSIFIER'])
        # Step counter (int)
        if 'STEP_COUNTER' in enabled_features:
            reading.update(steps=attrs['STEP_COUNTER'])
        # Shake detector (bool)
        if 'SHAKE_DETECTOR' in enabled_features:
            reading.update(shake=attrs['SHAKE_DETECTOR'])
        self.print_reading(reading)
        return reading


if __name__ == '__main__':
    utils.start_sensor(BNO085)
