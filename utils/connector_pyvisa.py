import os
from pathlib import Path
import sys
import subprocess
import time
import pyvisa

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from utils.terminal_styler import TerminalColours


PORT = 'COM9'  # Replace with your actual COM port
COMMAND = "*IDN?"  # "*IDN?" , 'ID'

CONNECTION_SETTINGS = {
        'baud_rate': 9600,
        'data_bits': 8,
        'stop_bits': pyvisa.constants.StopBits.one, # variants: one, two
        'parity': pyvisa.constants.Parity.none,     # variants: none, even, odd
        'read_termination': '\r\n', # Stefan: '\r\n', manual: '\r'
        'write_termination': '\r', # '\r'
        'timeout': 3000 # 1 sec
    }

def _com_to_pyvisa_port(com_port):
    """
    Convert a COM port string (e.g., 'COM3') to a PyVISA-compatible resource string.
    """
    if com_port.upper().startswith('COM'):
        port_number = com_port[3:]  # Extract the number after 'COM'
        return f'ASRL{port_number}::INSTR'
    else:
        raise ValueError(f"Invalid COM port format: {com_port}")


def connect(port, settings):
    tc = TerminalColours()
    print("\n connector-pyvisa.py: function connect()")
    print(tc.BLUE + f"Attempting to connect to {port} with settings: {settings}" + tc.RESET)
    try:
        rm = pyvisa.ResourceManager()
        resource_string = _com_to_pyvisa_port(port)   
        instrument = rm.open_resource(resource_string, **settings)
        print(tc.GREEN + f"Successfully connected to {port}" + tc.RESET)
        return instrument
    except Exception as e:
        print(tc.RED + f"Failed to connect to {port}:" + tc.RESET)
        print(f"{e}")
        return None


def read_value(instrument, command):
    tc = TerminalColours()
    print("\n connector-pyvisa.py: function read_value()")
    try:
        response = instrument.query(command)
        print(tc.GREEN + f"Response received:" + tc.RESET)
        print(f"{response=}")
        return response
    except Exception as e:
        print(tc.RED + f"Failed to read value for command '{command}': {e}" + tc.RESET)
        return None  


if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
    device = connect(PORT, CONNECTION_SETTINGS)
    if device is not None:
        x = read_value(device, COMMAND)
        print(f"{x}")
        device.close()