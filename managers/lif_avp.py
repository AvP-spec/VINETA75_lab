import threading
import time
import pandas as pd
import matplotlib.pyplot as plt
from PyQt6 import QtCore

from pathlib import Path
import os
import sys
import subprocess

#data_path = Path(r"C:\Andrei\DATA\test_data")

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from devices.Advanttest_Q8326 import Q8326
from devices.pilot_pz import PilotPZ500
from devices.pilot_pz import PilotPC4000
from devices.Perkin_Elmer_DS7780 import LockInAmplifier
import utils.scan_utils as su
from utils.plt_styler_avp import PlotStyler
from utils.terminal_styler import TerminalColours



class LIFManager(TerminalColours):

    def __init__(self, silent=True):
        self.master_diode = PilotPZ500()
        self.amplifier_diode = PilotPC4000()
        self.wlm = Q8326()
        self.sleep_time = 0.1 # time to wait after piezo set
        self.lia = LockInAmplifier()  
        
        self._connect_device(self.master_diode, silent=silent)
        self._connect_device(self.amplifier_diode, silent=silent)
        self._connect_device(self.wlm, silent=silent)
        self._connect_device(self.lia, silent=silent)
        

    def _connect_device(self, device, silent=True):
        ''' device types: COM, GPIB'''
        if device is None:
            print(f"{self.RED}")
            print(f"LIFManager._connect_device(): device is None ")
            print(f"{self.RESET}")

        print(f"\n LIFManager connecting: "
              f"{self.BLUE}{device.name}{self.RESET}")
        try:
            device.connect(silent=silent)

        except Exception as e:
            print(f"\n{self.RED}[{device.name}] Could not connect: {e}{self.RESET}")

    def disconnect_all(self):
        print(f"\n {self.CYAN}LIFManager disconnect{self.RESET}")
        self.master_diode.disconnect()
        self.amplifier_diode.disconnect()
        self.wlm.disconnect()
        self.lia.disconnect()
        return self
    

    def laser_on(self, silent=True):
        ### version to start parallel should be avioded:
        ### switchig on amplifier diode without master diode can damage the laser
        # print(f"{self.CYAN} \n" 
        #       f"LIFManager: Starting lasers in parallel...{self.RESET}")
        # # create thread objects
        # t1 = threading.Thread(target=self.master_diode.switch_on,
        #                       kwargs={"silent":silent, "timeout":10})
        # t2 = threading.Thread(target=self.amplifier_diode.switch_on,
        #                       kwargs={"silent":silent, "timeout":10})
        # # execute oblects
        # t1.start()
        # t2.start()
        # # wait for completion, block the main until threads finfished
        # t1.join()
        # t2.join() 
        
        ### version to start Starting lasers sequentially
        print(f"{self.CYAN} \n" 
              f"lif_avp: Starting lasers sequentially{self.RESET}")
        try:
            self.master_diode.switch_on(silent=silent)
            self.amplifier_diode.switch_on(silent=silent)
        except TimeoutError as e:
            print(f"Safety shutdown: {e}")
            self.laser_off(silent=silent)
        return self

    def laser_off(self, silent=False):
        ### the amplifier diode should not operate without master
        print(f"{self.CYAN} \n lif_avp: shutting down lasers{self.RESET}")
        self.amplifier_diode.switch_off()
        self.master_diode.switch_off()
        return self


    @staticmethod
    def _label_keys(dct:dict, label:str):
        '''
        Adds label to all keys in the dictionary.
        '''
        return {f"{label}_{k}": v for k, v in dct.items()}

    def read_state(self, 
                   silent=True, # only for wlm
                   device_read_time=False, # extra time-stemps
                   ):
        '''
        Read laser drivers and wavemeter in parallel.
        '''
        start_time = time.perf_counter()

        ### container to form the oreder of the output
        ### [wlm, master, amplif]
        task_results = [None, None, None]

        # data = {}  
        def worker(index, label, method, kwargs):
            try:
                readout = method(**kwargs)
                labeled = self._label_keys(readout, label)
                task_results[index] = labeled
                # data.update(labeled)
            except Exception as e:
                task_results[index] = {f"{label}_error": str(e)}
                # data[f"{label}_error"] = str(e)

        tasks = [
             (0, 'wlm', self.wlm.read, 
             {'silent': silent, 
              'device_read_time': device_read_time}),

             (1, 'master', self.master_diode.read_laser, 
             {'device_read_time': device_read_time}),

             (2, 'amplif', self.amplifier_diode.read_laser, 
             {'device_read_time': device_read_time})
        ]

        threads = []
        for index, label, method, kwargs in tasks:
            t = threading.Thread(target=worker, args=(index, label, method, kwargs))
            threads.append(t)

        ### start thresds
        for t in threads: t.start()
        ### wait for completion
        for t in threads: t.join()

        results = {
            "start_time": start_time,
            'duration_s': time.perf_counter() - start_time,
        }

        for data in task_results:
            if data:
                results.update(data)

        return results


    def scan_piezo(self,
                   v_list:list=None, # piezo voltage list in Volts
                   silent=True, 
                   life_plot=False, # if True, plot the scan in real time
                   ):
        """
        "limits": {"max": 13.5, "min": -13.5, "unit": "[V]", "resolution": 1E-3}
        """
        piezo_limits = self.master_diode.piezo['limits']

        if v_list is None:
            print(f"{self.RED} Error scan_piezo() from lif_avp.py: {self.RESET}")
            raise ValueError("v_list cannot be None")

        initial_backend = plt.get_backend()
        # print(f" {self.CYAN} {initial_backend=}{self.RESET}")
        ## requared backend 'QtAgg'
        ## defolt backend for Jupiter Notebook 'module://matplotlib_inline.backend_inline'

        ## try encloser for the safe backend change  
        try:
            if life_plot:
                # print("life_plot = True")
                plt.switch_backend('QtAgg')
                plotter = PiezoScanLifePlotter(v_list)

            # print("start scan")
            scan_data = {}
            i = 0
            for v in v_list:
                data = {}
                if v < piezo_limits['min'] or v > piezo_limits['max']:
                    print(f"{self.RED} Error scan_piezo() from lif_avp.py: {self.RESET}")
                    print(f"Voltage {v} is out of piezo limits "
                            f"[{piezo_limits['min']}, {piezo_limits['max']}]")
                    print("value is skipped")
                    continue
    
                self.master_diode.set_piezo(value=v, unit="V", silent=silent)
                time.sleep(self.sleep_time)
                data["piezo_v"] = self.master_diode.read_piezo(silent=silent)
                start_time = time.perf_counter()
                wavelength = self.wlm.read(
                                            device_read_time=False,
                                            slow=False,
                                            silent=silent
                                            )
                lockin = self.lia.read_signal(silent=silent, 
                                                device_read_time=False, 
                                                mode="magphase" # "xy"
                                                )
                duration = time.perf_counter() - start_time
                data["start_time_s"] = start_time
                data["read_duration_s"] = duration
                data.update(wavelength)
                data.update(lockin)
                print(data)
                scan_data[i] = data
                i += 1
                if life_plot:
                    plotter.update_lines(data)

            if life_plot:
                plotter.final_message()

            df = pd.DataFrame.from_dict(scan_data, orient='index')
            laser_state = self.read_state(silent=silent)

            result = {
                        "laser_state": laser_state,
                        "scan_data": df
                    }

        except:
            print(f"{self.RED} Error in LIFManager.scan_piezo(){self.RESET}")

        finally:
            plt.switch_backend(initial_backend)

        return result



