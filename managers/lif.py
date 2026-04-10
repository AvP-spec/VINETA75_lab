import threading
import time
import numpy as np
import pandas as pd

from pathlib import Path
import os
import sys

data_path = Path(r"C:\Andrei\DATA\test_data")

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from devices.Advanttest_Q8326 import Q8326
from devices.pilot_pz import PilotPZ500
from devices.pilot_pz import PilotPC4000
import utils.scan_utils as su
from utils.terminal_styler import TerminalColours



class LIFManager(TerminalColours):

    def __init__(self):
        self.master_diode = PilotPZ500()
        self.amplifier_diode = PilotPC4000()
        self.wlm = Q8326()
        self.scope = None # not yet implemented
        self._connect_device(self.master_diode, device_type="COM")
        self._connect_device(self.amplifier_diode)
        self._connect_device(self.wlm, device_type="GPIB")


    def _connect_device(self, device, device_type:str="COM"):
        ''' device types: COM, GPIB'''
        if device is None:
            print(f"{self.RED}")
            print(f"LIFManager._connect_device(): device is None ")
            print(f"{self.RESET}")

        print(f"\n LIFManager connecting: "
              f"{self.BLUE}{device.name}{self.RESET}")
        try:
            device.connect()

        except Exception as e:
            print(f"\n{self.RED}[{device.name}] Could not connect: {e}{self.RESET}")

    def disconnect_all(self):
        print(f"\n {self.CYAN}LIFManager disconnect{self.RESET}")
        self.master_diode.disconnect()
        self.amplifier_diode.disconnect()
        self.wlm.disconnect()
        return self
    

    def laser_on(self, silent=False):
        print(f"{self.CYAN} \n" 
              f"LIFManager: Starting lasers in parallel...{self.RESET}")
        # create thread objects
        t1 = threading.Thread(target=self.master_diode.switch_on,
                              kwargs={"silent":silent, "timeout":10})
        t2 = threading.Thread(target=self.amplifier_diode.switch_on,
                              kwargs={"silent":silent, "timeout":10})
        # execute oblects
        t1.start()
        t2.start()
        # wait for completion, block the main until threads finfished
        t1.join()
        t2.join() 
        
        ### version of consequent start
        # self.master_diode.switch_on()
        # self.amplifier_diode.switch_on()
        return self

    def laser_off(self):
        self.master_diode.switch_off()
        self.amplifier_diode.switch_off()
        return self


    def scan_piezo(self, 
                   v_step:float=3, # piezo voltage step 
                   v_max:float=None, # max piezo voltage
                   v_min:float=None, # min piezo voltage
                   v_unit:str="[V]", # piezo voltage units 
                   n_wlm:int=5, # number of wavelength measurements
                   zigzag:bool=True
                    ):
    
        '''
        pizo info: 
        "limits": {"max": 13.5, "min": -13.5, "unit": "[V]", "resolution": 1E-3}
        "unit_map": {"V": 1, "[V]": 1, "mV": 0.001, "[mV]": 0.001},
        '''
        piezo_limits = self.master_diode.piezo['limits']
        piezo_unit_map = self.master_diode.piezo['unit_map']
        
        if not isinstance(n_wlm, int) or n_wlm < 1:
            print(f"{self.RED} Error scan_piezo() from LIFManager: {self.RESET}")
            raise ValueError(f"n_wlm must be a positive integer, got {n_wlm}")
 
        
        ### set input to the base units [V]
        if v_max is None:
            v_max = piezo_limits['max']
        else:
            v_max = v_max * piezo_unit_map[v_unit]

        if v_min is None:
            v_min = piezo_limits['min']
        else:
            v_min = v_min * piezo_unit_map[v_unit] 

        v_step = v_step * piezo_unit_map[v_unit] 
        resolution = piezo_limits['resolution']

        v_list = su.get_scan_list_stepped(
                    min_val=v_min,
                    max_val=v_max,
                    step=v_step,
                    resolution=resolution,
                    margin_pct=0.5,
                    reverse=False,
                    zigzag=zigzag,
                    )

        result = []
        t0 = time.perf_counter()
        i = 0
        for v in v_list:
            i += 1
            print(f"meausurement {i} from {len(v_list)}")
            self.master_diode.set_piezo(value=v, unit="V", silent=True)
            data = [self.wlm.read() for i in range(n_wlm)]
            wls = [key['wavelength'] for key in data]
            times = [key['time_s'] for key in data]
            result.append({
                'time_s': min(times) - t0,
                'duration_s': max(times) - min(times),
                'pieso_V': v,
                'wavelength': sum(wls) / len(wls),
                'wls_err' : (max(wls) - min(wls))/2,
                'wls_std' : np.std(wls) if n_wlm > 2 else 0
            })
            print(f"piezo offset {v} V, wavelength {result[-1]['wavelength']}")
        print(f"{self.GREEN} scan finished {self.RESET}")
        return pd.DataFrame(result)




        

                

        

    
    def drift_monitor(self):
        pass




if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{data_path=}")
    print(f"{current_file=}")
    print(f"{project_root=}")

    r_man = LIFManager()
    r_man.laser_on()
    r_man.laser_off()
    r_man.disconnect_all()