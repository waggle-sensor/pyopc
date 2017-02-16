#!/usr/bin/env python3
'''
Alphasense reader using the USB-ISS interface. The only real dependency
is on the set_spi_mode and transfer_data functions. This could easily be
replaced with some other layer.

Example:

Suppose that the Alphasense is device /dev/ttyACM0. You can simply run:

python alphasense.py /dev/ttyACM0

USB-ISS Reference:
https://www.robot-electronics.co.uk/htm/usb_iss_tech.htm

Alphasense Reference:
waggle-sensor/waggle/docs/alphasense-opc-n2/
'''
from .usbiss import USBISS
from time import sleep
import struct
import sys
from contextlib import closing
import re
from pprint import pprint


def decode17(data):
    bincounts = struct.unpack_from('<16H', data, offset=0)
    mtof = [x / 3 for x in struct.unpack_from('<4B', data, offset=32)]
    sample_flow_rate = struct.unpack_from('<f', data, offset=36)[0]
    pressure = struct.unpack_from('<I', data, offset=40)[0]
    temperature = pressure / 10.0
    sampling_period = struct.unpack_from('<f', data, offset=44)[0]
    checksum = struct.unpack_from('<H', data, offset=48)[0]
    pmvalues = struct.unpack_from('<3f', data, offset=50)

    assert pmvalues[0] <= pmvalues[1] <= pmvalues[2]

    values = {
        'bins': bincounts,
        'mtof': mtof,
        'sample flow rate': sample_flow_rate,
        'sampling period': sampling_period,
        'pm1': pmvalues[0],
        'pm2.5': pmvalues[1],
        'pm10': pmvalues[2],
        'error': sum(bincounts) & 0xFFFF != checksum,
    }

    if temperature > 200:
        values['pressure'] = pressure
    else:
        values['temperature'] = temperature

    return values


def decode18(data):
    return decode17(data)


def decode16(data):
    return decode17(data)


def unpack_structs(structs, data):
    results = {}

    offset = 0

    for key, fmt in structs:
        values = struct.unpack_from(fmt, data, offset)
        if len(values) == 1:
            results[key] = values[0]
        else:
            results[key] = values
        offset += struct.calcsize(fmt)

    return results


class Alphasense(object):

    bin_units = {
        'bins': 'particle / second',
        'mtof': 'second',
        'sample flow rate': 'sample / second',
        'pm1': 'microgram / meter^3',
        'pm2.5': 'microgram / meter^3',
        'pm10': 'microgram / meter^3',
        'temperature': 'celcius',
        'pressure': 'pascal',
    }

    histogram_data_struct = [
        ('bins', '<16H'),
        ('mtof', '<4B'),
        ('sample flow rate', '<f'),
        ('weather', '<f'),
        ('sampling period', '<f'),
        ('checksum', '<H'),
        ('pm1', '<f'),
        ('pm2.5', '<f'),
        ('pm10', '<f'),
    ]

    config_data_structs = [
        ('bin boundaries', '<16H'),
        ('bin particle volume', '<16f'),
        ('bin particle density', '<16f'),
        ('bin particle weighting', '<16f'),
        ('gain scaling coefficient', '<f'),
        ('sample flow rate', '<f'),
        ('laser dac', '<B'),
        ('fan dac', '<B'),
        ('tof to sfr factor', '<B'),
    ]

    def __init__(self, device):
        self.spi = USBISS(device, mode=0x92, freq=500000)

        self.firmware = self.get_firmware_version().decode()
        self.config = self.get_config_data()

        if re.search('OPC-N2 FirmwareVer=OPC.*16.*BD', self.firmware):
            self.decoder = decode16
        elif re.search('OPC-N2 FirmwareVer=OPC.*17.*BD', self.firmware):
            self.decoder = decode17
        elif re.search('OPC-N2 FirmwareVer=OPC.*18.*BD', self.firmware):
            self.decoder = decode18
        else:
            raise RuntimeError('Invalid Alphasense firmware version.')

    def close(self):
        self.spi.close()

    def transfer(self, data, delay=0.001):
        result = bytearray(len(data))

        for i, x in enumerate(data):
            iss_result = self.spi.transfer([x])
            if iss_result[0] != 0xFF:
                raise RuntimeError('Alphasense Read Error')
            result[i] = iss_result[1]
            sleep(delay)

        return result

    def power_on(self, fan=True, laser=True):
        self.transfer([0x03], delay=0.01)

        if fan and laser:
            self.transfer([0x00], delay=0.001)
        elif fan:
            self.transfer([0x04], delay=0.001)
        elif laser:
            self.transfer([0x02], delay=0.001)

    def power_off(self, fan=True, laser=True):
        self.transfer([0x03], delay=0.01)

        if fan and laser:
            self.transfer([0x01], delay=0.001)
        elif fan:
            self.transfer([0x05], delay=0.001)
        elif laser:
            self.transfer([0x03], delay=0.001)

    def set_laser_power(self, power):
        self.transfer([0x42, 0x01, power])

    def set_fan_power(self, power):
        self.transfer([0x42, 0x00, power])

    def get_firmware_version(self):
        self.transfer([0x3F], delay=0.01)
        return self.transfer([0] * 60, delay=0.001)

    def get_config_data_raw(self):
        self.transfer([0x3C], delay=0.01)
        return self.transfer([0] * 256, delay=0.001)

    def get_config_data(self):
        config_data = self.get_config_data_raw()
        return unpack_structs(self.config_data_structs, config_data)

    def ready(self):
        return self.transfer([0xCF])[0] == 0xF3

    def get_histogram_raw(self):
        self.transfer([0x30], delay=0.01)
        return self.transfer([0] * 62, delay=0.001)

    def get_histogram(self):
        return self.decoder(self.get_histogram_raw())

    def get_pm(self):
        self.transfer([0x32], delay=0.01)
        data = self.transfer([0] * 12, delay=0.001)
        return struct.unpack('<3f', data)


OPCN2 = Alphasense

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(('Usage: {} device-name'.format(sys.argv[0])))
        sys.exit(1)

    with closing(Alphasense(sys.argv[1])) as alphasense:
        alphasense.power_on()

        pprint(alphasense.config)

        while True:
            # allows samples to collect for 10 seconds before reading.
            sleep(10)

            rawdata = alphasense.get_histogram_raw()
            data = decode17(rawdata)

            if data['error']:
                raise RuntimeError('Alphasense histogram error.')

            print('--- bins')

            for size, value in zip(alphasense.config['bin particle volume'], data['bins']):
                print(size, value)

            print()

            print('--- data')
            pprint(data)
            print()
