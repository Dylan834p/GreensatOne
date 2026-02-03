from machine import Pin, ADC, I2C # type: ignore
import dht # type: ignore
import time
import struct

class GasSensor:
    def __init__(self, pin_adc):
        self.sensor = ADC(Pin(pin_adc))
        self.baseline = 0

    def calibrate(self):
        """Sets the baseline by averaging 20 readings."""
        total = 0
        for _ in range(20):
            total += self.sensor.read_u16()
            time.sleep(0.1)
        self.baseline = total / 20

    def read(self):
        """Returns raw ADC value and estimated gas percentage."""
        val = self.sensor.read_u16()
        diff = max(0, val - self.baseline)
        # Normalizing to a 0-100 percentage scale based on expected sensitivity
        percentage = min(100.0, (diff / 10000.0) * 100.0)
        return val, round(percentage, 2)

class TempHumSensor:
    def __init__(self, pin_data):
        self.sensor = dht.DHT11(Pin(pin_data))

    def read(self):
        """Returns (temperature, humidity) or (None, None) on failure."""
        try:
            self.sensor.measure()
            return self.sensor.temperature(), self.sensor.humidity()
        except OSError:
            return None, None

class LightSensor:
    def __init__(self, i2c_bus, addr=0x23):
        self.i2c = i2c_bus
        self.addr = addr
        try:
            self.i2c.writeto(self.addr, b'\x01') # Power on
        except OSError:
            pass

    def read(self):
        """Returns light level in Lux."""
        try:
            self.i2c.writeto(self.addr, b'\x10') # H-Resolution mode
            time.sleep(0.2)
            data = self.i2c.readfrom(self.addr, 2)
            lux = ((data[0] << 8) | data[1]) / 1.2
            return round(lux, 1)
        except OSError:
            return -1

class PressureSensor:
    """BMP280 / BME280 pressure sensor driver."""
    def __init__(self, i2c_bus: I2C, addr=0x76):
        self.i2c = i2c_bus
        self.addr = addr
        self.t_fine = 0
        try:
            self.calib = self._read_calibration()
            self.i2c.writeto_mem(self.addr, 0xF4, b'\x27') # Normal mode
            self.i2c.writeto_mem(self.addr, 0xF5, b'\xA0') # Filter/Standby settings
            time.sleep(0.1)
        except OSError:
            raise Exception(f"Sensor not found at I2C address {hex(addr)}")

    def _read_calibration(self):
        data = self.i2c.readfrom_mem(self.addr, 0x88, 24)
        return struct.unpack('<HhhHhhhhhhhh', data)

    def _read_raw(self):
        data = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        return temp_raw, pres_raw

    def _compensate_temp(self, temp_raw):
        t1, t2, t3 = self.calib[0:3]
        v1 = (temp_raw / 16384.0 - t1 / 1024.0) * t2
        v2 = ((temp_raw / 131072.0 - t1 / 8192.0) ** 2) * t3
        self.t_fine = v1 + v2

    def read(self):
        """Returns atmospheric pressure in hPa."""
        try:
            t_raw, p_raw = self._read_raw()
            self._compensate_temp(t_raw)
            
            p_cal = self.calib[3:12]
            v1 = (self.t_fine / 2.0) - 64000.0
            v2 = v1 * v1 * p_cal[5] / 32768.0
            v2 = v2 + (v1 * p_cal[4] * 2.0)
            v2 = (v2 / 4.0) + (p_cal[3] * 65536.0)
            v1 = (p_cal[2] * v1 * v1 / 524288.0 + p_cal[1] * v1) / 524288.0
            v1 = (1.0 + v1 / 32768.0) * p_cal[0]

            if v1 == 0: return -1

            p = 1048576.0 - p_raw
            p = (p - (v2 / 4096.0)) * 6250.0 / v1
            v1 = p_cal[8] * p * p / 2147483648.0
            v2 = p * p_cal[7] / 32768.0
            p = p + (v1 + v2 + p_cal[6]) / 16.0
            return round(p / 100.0, 1)
        except Exception:
            return -1
        
class Alarm:
    def __init__(self, pin_buzzer):
        self.buzzer = Pin(pin_buzzer, Pin.OUT)
        self.buzzer.value(0)

    def beep(self, duration=0.1):
        self.buzzer.value(1)
        time.sleep(duration)
        self.buzzer.value(0)

    def alert(self):
        """Trigger a priority notification pattern."""
        for _ in range(3):
            self.beep(0.1)
            time.sleep(0.1)

class GreenSatLogger:
    def __init__(self):
        self.start_time = time.time()

    def get_uptime(self):
        """Returns system uptime in seconds."""
        return time.time() - self.start_time