class gdx_lite:

    def __init__(self, device):
        self.device = device

    def select_sensors(self, sensors=[]):
        self.enabled_sensors = sensors
        self.device.enable_sensors(self.enabled_sensors)

    def start(self, period=1000):
        self.device.start(period=period)

    def read(self):
        retvalues = []
        if self.device.read():
            for i, sensor in self.device.sensors.items():
                retvalues.append(sensor.values[-1])
        return retvalues

    def close(self):
        self.device.close()
