from serial import Serial


class USBISS(object):

    def __init__(self, device, mode, freq):
        if 6000000 % freq != 0:
            raise ValueError('Unsupported frequency.')

        divisor = (6000000 // freq) - 1

        self.serial = Serial(device, 57600)

        self.serial.write(bytearray([0x5A, 0x02, mode, divisor]))
        response = self.serial.read(2)

        if response[0] == 0:
            if response[1] == 0x05:
                raise RuntimeError('USB-ISS: Unknown Command')
            elif response[1] == 0x06:
                raise RuntimeError('USB-ISS: Internal Error 1')
            elif response[1] == 0x07:
                raise RuntimeError('USB-ISS: Internal Error 2')
            else:
                raise RuntimeError('USB-ISS: Undocumented Error')

    def close(self):
        self.serial.close()

    def transfer(self, data):
        self.serial.write(bytearray([0x61] + data))
        response = bytearray(self.serial.read(1 + len(data)))

        if response[0] == 0:
            raise RuntimeError('USB-ISS: Transmission Error')

        return response[1:]

    def __exit__(self):
        self.close()