class PiezoScanLifePlotter(PlotStyler):

    def __init__(self, v_list):
        # print("plotter init")
        self.x_data = []
        self.lockin_data = []
        self.wlm_data = []
        self.wlm_units = None

        plt.ion()
        self.fig, (self.ax_lockin, self.ax_wlm) = plt.subplots(
                        nrows=2, ncols=1, 
                        sharex=True, # common x
                        figsize=(10, 6),
                        gridspec_kw={'height_ratios': [2, 1]}
                        )

        self._set_window_on_top()
        # print("plt.ion")
        plt.subplots_adjust(hspace=0) # space between sublopts

        self._setup_axes(v_list)

        self.line_lockin, = self.ax_lockin.plot([], [], 'o', label='Magnitude (V)')
        self.line_wlm, = self.ax_wlm.plot([], [], 'o') #, label=f'Wavelength [{self.wlm.units}]'
        # print("plotter initialized")

    def _set_window_on_top(self, block=False):
        if self.fig.canvas.manager is None:
            print("if condition finished LIFManager._set_window_on_top()")
            return 
        
        try:
            window = self.fig.canvas.manager.window
            top_hint = QtCore.Qt.WindowType.WindowStaysOnTopHint
            current_flags = window.windowFlags()
            window.setWindowFlags(current_flags | top_hint)
            window.show()
            if not block:
                window.setWindowFlags(current_flags & ~top_hint)
                window.show()
        except Exception as e:
            print(f"Warning: Could not set window to top: {e}")


    
    def _setup_axes(self, v_list):
        # print("setting axes")
        ## Set fixed X-axis limits
        v_min, v_max = min(v_list), max(v_list)
        v_range = v_max - v_min
        margin = v_range * 0.03 if v_range != 0 else 0.5
        self.ax_lockin.set_xlim(v_min - margin, v_max + margin)
        ## Option A:
        plt.setp(self.ax_lockin.get_xticklabels(), visible=False)
        self.ax_wlm.set_xlabel('Piezo Voltage [V]')

        ## --- SET lock-in plot ---
        ## Add horizontal line at zero
        self.ax_lockin.axhline(0, color='gray', linestyle='--', linewidth=2, alpha=0.7)
        self.ax_lockin.set_ylabel('Lock-in Signal (%)')
        self.ax_lockin.grid(True, alpha=0.3)
        # ax.legend()

        ## --- SET wlm plot ---
        ## self.wlm_units determined in self.update_lines(), and the lable is set
        ## self.ax_wlm.set_ylabel(f'Wavelength [{self.wlm_units}]') 
        self.ax_wlm.grid(True, alpha=0.3)
        # ax.legend()
        
        ## using PlotSyler method
        self.set_scale_steps(self.ax_lockin)
        self.set_scale_steps(self.ax_wlm)
        # print("axes ready")

        return self


    def update_lines(self, data:dict):
        self.x_data.append(float(data["piezo_v"]))
        self.lockin_data.append(float(data["Magnitude_V"]))
        if self.wlm_units is None:
            allowed_units = {"nm", "THz"}
            found_units = allowed_units.intersection(data)
            if not found_units:
                raise KeyError(f"Wavelength units not found in data." 
                               f"Expected one of: {allowed_units}")
            self.wlm_units = next(iter(found_units))
            self.ax_wlm.set_ylabel(f'Wavelength [{self.wlm_units}]')
        self.wlm_data.append(float(data[self.wlm_units]))

        self.line_lockin.set_data(self.x_data, self.lockin_data)
        self.ax_lockin.relim()
        self.ax_lockin.autoscale_view(scalex=False, scaley=True)
        
        self.line_wlm.set_data(self.x_data, self.wlm_data)
        self.ax_wlm.relim()
        self.ax_wlm.autoscale_view(scalex=False, scaley=True)
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        return self


    def final_message(self):
        print("scan finished in the new function")
        def press_to_close(event):
            if event.key in ['q', 'escape', 'enter', 'return', 'space', ' ']:
                plt.close(self.fig)
        self.fig.canvas.mpl_connect('key_press_event', press_to_close)

        self.ax_lockin.text(
                    0.5, 0.5, 
                    'Measurement complete. Press a key to exit...', 
                    color='red', 
                    fontsize=14, 
                    fontweight='bold', 
                    ha='center', 
                    va='center', 
                    transform=self.ax_lockin.transAxes, # Use relative coordinates (0 to 1)
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='red', boxstyle='round,pad=0.5') # Optional: add a background box for readability
                )
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        
        self._set_window_on_top()
        plt.ioff()
        plt.show(block=True)


