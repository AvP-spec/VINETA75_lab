from base_device import BaseDevice
import pyvisa
import time
import os

class ArduinoAvP(BaseDevice):
    CONNECTION_SETTINGS = {
        'baud_rate': 9600, # 9600, 115200, 57600, 38400, 19200.
        'data_bits': 8,
        'stop_bits': pyvisa.constants.StopBits.one, # variants: one, two
        'parity': pyvisa.constants.Parity.none,     # variants: none, even, odd
        'read_termination': '\n', # Stefan: '\r\n'
        'write_termination': '\n',
        'timeout': 1000 # 1 sec
    }
    def __init__(self):
        super().__init__()
        self.hwid = "VID:PID:SER = 2341:0043:24238313635351910130"
        self.name = self.DEVICE_DIKT[self.hwid]
        # self.port = None


if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    arduino = ArduinoAvP()
    arduino.print_connections()
    #print(f"{arduino.connection=}")
    arduino.get_COM_port().connect()
    print(f"{arduino.connection=}")
    time.sleep(5)
    print("waiting for key input, press x or y then enter:")
    key = input()
    print(key)
    print(f"{arduino.connection=}")
    arduino.connection.write(key)
    print(arduino.connection)
    time.sleep(5)
    arduino.disconnect()
    print(arduino.connection)
