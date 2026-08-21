# \managers\lif_avp.py
####### TO DO:
##  stop progamm when the figure window is closed 
##  LIFManager or Plotter classes?

import threading
import time
import pandas as pd
import matplotlib.pyplot as plt
from PyQt6 import QtCore
from collections import deque # for work with que of limited length

from pathlib import Path
import os
import sys
import subprocess

import numpy as np

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

        ## varables for lif_monitor
        self.v_steps = [0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 3, 5]
        self._step_idx = 2 # defoult piezo voltage step 0.1 V
        self._monitoring_active = False

    ## -----------------------------------------------    
    ## switch on and device connect functions
    ## ----------------------------------------------
    def connect_all(self, silent=True):
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

    ## ----------------------------------------
    ## read out functions
    ## -------------------------------------
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

    ## -----------------------------------
    ## check functions
    ## ----------------------------------
    def check_piezo_limits(self, value: float) -> float | None:
        limits = self.master_diode.piezo['limits']
        if value < limits['min'] or value > limits['max']:
            print(f"{self.RED} Error in check_piezo_limits() from lif_avp.py: {self.RESET}")
            print(f"Voltage {value:.4f} V is out of piezo limits: "
                  f"[{limits['min']}, {limits['max']}]")
            print("value is skipped.")
            return None
        
        return value


    ## -----------------------------
    ## scan functions
    ## ---------------------------------
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
                # plt.switch_backend('QtAgg') ## use: %matplotlib QtAgg for Jupiter Notebook
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

        except Exception as e:
            print(f"{self.RED} Error in LIFManager.scan_piezo(){self.RESET}")
            print(e)
            result = None

        finally:
            # plt.switch_backend(initial_backend)
            print(f"----- scan_piezo() finished -----")

        return result


    def lif_monitor(self, max_points=100, 
                    meas_time=0.5, # [s] instrument readout time
                    pause_time=0.01, # for additional slow down
                    spec_line="Ar II", 
                    silent=True
                    ):
        """
        Real-time LIF monitoring with interactive plot and 
        key piezo tuning.
        Args:
            max_points (int): Number of points in the rolling window.
            meas_time (float): instrument readout time for scaling the rolling window.
            pause_time (float): additional slow down of the experiment
            spec_line (str): Target spectral line (Ar I or Ar II).
            silent (bool): If True, suppresses console output.
        Returns: 
            dict = {
                "laser_state": laser_state_dict,
                "scan_data": pd.DataFrame with collected data in the rolling wiindow
            }
        """

        plotter = LifeLIFPlotter(max_points=max_points, 
                                 pause_time=pause_time, 
                                 read_out_time=meas_time, 
                                 spec_line=spec_line)

        plotter.connect_key_controls(self._on_key)

        self._monitoring_active = True
        print(f"{self.GREEN}Monitoring started.{self.RESET}")
        print(f"----- Controls ------")
        print(f"piezo voltage increse/decrease: {self.CYAN}UP/DOWN {self.RESET}")
        print(f"voltge steps: {self.v_steps}V")
        print(f"defoult step: {self.v_steps[self._step_idx]}V, {self.CYAN}LEFT/RIGHT {self.RESET}")
        print(f"Quit: {self.CYAN} q {self.RESET}")

        start_time = time.perf_counter()
        try:
            while self._monitoring_active:
                ## --- Instrument readout section ---
                if not silent:
                    t0 = time.perf_counter()
                data = {}
                piezo = self.master_diode.read_piezo(silent=True)
                wavelength = self.wlm.read(
                                            device_read_time=False,
                                            slow=False,
                                            silent=True
                                            )
                lockin = self.lia.read_signal(silent=True, 
                                            device_read_time=False, 
                                            mode="magphase" # "xy"
                                            )
                t_rel = time.perf_counter() - start_time
                data = {
                    'time_s': t_rel,
                    'piezo_v': piezo,
                    **wavelength,
                    **lockin
                }

                if not silent:
                    print(f"readout time = {t0-time.perf_counter()}")

                ## --- Visualization update ---
                plotter.update_lines(data)
                plt.pause(pause_time)

        except Exception as e:
            print(f"{self.RED} LIFManager.lif_monitor() Error{self.RESET} out of loop: {e}")
        finally:
            self._monitoring_active = False
            if not silent:
                print(f"{self.CYAN}Monitoring session finished.{self.RESET}")
            
        ## Prepare and return data
        laser_state = self.read_state(silent=silent)
        df = pd.DataFrame(plotter.data_bufers)
        result = {
                    "laser_state": laser_state,
                    "scan_data": df
                }

        return result


    def _on_key(self, event):
        """Handle keyboard interactions from the plotter window.
        used in lif_monitor()
        """
        if event.key == 'q' or event.key == 'escape':
            self._monitoring_active = False
            return

        # Handle voltage changes (UP/DOWN arrows)
        if event.key in ['up', 'down']:
            step = self.v_steps[self._step_idx]
            piezo_str = self.master_diode.read_piezo(silent=True)
            piezo = float(piezo_str)
            target_v = piezo + (step if event.key == 'up' else -step)
            
            validated_v = self.check_piezo_limits(target_v)
            if validated_v is not None:
                v = validated_v
                self.master_diode.set_piezo(value=v, unit="V", silent=True)
                print(f"Piezo V -> {v:.4f} V (step: {step})")

        # Handle step size changes (LEFT/RIGHT arrows)
        elif event.key in ['left', 'right']:
            direction = 1 if event.key == 'right' else -1
            # Cycle through the predefined v_steps list
            self._step_idx = (self._step_idx + direction) % len(self.v_steps)
            print(f"Current step size: {self.v_steps[self._step_idx]} V")