class LIFPlotter(PlotStyler):
    pass

    

if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
    # print(f"{data_path=}")
    # print(f"{current_file=}")
    # print(f"{project_root=}")

    def test_label_keys():
        dct = {
            "current_A": 1.25,
            "temperature_C": 24.5,
            "status": "ON",
            "interlock": True
            }
        labeled_dct = LIFManager._label_keys(dct=dct, label="master")
        print(f"original dict= {dct}")
        print(f"new dict = {labeled_dct}")

   # test_label_keys()


    rm = LIFManager()

    # readout = rm.read_state()
    # print(readout)
    voltage_list = su.get_scan_list_stepped(
                    min_val=-13.5,
                    max_val=13.5,
                    step=5,
                    resolution=1E-3,
                    margin_pct=0.5,
                    reverse=False,
                    zigzag=True,
                    )
    print(f"voltage_list = {voltage_list}")


    def test_scan_piezo(v_list=voltage_list,
                        silent=True,
                        life_plot=True):
        # scan_list = su.get_scan_list_stepped(step=3,
        #                          zigzag=True)
        rm.scan_piezo(v_list=v_list, 
                         silent=silent, 
                         life_plot=life_plot)
      
    test_scan_piezo()

    # master_readout = r_man.master_diode.read_laser()
    # print(master_readout)
    # rm.laser_on(silent=True)
    # rm.laser_off(silent=True)
    rm.disconnect_all()