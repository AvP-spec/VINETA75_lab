import serial
import time
import sys
from pathlib import Path
import subprocess
import os

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from utils.terminal_styler import TerminalColours


PORT = 'COM11'  # Replace with your actual COM port
COMMAND = 'ID'  # "*IDN?" 'ID'
CONNECTION_SETTINGS = {
    'baudrate': 9600,
    'bytesize': 8,          # 5, 6, 7, 8
    'parity': 'N',          # 'N' (none), 'E' (even), 'O' (odd), 'M' (mark), 'S' (space)
    'stopbits': 1,          # 1, 1.5, 2
    'timeout': 3.0,         # timeout in seconds (3000 ms = 3.0 s)
}

TERMINATOR = {
    'read_termination': '\r', #  '\r\n' or '\r'
    'write_termination': '\r'   # '\r\n' or '\r'
}


def connect(port: str, settings: dict):
    tc = TerminalColours()
    print("\n connector-serial.py: function connect()")
    print(tc.BLUE + f"Attempting to connect to {port} with settings: {settings}" + tc.RESET)
    try:
        ser = serial.Serial(port=port, **settings)
        print(tc.GREEN + f"Successfully connected to {port}" + tc.RESET)
        return ser
    except Exception as e:
        print(tc.RED + f"Failed to connect to {port}:" + tc.RESET)
        print(f"{e}")
        return None

    
def send_command(ser: serial.Serial, command: str, settings: dict):
    tc = TerminalColours()
    print("\n connector-serial.py: function send_command()")
    try:
        # Clear input buffer to discard stale/leftover data before sending new command
        ser.reset_input_buffer()
        # Append the write termination to the command
        full_command = command + settings['write_termination']
        ser.write(full_command.encode('utf-8'))
        # Ensure data is immediately flushed to the physical port
        ser.flush()
        print(tc.GREEN + f"Command '{command}' sent." + tc.RESET)

        # Give the device time to respond and check the buffer
        time.sleep(0.2)
        bytes_available = ser.in_waiting
        print(f"Bytes waiting in buffer after write: {bytes_available}")

    except Exception as e:
        print(tc.RED + f"Failed to send command '{command}': {e}" + tc.RESET)


def read_response(ser: serial.Serial, settings: dict):
    tc = TerminalColours()
    print("\n connector-serial.py: function read_response()")
    try:
        # Read until specified termination string (works for '\r', '\n', or '\r\n')
        termination = settings.get('read_termination', '\r') #.encode('utf-8')
        raw_response = ser.read_until(expected=termination)
        response = raw_response.decode('utf-8').strip()

        print(tc.GREEN + f"Response received:" + tc.RESET)
        print(f"{response=}")
        return response
    
    except Exception as e:
        print(tc.RED + f"Failed to read response: {e}" + tc.RESET)
        return None
    
    
if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

    # Connect to the serial port
    ser = connect(PORT, CONNECTION_SETTINGS)

    if ser is not None:
        try:
            # Send the command
            send_command(ser, COMMAND, TERMINATOR)
            
            # Read the response
            response = read_response(ser, TERMINATOR)
            
            if response:
                print(f"{response}")
            else:
                print("No response received.")
                
        finally:
            ## Attempt to set the device to local mode before closing
            ## Does not work so far, but leaving it here for future attempts
            send_command(ser, "REMOTE 0", TERMINATOR)  
            ser.dtr = False  # Отключаем Data Terminal Ready
            ser.rts = False  # Отключаем Request to Send
            time.sleep(0.5)  # Give the device a moment to process the command

            ser.close()
            print("Serial connection closed.")
    else:
            sys.exit(1)