class PiezoScanLifePlotter(PlotStyler, TerminalColours):

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

        self.set_window_on_top(fig=self.fig)
        # print("plt.ion")
        plt.subplots_adjust(hspace=0) # space between sublopts

        self._setup_axes(v_list)

        self.line_lockin, = self.ax_lockin.plot([], [], 'o', label='Magnitude [V]')
        self.line_wlm, = self.ax_wlm.plot([], [], 'o') #, label=f'Wavelength [{self.wlm.units}]'
        # print("plotter initialized")

    
    def _setup_axes(self, v_list):
        # print("setting axes")
        ## Set fixed X-axis limits
        v_min, v_max = min(v_list), max(v_list)
        v_range = v_max - v_min
        margin = v_range * 0.03 if v_range != 0 else 0.5
        self.ax_lockin.set_xlim(v_min - margin, v_max + margin)
        ## 
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
        self.ax_wlm.axhline(668.61379, color='gray', linestyle='--', linewidth=2, alpha=0.7)
        text = "Ar II 668.61379 nm vac"
        self.ax_wlm.text(x=v_list[0], 
                         y=668.61379 ,
                         s=text, 
                         transform=self.ax_wlm.transData,
                         color='gray',
                         verticalalignment='bottom',

                        )
        
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
                print(f"{self.RED}{self.__class__.__name__} error {self.RESET}")
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
        print(f"{self.GREEN }scan finished {self.RESET}")
        print("to end programm:")
        print("1. activate plot window")
        print("2. press 'q', 'escape', 'enter', 'return', 'space', ' ' ")
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
        
        self.set_window_on_top(fig=self.fig)
        plt.ioff()
        plt.show(block=True)


