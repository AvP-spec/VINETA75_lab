from base_device import BaseDevice
from pilot_pz import PilotPZ
import time
import types
import pyvisa


CONNECTION_SETTINGS = {
        'baud_rate': 9600,
        'data_bits': 8,
        'stop_bits': pyvisa.constants.StopBits.one, # variants: one, two
        'parity': pyvisa.constants.Parity.none,     # variants: none, even, odd
        'read_termination': '\r\n', # Stefan: '\r\n', manual: '\r'
        'write_termination': '\r', # '\r'
        'timeout': 3000 # 1 sec
    }



if __name__ == "__main__":
    print('hallo')
    device = BaseDevice()
    device.print_connections()
    device.CONNECTION_SETTINGS = CONNECTION_SETTINGS
    print(device.CONNECTION_SETTINGS)
    device.time_sleep = 0.01
    device.name = "test_device"
    device.port = device._com_to_visa("COM4")
    print(f"{device.port=}")
    device.connect()

 #   device.send_command = types.MethodType(PilotPZ.send_command, device)
 #   device.flush_buffer = types.MethodType(PilotPZ.flush_buffer, device)
    #device.after_connect = types.MethodType(PilotPZ.after_connect, device)
 #   device.read_value = types.MethodType(PilotPZ.read_value, device)
    
    # device.print_com_info()
    
    
    
#    print("flush_buffer()")
 #   device.flush_buffer(silent=False)
 #   IDN = device.read_value("*IDN?")
 #   print(f"{IDN=}")

    # try:
    #     device.send_command("*IDN?")
    # except Exception as e:
    #     print(f"{device.RED}IDN query failed:{device.RESET}")

    x = device.connection.query("*IDN?")
    # time.sleep(0.01)
    print(f"{x}")
    device.disconnect()