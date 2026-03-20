from pathlib import Path
import os
import sys

data_path = Path(r"C:\Andrei\DATA\test_data")
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from devices.Advanttest_Q8326 import Q8326
from devices.pilot_pz import PilotPZ500



class LIFManager():
    RED = "\033[31m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    def __init__(self):
        self.master_diode = PilotPZ500()
        self.amplifier_diode = None # not yet implemented
        self.wlm = Q8326()
        self.scope = None # not yet implemented
        self._connect_device(self.master_diode, device_type="COM")
        self._connect_device(self.wlm, device_type="GPIB")


    def _connect_device(self, device, device_type:str):
        ''' device types: COM, GPIB'''
        if device is None:
            print(f"{self.RED}")
            print(f"LIFManager._connect_device(): device is None ")
            print(f"{self.RESET}")

        print(f"\n LIFManager connecting: "
              f"{self.BLUE}{device.name}{self.RESET}")
        try:
            if device_type == "COM":
                device.get_COM_port().connect()
            elif device_type == "GPIB":
                device.connect()
            else: 
                print(f"{self.MAGENTA} Unkown device type {self.RESET}")
        except Exception as e:
            print(f"\n{self.RED}[{device.name}] Could not connect: {e}{self.RESET}")

    def disconnect_all(self):
        print(f"\n {self.CYAN}LIFManager disconnect{self.RESET}")
        self.master_diode.disconnect()
        self.wlm.disconnect()
        return self
    
    def drift_monitor(self):
        pass




if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{data_path=}")
    print(f"{current_file=}")
    print(f"{project_root=}")

    r_man = LIFManager()
    r_man.disconnect_all()