class LifeLIFPlotter(PlotStyler, TerminalColours):
    """
    Real-time plotter for lif_monitor(). 
    Displays Lock-in signal, Wavelength, and Piezo Voltage against time.
    allow ajust piezo voltage offset with arrows keys up and down 
    """
    ## keys as resived from devises
    ALLOWED_WLM_KEYS = {"nm", "THz"}
    LOCKIN_KEY = "Magnitude_V"
    PIEZO_KEY = "piezo_v"

    REFERENCE_LINES = {
        "Ar I": 667.9,
        "Ar II": 668.61379
    }

    def __init__(self, max_points=100, 
                 fig_size=(10, 8),
                 pause_time=0.01, 
                 read_out_time=0.1,
                 spec_line="Ar II"
                 ):
        
        self.max_points = max_points
        self.spec_line = spec_line
        self.pause_time = pause_time 
        ## selection of the key is in self.update_lines()
        self.wlm_key = None

        self.data_bufers = {}

        ## Setup Figure and Axes
        self.fig, (self.ax_lockin, 
                   self.ax_wlm, 
                   self.ax_piezo) = plt.subplots(3, 1, 
                                                 figsize=fig_size, 
                                                 sharex=True, 
                                                 constrained_layout=True
                                                )
        title="LifeLIFPlotter: LIF Real-Time Monitor"
        self.fig.canvas.manager.set_window_title(title)

        ## estimate length of time window
        self.dt_est = pause_time + read_out_time
        self.window_width = max_points * self.dt_est
        self.current_xlim = self.window_width
        self.ax_piezo.set_xlim(0, self.current_xlim)
        
        self.line_lockin, = self.ax_lockin.plot([], [], color='tab:red', 
                                                # label='Lock-in Signal [%]',
                                                marker='o',
                                                linestyle='-',
                                                linewidth=4,
                                                )
        self.line_wlm, = self.ax_wlm.plot([], [], color='tab:blue', 
                                          label='Wavelength',
                                          linestyle='-',
                                          linewidth=2,
                                          marker='o',
                                          markerfacecolor='white',
                                          markeredgecolor='tab:blue',
                                          markeredgewidth=1.5,
                                          )
        self.line_piezo, = self.ax_piezo.plot([], [], color='tab:purple', 
                                              label='Piezo [V]',
                                              linestyle='-',
                                              linewidth=2,
                                              marker='o',
                                              markerfacecolor='white',
                                              
                                              )

        self._setup_monitor_axes()
        self.set_window_on_top(self.fig)
        self.cid = None 
        plt.ion()


    def _setup_monitor_axes(self):
        """Internal method to apply styling and add reference spectral lines."""
        self.ax_piezo.set_xlabel("Relative Time [s]")
        self.ax_lockin.set_ylabel("Lock-in Signal [%]")
        self.ax_wlm.set_ylabel("Wavelength")
        self.ax_piezo.set_ylabel("Piezo [V]")

        ## using PlotSyler method
        self.set_scale_steps(self.ax_lockin)
        self.set_scale_steps(self.ax_wlm)
        self.set_scale_steps(self.ax_lockin)

        for ax in [self.ax_lockin, self.ax_wlm, self.ax_piezo]:
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper right')

        if self.spec_line in self.REFERENCE_LINES:
            target_wl = self.REFERENCE_LINES[self.spec_line]
            label = f"{self.spec_line}: {target_wl} nm"
            
            self.ax_wlm.axhline(target_wl, color='gray', linestyle='--', linewidth=1.5, alpha=0.6)
            self.ax_wlm.text(x=0.02, # 2% from left edge 
                             y=target_wl, # transform only for y: ax_wlm.get_yaxis_transform() 
                             s=label, 
                             transform=self.ax_wlm.get_yaxis_transform(), # self.ax_wlm.transData,
                             verticalalignment='bottom', 
                             color='gray', 
                             #fontsize=9
                             )


    def update_lines(self, data:dict):
        """Updates the canvas. This is where plt.draw() or fig.canvas.draw_idle() goes.
           for Jupyter %matplotlib qt better to use draw_idle()
        """
        for key, value in data.items():
            if key not in self.data_bufers:
                self.data_bufers[key] = deque(maxlen=self.max_points)
            self.data_bufers[key].append(float(value))

        if self.wlm_key is None:
            found_keys = self.ALLOWED_WLM_KEYS.intersection(data)     
            if not found_keys:
                print(f"{self.RED}{self.__class__.__name__} error {self.RESET}")
                raise KeyError(f"Wavelength units not found in data." 
                                f"Expected one of: {self.ALLOWED_WLM_KEYS}")
            
            self.wlm_key = next(iter(found_keys))
            self.ax_wlm.set_ylabel(f"Wavelength [{self.wlm_key}]")

        ## set lines
        t = self.data_bufers.get('time_s')
        self.line_lockin.set_data(t, self.data_bufers[self.LOCKIN_KEY])
        self.line_wlm.set_data(t, self.data_bufers[self.wlm_key])
        self.line_piezo.set_data(t, self.data_bufers[self.PIEZO_KEY])

        # shift of X axes
        if t[-1] > self.current_xlim:
            shift = self.window_width * 0.25 
            self.current_xlim = t[-1] + shift
            self.ax_piezo.set_xlim(self.current_xlim - self.window_width, self.current_xlim)
        
        # autoscale for Y axes
        for ax in [self.ax_lockin, self.ax_wlm, self.ax_piezo]:
            ax.relim()
            ax.autoscale_view(scalex=False) 

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(self.pause_time)


    def connect_key_controls(self, callback):
        self.cid = self.fig.canvas.mpl_connect('key_press_event', callback)
    

if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
    tc = TerminalColours()
    print(f"Test of the module: {tc.GREEN}{__file__}{tc.RESET}")
    lm = LIFManager()
    print(f"{tc.CYAN}initialized{tc.RESET} {lm=}")

    ##--------------------------------------------##
    ##              tests without devices         ##
    ## -------------------------------------------##

    def check_root_path():
        print(f"{tc.CYAN} \n  project root for internal imports: {tc.RESET}")
        print(f"{current_file=}")
        print(f"{project_root=}")

    # check_root_path()


    def test_label_keys():
        print(f"{tc.CYAN} \n  test @staticmethod _label_keys() {tc.RESET}")
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


    def test_lif_plotter(read_out_time=0.1):
        """
        A test function to verify visualization and window-shifting logic. 
        Simulates the LIF monitoring loop.
        """
        print(f"{tc.CYAN}\n------ Starting LifeLIFPlotter Test{tc.RESET}")
        plotter = LifeLIFPlotter(
            max_points=50, 
            pause_time=0.1,   
            read_out_time=read_out_time, 
            spec_line="Ar II"
        )
        # plt.pause(0.1)
        
        start_time = time.time()
        window_closed = False
        
        try:
            ## Simulate 80 iterations
            for i in range(80):
                ## Check if figure window present
                if not plt.fignum_exists(plotter.fig.number):
                    print(f"{tc.YELLOW}Test interrupted: Plot window was closed by user.{tc.RESET}")
                    window_closed = True
                    break


                current_time = time.time() - start_time
                
                ## data generation
                signal_val = 0.1 * np.random.random() + np.exp(-((current_time - 15)**2) / 10)
                wlm_val = 668.61379 + 0.0005 * np.sin(current_time * 0.5)
                piezo_val = 2.0 + (i % 50) * 0.1
                data = {
                    'time_s': current_time,
                    'Magnitude_V': signal_val,
                    'nm' : wlm_val,
                    'piezo_v': piezo_val,
                }
                
                ## plot data
                plotter.update_lines( data)
                plt.pause(read_out_time)
                if i % 20 == 0:
                    print(f"Iteration {i}: T={current_time:.2f}s, Sig={signal_val:.3f}V")

        except KeyboardInterrupt:
            print("Test interrupted by user.")
        finally:
            print(f"{tc.CYAN}===== ENDED: LifeLIFPlotter Test{tc.RESET}")

    test_lif_plotter(read_out_time=0.1)


    def test_check_piezo_limits():
        print(f"\n{tc.CYAN}----- Testing check_piezo_limits(Offline Mode){tc.RESET}")
        test_cases = [
        (5.0, "Valid value"),
        (-14.1, "Below minimum"),
        (13.51, "Above maximum"),
        (-13.5, "Minimum boundary"),
        (13.5, "Maximum boundary")
        ]
        i=0
        rm = LIFManager()
        for val, description in test_cases:
            result = rm.check_piezo_limits(val)
            status = f"{rm.GREEN}PASS{rm.RESET}" if (result == val or result is None) else f"{rm.RED}FAIL{rm.RESET}"
            print(f"Test {description}: Input={val}V -> Result={result} | {status}")
            if status == f"{rm.GREEN}PASS{rm.RESET}":
                i += 1

        if i == len(test_cases):
            print(f"{tc.GREEN} Success")
        else:
            print(f"{tc.RED} Test FAILD PASSED = {i} from {len(test_cases)}")
        print(f"{tc.CYAN}===== Ended: check_piezo_limits(Offline Mode){tc.RESET}")
        return

   #  test_check_piezo_limits()

    ##--------------------------------------------##
    ##              tests  devices                ##
    ## -------------------------------------------##

    def test_read_state():
        print(f"{tc.CYAN} \n----- Test: reading of the LIF state{tc.RESET}")
        readout = None
        try:
            lm._connect_device(lm.master_diode, silent=True)
            lm._connect_device(lm.amplifier_diode, silent=True)
            lm._connect_device(lm.wlm, silent=True)
            readout = lm.read_state()
            print(f"{tc.GREEN} successful reading {tc.RESET}")
        except Exception as e:
            print(f"{tc.RED} test_read_state() error: {tc.RESET} \n {e} ") 
        finally:
            lm.wlm.disconnect()
            lm.amplifier_diode.disconnect()
            lm.master_diode.disconnect()
        if readout:
            print(f"{tc.CYAN} LIF readout {tc.RESET}")
            print(readout)

        print(f"{tc.CYAN}======= END: Test: reading of the LIF state{tc.RESET}")
        return

   #  test_read_state()
 
    def test_scan_piezo(step=1, silent=True, life_plot=True, wait:int=5):
        print(f"{tc.CYAN}\n----- Test: scan_piezo() {tc.RESET}")
        voltage_list = su.get_scan_list_stepped(
                        min_val=-13.5,
                        max_val=13.5,
                        step=step,
                        resolution=1E-3,
                        margin_pct=0.5,
                        reverse=False,
                        zigzag=True,
                        )
        voltage_list.append(0)
        print(f"voltage_list = {voltage_list}")
        print(f"number of points = {len(voltage_list)}")

        try:
            lm.connect_all()
            lm.laser_on()
            print(f"waiting time {wait} s")
            i = 0
            for i in range(wait):
                print(f"left time = {wait - i} s")
                time.sleep(1)

            result = lm.scan_piezo(v_list=voltage_list, 
                            silent=silent, 
                            life_plot=life_plot)
            print(f"{tc.GREEN}{result.keys()=}{tc.RESET}")
        except Exception as e:
            print(f"{tc.RED} test_scan_piezo() error: {tc.RESET} \n {e} ")
        finally:
            lm.laser_off()
            lm.disconnect_all()

        print(f"{tc.CYAN}======= ENDED: scan_piezo(){tc.RESET}")
        return
 
    # test_scan_piezo(step=5, wait=5)

