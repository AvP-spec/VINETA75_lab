import threading
import time
import numpy as np
import pandas as pd

from pathlib import Path
import os
import sys

data_path = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/lif_py_test")

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from devices.Advanttest_Q8326 import Q8326
from devices.pilot_pz import PilotPZ500, PilotPC4000
from devices.function_generator import FunctionGenerator
from devices.lock_in_amplifier import LockInAmplifier
from devices.daq import DAQ
import utils.scan_utils as su
from utils.terminal_styler import TerminalColours

style = TerminalColours()

import utils.lif_plots as lp

class LIFManager(TerminalColours):

    def __init__(self):
        self.master_diode = PilotPZ500()
        self.amplifier_diode = PilotPC4000()
        self.wlm = Q8326()
        self.scope = None # not yet implemented
        self.fg = FunctionGenerator()
        self.lia = LockInAmplifier()
        self.daq = DAQ()

        self._connect_device(self.master_diode, device_type="COM")
        self._connect_device(self.amplifier_diode)
        self._connect_device(self.wlm, device_type="GPIB")
        self._connect_device(self.fg, device_type="COM")
        self._connect_device(self.lia, device_type="COM")
        self.daq.connect()
         


    def _connect_device(self, device, device_type:str="COM"):
        ''' device types: COM, GPIB'''
        if device is None:
            print(f"{self.RED}")
            print(f"LIFManager._connect_device(): device is None ")
            print(f"{self.RESET}")

            return

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
        self.fg.disconnect()
        self.lia.disconnect()
        self.daq.disconnect()

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
              f"LIFManager: Starting lasers sequentially{self.RESET}")
        try:
            self.master_diode.switch_on(silent=silent)
            self.amplifier_diode.switch_on(silent=silent)
        except TimeoutError as e:
            print(f"Safety shutdown: {e}")
            self.laser_off(silent=silent)
        return self

    def laser_off(self, silent=False):
        ### the amplifier diode should not operate without master
        print(f"{self.CYAN} \n LIFManager: Shating lasers off{self.RESET}")
        self.amplifier_diode.switch_off()
        self.master_diode.switch_off()
        return self
    
    def aom_on(self, frequency_Hz: float = 1000.0, 
               amplitude_V: float = 1.0, silent = True): 
        self.fg.set_frequency(frequency_Hz, silent=silent)
        self.fg.set_amplitude(amplitude_V, silent=silent)
        self.fg.set_waveform("SIN", silent=silent)
        self.fg.output_on(silent=silent)
        return self
    
    def aom_off(self, silent=True): 
        self.fg.output_off(silent=silent)
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
        Order: wlm, master, amplif, lia, daq
        '''
        start_time = time.perf_counter()

        ### container to form the oreder of the output
        ### [wlm, master, amplif]
        task_results = [None]*5

        # data = {}  
        def worker(index, label, device, method_name, kwargs):
            # PRÜFUNG: Nur ausführen, wenn das Gerät verbunden ist!
            if device is None or getattr(device, 'connection', None) is None:
                # Still beenden, wenn keine Verbindung existiert
                return 

            try:
                # Die Methode dynamisch vom Objekt aufrufen
                method = getattr(device, method_name)
                readout = method(**kwargs)
                task_results[index] = self._label_keys(readout, label)
            except AttributeError:
                pass
            except Exception as e:
                task_results[index] = {f"{label}_error": str(e)}

        tasks = [
            (0, 'wlm', self.wlm, 'read', 
            {'silent': silent, 'device_read_time': device_read_time}),
            
            (1, 'master', self.master_diode, 'read_laser', 
            {'device_read_time': device_read_time}),
            
            (2, 'amplif', self.amplifier_diode, 'read_laser', 
            {'device_read_time': device_read_time}),
            
            (3, 'lia', self.lia, 'read_signal', 
            {'silent': silent, 'device_read_time': device_read_time}),
            
            (4, 'daq', self.daq, 'read_lif_signal', 
            {'silent': silent, 'device_read_time': device_read_time}),
        ]

        threads = []
        for index, label, device, method_name, kwargs in tasks:
            t = threading.Thread(target=worker, args=(index, label, device, method_name, kwargs))
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
    
    def get_device_state_meta(self) -> dict:
        '''Returns current device settings as metadata dict for file_utils.'''
        meta = {}
        try:
            meta['master_set_current_A']    = float(self.master_diode.read_setcurrent())
            meta['master_set_temperature_C']= float(self.master_diode.read_settemperature())
            meta['master_piezo_V']          = float(self.master_diode.read_piezo())
            meta['master_laser_mode']       = self.master_diode.read_mode()
            meta['master_laser_status']     = self.master_diode.read_status()
            meta['amplif_set_current_A']    = float(self.amplifier_diode.read_setcurrent())
            meta['amplif_set_temperature_C']= float(self.amplifier_diode.read_settemperature())
            meta['amplif_laser_mode']       = self.amplifier_diode.read_mode()
            meta['amplif_laser_status']     = self.amplifier_diode.read_status()
            meta['wlm_average']             = self.wlm.average
        except Exception as e:
            meta['device_state_error'] = str(e)
        return meta



    def scan_piezo(self, 
                   v_step:float=3, # piezo voltage step 
                   v_max:float=None, # max piezo voltage
                   v_min:float=None, # min piezo voltage
                   v_unit:str="[V]", # piezo voltage units 
                   n_wlm:int=5, # number of wavelength measurements
                   zigzag:bool=True,
                   hysteresis: bool=False,
                   # device_read_time=False,
                   silent: bool = True, # only for wlm in current implementation
                   plot: bool = False, 
                   save_path: str = None, 
                    ):
    
        '''
        piezo info: 
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

        if hysteresis: 
            v_list_forward = su.get_scan_list_stepped( 
                min_val=v_min, max_val=v_max, step=v_step, 
                resolution=resolution, margin_pct=0.5, reverse=False, zigzag=False
            )
            v_list_backward = su.get_scan_list_stepped( 
                min_val=v_min, max_val=v_max, step=v_step, 
                resolution=resolution, margin_pct=0.5, reverse=True, zigzag=False
            )
            v_list = v_list_forward + v_list_backward
            print(f"{self.GREEN}Hysteresis mode active: scanning forward and backward.{self.RESET}")
        else: 
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

        for i, v in enumerate(v_list): 
            print(f"  point {i+1}/{len(v_list)}, piezo={v} V", end=" → ")
            self.master_diode.set_piezo(value=v, unit="V", silent=True)
            states = [self.read_state(silent=silent) for _ in range(n_wlm)]

            wls = [s.get('wlm_wavelength', np.nan) for s in states]
            wl_mean = sum(wls) / n_wlm
            wl_std = float(np.std(wls)) if n_wlm > 2 else 0.0
            wl_err = (max(wls) - min(wls)) / 2

            print(f"wavelength = {wl_mean*1E9:.4f} nm")

            last = states[-1]

            record = {
                'time_s':                   time.perf_counter() - t0,
                'piezo_V':                  v,
                'wl_mean_m':                wl_mean,
                'wl_std_m':                 wl_std,
                'wl_err_m':                 wl_err,
                'master_current_A':         last['master_current_A'],
                'master_temperature_C':     last['master_temperature_C'],
                'master_power':             last['master_power'],
                'master_piezo_off_set_V':   last['master_piezo_off_set_V'],
                'amplif_current_A':         last['amplif_current_A'],
                'amplif_temperature_C':     last['amplif_temperature_C'],
                'amplif_power':             last['amplif_power'],
                'daq_lif_signal_V':         last.get('daq_lif_signal_V'),
                'daq_lif_std_V':            last.get('daq_lif_std_V'),
                'lia_R':                    last.get('lia_R'),
                'lia_X':                    last.get('lia_X'),
                'lia_Y':                    last.get('lia_Y'),
                'lia_theta_deg':            last.get('lia_theta_deg'),
            }

            result.append(record)


        df = pd.DataFrame(result)
        print(f"\n{self.GREEN}scan_piezo() finished: "
              f"{len(df)} points in {df['time_s'].iloc[-1]:.1f} s{self.RESET}")
        print(df.to_string())

        if plot: 
            lp.plot_scan_piezo(df, save_path=save_path)
        
        return df
    
    def _plot_scan_piezo(self, df: pd.DataFrame, save_path: str = None):
        '''Plot results of scan_piezo(): wavelength vs piezo and temperature stability.'''
        import matplotlib.pyplot as plt

        fig, (ax_wl, ax_temp) = plt.subplots(
            2, 1, figsize=(10, 7), 
            gridspec_kw={"hspace": 0.35}
        )

        # --- Plot A: Wellenlänge vs. Piezo-Spannung ---
        wl_nm     = df['wl_mean_m'] * 1e9
        wl_err_nm = df['wl_std_m']  * 1e9
        piezo     = df['piezo_V']

        ax_wl.errorbar(
            piezo, wl_nm,
            yerr=wl_err_nm,
            fmt='o-', color='tab:blue',
            markersize=5, linewidth=1.4,
            capsize=3, capthick=1, elinewidth=0.8,
            label='λ mean ± std'
        )
        ax_wl.set_xlabel("Piezo-Spannung [V]", fontsize=11)
        ax_wl.set_ylabel("Wellenlänge [nm]",   fontsize=11)
        ax_wl.set_title("Wellenlänge vs. Piezo-Spannung", fontsize=11)
        ax_wl.legend(fontsize=9)
        ax_wl.grid(True, linestyle='--', alpha=0.4)

        # Abstimmrate als Text
        if len(df) > 1:
            dv  = piezo.max() - piezo.min()
            dwl = wl_nm.max() - wl_nm.min()
            rate = dwl / dv if dv > 0 else 0
            ax_wl.text(
                0.97, 0.05,
                f"Abstimmrate: {rate*1e3:.2f} pm/V",
                transform=ax_wl.transAxes,
                fontsize=9, ha='right', va='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
            )

        # --- Plot B: Temperatur vs. Zeit ---
        time_s = df['time_s']

        ax_temp.plot(time_s, df['master_temperature_C'],
                    'o-', color='tab:blue', markersize=4,
                    linewidth=1.2, label='Master')
        ax_temp.plot(time_s, df['amplif_temperature_C'],
                    's--', color='tab:orange', markersize=4,
                    linewidth=1.2, label='Amplifier')

        ax_temp.set_xlabel("Zeit [s]",          fontsize=11)
        ax_temp.set_ylabel("Temperatur [°C]",   fontsize=11)
        ax_temp.set_title("Laser-Temperatur während des Scans", fontsize=11)
        ax_temp.legend(fontsize=9)
        ax_temp.grid(True, linestyle='--', alpha=0.4)

        # Temperaturschwankung als Text
        t_master_range = df['master_temperature_C'].max() - df['master_temperature_C'].min()
        t_amplif_range = df['amplif_temperature_C'].max() - df['amplif_temperature_C'].min()
        ax_temp.text(
            0.97, 0.97,
            f"Master Δ: {t_master_range*1e3:.1f} mK\n"
            f"Amplif Δ: {t_amplif_range*1e3:.1f} mK",
            transform=ax_temp.transAxes,
            fontsize=9, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
        )

        fig.suptitle("scan_piezo() Ergebnis", fontsize=13, fontweight='bold')
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"{self.GREEN}Plot gespeichert: {save_path}{self.RESET}")

        print(f"{style.YELLOW2}-------- Close Figure to continue -------- {style.RESET}")
        plt.show(block=True)
        # plt.pause(0.5)
        # plt.close(fig)



    def measure_laser_settling(self, 
                               scenarios: list = None, 
                               n_measurements: int = 15, 
                               sleep: float = 0.1,
                               plot: bool = True, 
                               save_path: str = None,
                               ): 
        piezo_limits = self.master_diode.piezo['limits']
        v_min = piezo_limits['min']
        v_max = piezo_limits['max']
        
        if scenarios is None:
            scenarios = [
                
                (v_max, v_min,  "max → min (worst case reverse)"),
                (v_min, v_max,  "min → max (worst case)"),
                # (0,     5,      "small step: 0 → 5 V"),
                # (5,     0,      "small step: 5 → 0 V"),
                # (0,     v_max,  "half range: 0 → max"),
            ]

        all_results = {}  # {label: DataFrame}

        for v_start, v_end, label in scenarios:
            print(f"\n{self.CYAN}=== Settling test: {label} ==={self.RESET}")

            # move to start position and wait for settling
            print(f"  Moving to start position {v_start} V ...")
            self.master_diode.set_piezo(value=v_start, unit="V", silent=True)
            time.sleep(2.0)  # wait for laser to settle at start

            # execute the step
            print(f"  Step to {v_end} V – starting measurements ...")
            t_step = time.perf_counter()
            self.master_diode.set_piezo(value=v_end, unit="V", silent=True)

            # measure settling
            records = []
            for i in range(n_measurements):
                print(f"Messung Nr. {i}")
                t = time.perf_counter() - t_step

                master_data = self.master_diode.read_laser(device_read_time=False)
                amplif_data = self.amplifier_diode.read_laser(device_read_time=False)

                records.append({
                    'time_s':                    t,
                    'master_current_A':          master_data['current_A'],
                    'master_set_current_A':      master_data['set_current_A'],
                    'master_temperature_C':      master_data['temperature_C'],
                    'master_set_temperature_C':  master_data['set_temperature_C'],
                    'master_power':              master_data['power'],
                    'amplif_current_A':          amplif_data['current_A'],
                    'amplif_set_current_A':      amplif_data['set_current_A'],
                    'amplif_temperature_C':      amplif_data['temperature_C'],
                    'amplif_set_temperature_C':  amplif_data['set_temperature_C'],
                    'amplif_power':              amplif_data['power'],
                })
                time.sleep(sleep)

            df = pd.DataFrame(records).set_index('time_s')
            all_results[label] = df
            print(f"  {self.GREEN}Done. {len(df)} measurements over {df.index[-1]:.1f} s{self.RESET}")

        if plot:
            lp.plot_settling(df, scenarios=scenarios, save_path=save_path)

        return all_results
    
    def measure_laser_warmup(self, 
                             n_measurements: int = 15, 
                             sleep: float = 0.1, 
                             plot: bool = True, 
                             save_path: str = None, 
                             ):
        print(f"\n {self.MAGENTA} Measuring laser warmup for {n_measurements} time-steps{self.RESET}")
        record = []
        t_step = time.perf_counter()

        for i in range(n_measurements):
            print(f"Messung Nr. {i}")
            t = time.perf_counter() - t_step

            master_data = self.master_diode.read_laser(device_read_time=False)
            amplif_data = self.amplifier_diode.read_laser(device_read_time=False)

            record.append({
                'time_s':                    t,
                'master_current_A':          master_data['current_A'],
                'master_set_current_A':      master_data['set_current_A'],
                'master_temperature_C':      master_data['temperature_C'],
                'master_set_temperature_C':  master_data['set_temperature_C'],
                'master_power':              master_data['power'],
                'amplif_current_A':          amplif_data['current_A'],
                'amplif_set_current_A':      amplif_data['set_current_A'],
                'amplif_temperature_C':      amplif_data['temperature_C'],
                'amplif_set_temperature_C':  amplif_data['set_temperature_C'],
                'amplif_power':              amplif_data['power'],
            })
            time.sleep(sleep)

        df = pd.DataFrame(record).set_index('time_s')
        print(f"  {self.GREEN}Done. {len(df)} measurements over {df.index[-1]:.1f} s{self.RESET}")

        # if plot:
        #     lp.plot_warmup(df, save_path=save_path)
        
        return df
    
    def _plot_warmup(self, df: pd.DataFrame, save_path: str = None):
        '''Plot laser warmup: current drift and temperature drift over time.'''
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        fig = plt.figure(figsize=(14, 8))
        gs  = GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

        axes = [fig.add_subplot(gs[row, col]) 
                for row in range(2) for col in range(3)]

        # --- Daten vorbereiten ---
        time_s = df.index

        plots = [
            # (title, y_master, y_amplif, ylabel, nulllinie)
            ("Current [A]",
            df['master_current_A'],
            df['amplif_current_A'],
            "Current [A]", False),

            ("Temperature [°C]",
            df['master_temperature_C'],
            df['amplif_temperature_C'],
            "Temperature [°C]", False),

            ("Power",
            df['master_power'],
            df['amplif_power'],
            "Power", False),

            ("Current drift (Ist - Soll) [A]",
            df['master_current_A'] - df['master_set_current_A'],
            df['amplif_current_A'] - df['amplif_set_current_A'],
            "Drift [A]", True),

            ("Temperature drift (Ist - Soll) [°C]",
            df['master_temperature_C'] - df['master_set_temperature_C'],
            df['amplif_temperature_C'] - df['amplif_set_temperature_C'],
            "Drift [°C]", True),
        ]

        for ax, (title, y_master, y_amplif, ylabel, nulllinie) in zip(axes, plots):
            ax.plot(time_s, y_master,
                    color='steelblue', linewidth=1.2, label='master')
            ax.plot(time_s, y_amplif,
                    color='tomato', linewidth=1.2, linestyle='--', label='amplif')
            if nulllinie:
                ax.axhline(0, color='black', linewidth=0.8, linestyle='-')
            ax.set_title(title, fontsize=9)
            ax.set_xlabel("time [s]", fontsize=8)
            ax.set_ylabel(ylabel, fontsize=8)
            ax.legend(fontsize=8)
            ax.grid(True, linestyle=':', alpha=0.6)

        # sechsten Subplot ausblenden (nur 5 Plots)
        axes[5].set_visible(False)

        fig.suptitle("Laser Warmup", fontsize=13, fontweight='bold')
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"{self.GREEN}Plot gespeichert: {save_path}{self.RESET}")

        plt.show(block=True)
        # plt.pause(0.5)
        # plt.close(fig)

    def _wait_for_temperature(self, laser, target_temp: float, tolerance: float = 0.1, timeout: float = 500):
        """
        Wartet, bis die Temperatur innerhalb einer Toleranz des Zielwerts liegt.
        timeout: maximale Wartezeit in Sekunden (Standard 5 Minuten)

        Parameters:
        laser        : Das Laser-Objekt (z.B. self.master_diode oder self.amplifier_diode)
        target_temp  : Zieltemperatur in °C
        tolerance    : Erlaubte Abweichung
        timeout      : Maximale Wartezeit in Sekunden
        """
        start_time = time.perf_counter()
        laser_name = "Master" if laser == self.master_diode else "Amplifier"
        print(f"  Waiting for {laser_name} temperature to reach {target_temp}°C (±{tolerance}°C)...", end="")
        
        # Flag für den overshoot
        has_overshoot = False
        # prüfen, ob heizen oder kühlen
        initial_data = laser.read_laser(device_read_time=False)
        initial_temp = initial_data['temperature_C']
        is_heating = target_temp > initial_temp

        while True:
            # Aktuellen Wert auslesen
            current_data = laser.read_laser(device_read_time=False)
            current_temp = current_data['temperature_C']

            # 1. Überschwingen erkennen: 
            if not has_overshoot: 
                if is_heating and current_temp > target_temp: 
                    time.sleep(2.0)
                    has_overshoot = True
                    print("\n  Overshoot detected, waiting for return to target...", end="")
                elif not is_heating and current_temp < target_temp: 
                    time.sleep(2.0)
                    has_overshoot = True
                    print("\n  Overshoot detected, waiting for return to target...", end="")
            
            # 2. Toleranzprüfung nur nach einmal überschwingen
            if has_overshoot and abs(current_temp - target_temp) <= tolerance: 
                print(f"\n {self.GREEN}Stabilized! Current Temp: {current_temp:.2f} °C{self.RESET}")
                return True
            
            # Timeout-Prüfung
            if (time.perf_counter() - start_time) > timeout:
                print(f"\n  {self.RED}Timeout! Target not reached. Current Temp: {current_temp:.2f}°C{self.RESET}")
                return False
            
            # Kleiner Punkt zur Visualisierung im Terminal
            print(".", end="", flush=True)
            time.sleep(2.0) # Nicht zu oft abfragen, um den Bus nicht zu belasten
    
    def measure_temperature_settling(self, 
                               scenarios: list = None, 
                               n_measurements: int = 50, 
                               sleep: float = 1.0, 
                               plot: bool = True, 
                               save_path: str = None):
        """
        Misst das Settling-Verhalten des Lasers bei Temperaturänderungen.
        """
        # Standard-Szenarien für Temperatur (Start_Temp, Ziel_Temp, Label)
        if scenarios is None:
            scenarios = [
                (20.0, 10.0, "Cooling: 20°C → 10°C"),
                (10.0, 20.0, "Heating: 10°C → 20°C"),
            ]

        all_results = {}  # {label: DataFrame}

        for t_start, t_end, label in scenarios:
            print(f"\n{self.CYAN}=== Temperature Settling test: {label} ==={self.RESET}")

            # 1. Setze Starttemperatur und warte auf thermisches Gleichgewicht
            print(f"  Moving to start temperature {t_start} °C ...")
            self.master_diode.set_temperature(value=t_start, unit="C", silent=True)
            
            success = self._wait_for_temperature(t_start, tolerance=0.1, timeout=600)
            if not success: 
                print("  Warning: Start temperature not fully stabilized. Proceeding anyway...")
            print("    Waiting 45 more seconds for stabilization...")
            time.sleep(45) 

            # 2. Ausführen des Temperatursprungs
            print(f"  Step to {t_end} °C – starting measurements ...")
            t_step = time.perf_counter()
            self.master_diode.set_temperature(value=t_end, unit="C", silent=True)

            # 3. Settling messen
            records = []
            for i in range(n_measurements):
                # Fortschrittsanzeige alle 5 Messungen, um das Terminal nicht zu fluten
                if i % 5 == 0:
                    print(f"  Measurement {i}/{n_measurements}...")
                    
                t = time.perf_counter() - t_step

                master_data = self.master_diode.read_laser(device_read_time=False)
                amplif_data = self.amplifier_diode.read_laser(device_read_time=False)

                records.append({
                    'time_s':                    t,
                    'master_current_A':          master_data['current_A'],
                    'master_set_current_A':      master_data['set_current_A'],
                    'master_temperature_C':      master_data['temperature_C'],
                    'master_set_temperature_C':  master_data['set_temperature_C'],
                    'master_power':              master_data['power'],
                    'amplif_current_A':          amplif_data['current_A'],
                    'amplif_set_current_A':      amplif_data['set_current_A'],
                    'amplif_temperature_C':      amplif_data['temperature_C'],
                    'amplif_set_temperature_C':  amplif_data['set_temperature_C'],
                    'amplif_power':              amplif_data['power'],
                })
                time.sleep(sleep)

            df = pd.DataFrame(records).set_index('time_s')
            all_results[label] = df
            print(f"  {self.GREEN}Done. {len(df)} measurements over {df.index[-1]:.1f} s{self.RESET}")

        if plot:
            lp.plot_temperature_settling(all_results, scenarios=scenarios, save_path=save_path)

        self.master_diode.set_temperature(value=16, unit="C", silent=True)
        return all_results 
    
    
    def _plot_settling(self, all_results: dict, scenarios: list, save_path: str = None): 
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        n_scenarios = len(scenarios)
        fig = plt.figure(figsize=(14, 4 * n_scenarios))
        gs = GridSpec(n_scenarios, 3, figure=fig, hspace=0.5, wspace=0.35)

        col_titles = ['Current [A]', 'Temperature [°C]', 'Power']

        for row, (v_start, v_end, label) in enumerate(scenarios):
            df = all_results[label]

            axes = [fig.add_subplot(gs[row, col]) for col in range(3)]

            # current
            axes[0].plot(df.index, df['master_current_A']-df['master_set_current_A'],
                        color='steelblue', label='master')
            axes[0].plot(df.index, df['amplif_current_A']-df['amplif_set_current_A'],
                        color='tomato', label='amplif', linestyle='--')
            axes[0].axhline(0, color='black', linewidth=0.8, linestyle='-')

            # temperature
            axes[1].plot(df.index, df['master_temperature_C']-df['master_set_temperature_C'],
                        color='steelblue', label='master')
            axes[1].plot(df.index, df['amplif_temperature_C']-df['amplif_set_temperature_C'],
                        color='tomato', label='amplif', linestyle='--')
            axes[1].axhline(0, color='black', linewidth=0.8, linestyle='-')

            # power
            axes[2].plot(df.index, df['master_power'],
                        color='steelblue', label='master')
            axes[2].plot(df.index, df['amplif_power'],
                        color='tomato', label='amplif', linestyle='--')

            for col, ax in enumerate(axes):
                ax.set_xlabel('time [s]')
                ax.legend(fontsize=8)
                ax.grid(True, linestyle=':', alpha=0.6)
                if col == 0:
                    ax.set_ylabel(f"{label}\n\n{col_titles[col]}", fontsize=9)
                else:
                    ax.set_ylabel(col_titles[col], fontsize=9)
                if row == 0:
                    ax.set_title(col_titles[col], fontsize=10)

        fig.suptitle('Laser settling after piezo step', fontsize=13, y=1.01)
        plt.tight_layout()

        if save_path: 
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"{self.GREEN}Plot gespeichert: {save_path}{self.RESET}")

        print(f"{style.YELLOW2}-------- Close Figure to continue -------- {style.RESET}")
        plt.show(block=True)
        # plt.pause(1)
        # plt.close(fig)



    def set_wavelength(self,
                    target_wavelength_m: float = 668.4e-9,
                    tolerance_pm: float = 1.0,
                    coarse_tolerance_pm: float = 100.0,
                    use_current: bool = False,
                    use_temperature: bool = True,
                    n_wlm: int = 5,
                    max_iterations: int = 50,
                    silent: bool = False,
                    ) -> bool:
        '''
        Sets laser to target wavelength in two steps:
        1. Coarse tuning via temperature and/or current
        2. Fine tuning via piezo

        Parameters
        ----------
        target_wavelength_m : target wavelength [m]
        tolerance_pm        : final tolerance for piezo fine tuning [pm]
        coarse_tolerance_pm : tolerance for coarse tuning [pm]
        use_current         : enable current tuning in coarse step
        use_temperature     : enable temperature tuning in coarse step
        n_wlm               : WLM measurements to average per step
        max_iterations      : max iterations per tuning stage
        '''
        target_nm = target_wavelength_m * 1e9
        tol_m     = tolerance_pm    * 1e-12
        coarse_m  = coarse_tolerance_pm * 1e-12

        piezo_limits = self.master_diode.piezo['limits']
        v_min = piezo_limits['min']
        v_max = piezo_limits['max']
        v_mid = (v_min + v_max) / 2

        current_limits = self.master_diode.current['limits']
        i_min  = current_limits['min']
        i_max  = 0.073              # Secure-Setup-Limit

        T_min  = -5.0               # °C
        T_max  = 30.0               # °C

        if not use_current and not use_temperature:
            print(f"{self.RED}set_wavelength(): mindestens eine Grobabstimmung "
                f"(Strom oder Temperatur) muss aktiviert sein.{self.RESET}")
            return False

        print(f"\n{self.CYAN}set_wavelength(): "
            f"target = {target_nm:.4f} nm, "
            f"tolerance = ±{tolerance_pm:.1f} pm\n"
            f"  Grobabstimmung: "
            f"{'Strom ' if use_current else ''}"
            f"{'Temperatur' if use_temperature else ''}{self.RESET}")

        def _measure_wl() -> float:
            wls = [self.wlm.read(silent=True)['wavelength']
                for _ in range(n_wlm)]
            return sum(wls) / n_wlm

        # ----------------------------------------------------------------
        # Schritt 1: Grobabstimmung
        # Reihenfolge: erst Temperatur (langsam, großer Bereich),
        #              dann Strom (schnell, kleiner Bereich)
        # ----------------------------------------------------------------
        print(f"\n{self.MAGENTA}  Schritt 1: Grobabstimmung ...{self.RESET}")

        self.master_diode.set_piezo(value=v_mid, unit="V", silent=True)

        tuning_rate_current = -2.2435e-9   # m/A
        tuning_rate_temp    = -12e-12      # m/K  (-12 pm/K)

        i_current = 0.05
        T_current = float(self.master_diode.read_settemperature())

        if use_current:
            self.master_diode.set_current(i_current, unit="A", silent=True)
            time.sleep(2.0)

        # --- Schritt 1a: Temperatur-Grobabstimmung ---
        if use_temperature:
            print(f"  {self.MAGENTA}Schritt 1a: Temperatur-Abstimmung ...{self.RESET}")
            for i in range(max_iterations):
                wl       = _measure_wl()
                error_m  = target_wavelength_m - wl
                error_pm = error_m * 1e12

                if not silent:
                    print(f"  [temp]   iter {i+1:2d}: "
                        f"λ={wl*1e9:.6f} nm, "
                        f"error={error_pm:+.1f} pm, "
                        f"T={T_current:.3f} °C")

                if abs(error_m) <= coarse_m:
                    print(f"  {self.GREEN}Temperatur-Abstimmung erreicht: "
                        f"error = {error_pm:+.1f} pm{self.RESET}")
                    break

                # Temperatur-Korrektur – maximal 2°C pro Schritt
                max_step_K  = 2.0
                T_correction = np.clip(error_m / tuning_rate_temp,
                                    -max_step_K, max_step_K)
                T_new = np.clip(T_current + T_correction, T_min, T_max)

                if T_new <= T_min:
                    print(f"  {self.YELLOW}Temperatur-Untergrenze erreicht "
                        f"({T_min}°C){self.RESET}")
                    break
                if T_new >= T_max:
                    print(f"  {self.YELLOW}Temperatur-Obergrenze erreicht "
                        f"({T_max}°C){self.RESET}")
                    break

                # Abstimmrate adaptiv aktualisieren
                if i > 0:
                    dT = T_new - T_current
                    if abs(dT) > 0.01:
                        tuning_rate_temp = (0.7 * tuning_rate_temp
                                        + 0.3 * (error_m / dT))
                        tuning_rate_temp = np.clip(tuning_rate_temp,
                                                -50e-12, -1e-12)

                self.master_diode.set_temperature(T_new, unit="C", silent=True)
                T_current = T_new
                success = self._wait_for_temperature(T_new, tolerance=tolerance_pm, timeout=600)
                if not success: 
                    print("  Warning: Start temperature not fully stabilized. Proceeding anyway...")
                print("    Waiting 10 more seconds for stabilization...")
                time.sleep(10)

            else:
                print(f"  {self.YELLOW}Temperatur-Abstimmung: "
                    f"max iterations erreicht{self.RESET}")

        # --- Schritt 1b: Strom-Grobabstimmung ---
        if use_current:
            print(f"  {self.MAGENTA}Schritt 1b: Strom-Abstimmung ...{self.RESET}")
            for i in range(max_iterations):
                wl       = _measure_wl()
                error_m  = target_wavelength_m - wl
                error_pm = error_m * 1e12

                if not silent:
                    print(f"  [coarse] iter {i+1:2d}: "
                        f"λ={wl*1e9:.6f} nm, "
                        f"error={error_pm:+.1f} pm, "
                        f"I={i_current*1e3:.2f} mA")

                if abs(error_m) <= coarse_m:
                    print(f"  {self.GREEN}Strom-Abstimmung erreicht: "
                        f"error = {error_pm:+.1f} pm{self.RESET}")
                    break

                max_step_A   = 0.050
                i_correction = np.clip(error_m / tuning_rate_current,
                                    -max_step_A, max_step_A)
                i_new = np.clip(i_current + i_correction, i_min, i_max)

                if i_new <= i_min:
                    print(f"  {self.YELLOW}Strom-Untergrenze erreicht{self.RESET}")
                    break
                if i_new >= i_max:
                    print(f"  {self.YELLOW}Strom-Obergrenze erreicht{self.RESET}")
                    break

                if i > 0:
                    di = i_new - i_current
                    if abs(di) > 1e-4:
                        tuning_rate_current = (0.7 * tuning_rate_current
                                            + 0.3 * (error_m / di))

                self.master_diode.set_current(i_new, unit="A", silent=True)
                i_current = i_new
                time.sleep(0.5)

            else:
                print(f"  {self.YELLOW}Strom-Abstimmung: "
                    f"max iterations erreicht{self.RESET}")

        # Prüfe ob Grobabstimmung erfolgreich
        wl       = _measure_wl()
        error_m  = target_wavelength_m - wl
        error_pm = error_m * 1e12
        if abs(error_m) > coarse_m:
            print(f"  {self.RED}Grobabstimmung nicht erfolgreich: "
                f"error = {error_pm:+.1f} pm – Feinabstimmung wird trotzdem versucht"
                f"{self.RESET}")

        # ----------------------------------------------------------------
        # Schritt 2: Feinabstimmung über Piezo
        # ----------------------------------------------------------------
        print(f"\n{self.MAGENTA}  Schritt 2: Feinabstimmung über Piezo ...{self.RESET}")

        tuning_rate_piezo = 1.0564e-11   # m/V
        v_current = float(self.master_diode.read_piezo())

        for i in range(max_iterations):
            wl       = _measure_wl()
            error_m  = target_wavelength_m - wl
            error_pm = error_m * 1e12

            if not silent:
                print(f"  [fine]   iter {i+1:2d}: "
                    f"λ={wl*1e9:.6f} nm, "
                    f"error={error_pm:+.3f} pm, "
                    f"V={v_current:.4f} V")

            if abs(error_m) <= tol_m:
                print(f"\n{self.GREEN}set_wavelength(): Ziel erreicht. "
                    f"λ = {wl*1e9:.6f} nm "
                    f"(error = {error_pm:+.3f} pm){self.RESET}")
                return True

            v_correction = error_m / tuning_rate_piezo
            v_new = np.clip(v_current + v_correction, v_min, v_max)

            if v_new in (v_min, v_max):
                print(f"  {self.RED}Piezo-Grenze erreicht – "
                    f"Feinabstimmung nicht möglich.{self.RESET}")
                return False

            if i > 0:
                dv = v_new - v_current
                if abs(dv) > 0.001:
                    tuning_rate_piezo = (0.7 * tuning_rate_piezo
                                        + 0.3 * (error_m / dv))
                    tuning_rate_piezo = np.clip(tuning_rate_piezo,
                                                0.5e-12, 10e-12)

            self.master_diode.set_piezo(value=v_new, unit="V", silent=True)
            v_current = v_new

        print(f"{self.RED}set_wavelength(): Feinabstimmung: "
            f"max iterations erreicht{self.RESET}")
        return False


    def drift_monitor(self,
                  duration_s: float = 60,
                  interval_s: float = 5,
                  plot: bool = True,
                  save_path: str = None,
                  silent: bool = False,
                  ):
        print(f"\n{self.CYAN}Starting Drift Monitor for {duration_s} s, "
            f"interval {interval_s} s ...{self.RESET}")

        drift_records = []
        t_start = time.perf_counter()

        try:
            while time.perf_counter() - t_start < duration_s:
                t_current = time.perf_counter() - t_start

                # WLM
                wlm_data   = self.wlm.read(silent=True, device_read_time=False)
                wavelength = wlm_data['wavelength']

                # LIA – optional
                try:
                    lia_data  = self.lia.read_signal(silent=True, device_read_time=False)
                    intensity = lia_data.get('R', None)
                except Exception:
                    intensity = None

                # Laser
                master_data = self.master_diode.read_laser(device_read_time=False)
                amplif_data = self.amplifier_diode.read_laser(device_read_time=False)

                record = {
                    "time_s":              t_current,
                    "wavelength_m":        wavelength,
                    "lif_intensity_R":     intensity,
                    "master_current_A":    master_data["current_A"],
                    "master_temperature_C": master_data["temperature_C"],
                    "amplif_current_A":    amplif_data["current_A"],
                    "amplif_temperature_C": amplif_data["temperature_C"],
                }
                drift_records.append(record)

                if not silent:
                    wl_nm = wavelength * 1e9 if wavelength else 0
                    print(f"  t={t_current:6.1f} s | "
                        f"λ={wl_nm:.5f} nm | "
                        f"R={intensity} | "
                        f"T_master={master_data['temperature_C']:.4f} °C | "
                        f"T_amplif={amplif_data['temperature_C']:.4f} °C")

                time.sleep(interval_s)

        except KeyboardInterrupt:
            print(f"\n{self.YELLOW}Drift monitor stopped by user "
                f"after {time.perf_counter()-t_start:.1f} s.{self.RESET}")

        df = pd.DataFrame(drift_records).set_index("time_s")
        print(f"{self.GREEN}Done. {len(df)} measurements over "
            f"{df.index[-1]:.1f} s{self.RESET}")

        # if plot:
        #     lp.plot_drift_monitor(df, save_path=save_path)

        return df
    

    def _plot_drift_monitor(self, df: pd.DataFrame, save_path: str = None):
        '''Plot drift monitor results: wavelength, drift, temperature and current over time.'''
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        fig = plt.figure(figsize=(14, 12))
        gs  = GridSpec(4, 2, figure=fig, hspace=0.45, wspace=0.35)

        ax_wl_abs  = fig.add_subplot(gs[0, :])   # volle Breite – absolute Wellenlänge
        ax_wl_drift = fig.add_subplot(gs[1, :])  # volle Breite – Drift in pm
        ax_temp_m  = fig.add_subplot(gs[2, 0])
        ax_temp_a  = fig.add_subplot(gs[2, 1])
        ax_curr_m  = fig.add_subplot(gs[3, 0])
        ax_curr_a  = fig.add_subplot(gs[3, 1])

        time_s     = df.index
        wl_nm      = df['wavelength_m'] * 1e9
        wl_pm_drift = (wl_nm - wl_nm.mean()) * 1e3
        drift_range = wl_pm_drift.max() - wl_pm_drift.min()
        drift_std   = wl_pm_drift.std()

        # --- absolute Wellenlänge ---
        ax_wl_abs.plot(time_s, wl_nm,
                    color='tab:blue', linewidth=1.2, label='λ [nm]')
        ax_wl_abs.set_ylabel("Wellenlänge [nm]", fontsize=10)
        ax_wl_abs.set_xlabel("Zeit [s]", fontsize=10)
        ax_wl_abs.set_title("Absolute Wellenlänge", fontsize=11)
        ax_wl_abs.grid(True, linestyle='--', alpha=0.4)
        ax_wl_abs.legend(fontsize=9)

        # --- Drift in pm ---
        ax_wl_drift.plot(time_s, wl_pm_drift,
                        color='tab:red', linewidth=1.2, label='Drift [pm]')
        ax_wl_drift.axhline(0, color='black', linewidth=0.8, linestyle=':')

        # Zeeman-Aufspaltung als Referenz einzeichnen
        ax_wl_drift.axhline( 2.08, color='gray', linewidth=0.8,
                            linestyle='--', alpha=0.6, label='±Δλ_Z = 2.08 pm')
        ax_wl_drift.axhline(-2.08, color='gray', linewidth=0.8,
                            linestyle='--', alpha=0.6)

        ax_wl_drift.set_ylabel("Drift vom Mittelwert [pm]", fontsize=10)
        ax_wl_drift.set_xlabel("Zeit [s]", fontsize=10)
        ax_wl_drift.set_title("Wellenlängen-Drift", fontsize=11)
        ax_wl_drift.grid(True, linestyle='--', alpha=0.4)
        ax_wl_drift.legend(fontsize=9)
        ax_wl_drift.text(
            0.99, 0.95,
            f"Drift range: {drift_range:.2f} pm\n"
            f"Drift std:   {drift_std:.2f} pm\n"
            f"Zeeman Δλ:   2.08 pm",
            transform=ax_wl_drift.transAxes,
            fontsize=9, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

        # --- Master Temperatur ---
        t_master = df['master_temperature_C']
        t_m_range = (t_master.max() - t_master.min()) * 1e3
        ax_temp_m.plot(time_s, t_master,
                    color='steelblue', linewidth=1.2)
        ax_temp_m.set_title("Master Temperatur", fontsize=10)
        ax_temp_m.set_xlabel("Zeit [s]", fontsize=9)
        ax_temp_m.set_ylabel("Temperatur [°C]", fontsize=9)
        ax_temp_m.grid(True, linestyle='--', alpha=0.4)
        ax_temp_m.text(
            0.97, 0.97, f"Δ = {t_m_range:.1f} mK",
            transform=ax_temp_m.transAxes,
            fontsize=9, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

        # --- Amplifier Temperatur ---
        t_amplif  = df['amplif_temperature_C']
        t_a_range = (t_amplif.max() - t_amplif.min()) * 1e3
        ax_temp_a.plot(time_s, t_amplif,
                    color='tomato', linewidth=1.2)
        ax_temp_a.set_title("Amplifier Temperatur", fontsize=10)
        ax_temp_a.set_xlabel("Zeit [s]", fontsize=9)
        ax_temp_a.set_ylabel("Temperatur [°C]", fontsize=9)
        ax_temp_a.grid(True, linestyle='--', alpha=0.4)
        ax_temp_a.text(
            0.97, 0.97, f"Δ = {t_a_range:.1f} mK",
            transform=ax_temp_a.transAxes,
            fontsize=9, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

        # --- Master Strom ---
        ax_curr_m.plot(time_s, df['master_current_A'] * 1e3,
                    color='steelblue', linewidth=1.2)
        ax_curr_m.set_title("Master Strom", fontsize=10)
        ax_curr_m.set_xlabel("Zeit [s]", fontsize=9)
        ax_curr_m.set_ylabel("Strom [mA]", fontsize=9)
        ax_curr_m.grid(True, linestyle='--', alpha=0.4)

        # --- Amplifier Strom ---
        ax_curr_a.plot(time_s, df['amplif_current_A'] * 1e3,
                    color='tomato', linewidth=1.2)
        ax_curr_a.set_title("Amplifier Strom", fontsize=10)
        ax_curr_a.set_xlabel("Zeit [s]", fontsize=9)
        ax_curr_a.set_ylabel("Strom [mA]", fontsize=9)
        ax_curr_a.grid(True, linestyle='--', alpha=0.4)

        fig.suptitle(
            f"Drift Monitor – {df.index[-1]:.0f} s  |  "
            f"{len(df)} Messungen  |  "
            f"Interval: {df.index[1]-df.index[0]:.1f} s",
            fontsize=13, fontweight='bold'
        )
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"{self.GREEN}Plot gespeichert: {save_path}{self.RESET}")

        plt.show(block=True)
        # plt.pause(0.5)
        # plt.close(fig)



    def test_piezo_resolution(self,
                            v_center: float = 0.0,
                            v_range: float = 5.0,
                            v_steps: list = None,
                            n_scans: int = 3,
                            n_wlm: int = 5,
                            silent: bool = True,
                            plot: bool = True,
                            save_path: str = None,
                            ):
        '''
        Tests piezo resolution and reproducibility.

        Two tests:
        A) Resolution test: smallest voltage step still visible in wavelength
            → determines effective resolution of piezo + WLM combined
        B) Reproducibility test: n_scans forward + backward scans
            → quantifies hysteresis and scan-to-scan reproducibility

        Parameters
        ----------
        v_center : center piezo voltage [V]
        v_range  : scan range ± v_range around v_center [V]
        v_steps  : list of step sizes to test for resolution [V]
                default: [1.0, 0.5, 0.1, 0.05, 0.01]
        n_scans  : number of repeated scans for reproducibility test
        n_wlm    : wavelength measurements per point
        '''
        if v_steps is None:
            v_steps = [1.0, 0.5, 0.1, 0.05, 0.01]

        print(f"\n{self.CYAN}{'='*60}")
        print(f"  Piezo Resolution & Reproducibility Test")
        print(f"  v_center={v_center} V, v_range=±{v_range} V")
        print(f"  v_steps={v_steps} V")
        print(f"  n_scans={n_scans}, n_wlm={n_wlm}")
        print(f"{'='*60}{self.RESET}\n")

        results = {
            "resolution": {},    # {v_step: DataFrame}
            "reproducibility": []  # list of DataFrames
        }

        # ================================================================
        # TEST A: Auflösung
        # Für jeden Spannungsschritt: Piezo schrittweise setzen und
        # Wellenlänge messen. Kleinster Schritt bei dem WLM noch
        # eine Änderung sieht = effektive Auflösung
        # ================================================================
        print(f"{self.MAGENTA}--- Test A: Auflösung ---{self.RESET}")
        print(f"  Testet kleinste sichtbare Wellenlängenänderung pro Spannungsschritt\n")

        for v_step in v_steps:
            n_points = int(2 * v_range / v_step) + 1
            if n_points > 200:
                print(f"  {self.YELLOW}v_step={v_step} V: {n_points} Punkte – übersprungen "
                    f"(zu viele Punkte, v_range reduzieren){self.RESET}")
                continue

            print(f"  v_step = {v_step} V → {n_points} Punkte ...")
            v_list = [round(v_center - v_range + i * v_step, 6)
                    for i in range(n_points)]
            # Piezo-Limits prüfen
            v_min_limit = self.master_diode.piezo['limits']['min']
            v_max_limit = self.master_diode.piezo['limits']['max']
            v_list = [v for v in v_list
                    if v_min_limit <= v <= v_max_limit]

            records = []
            t0 = time.perf_counter()
            for v in v_list:
                self.master_diode.set_piezo(value=v, unit="V", silent=True)
                wls = [self.wlm.read(silent=silent)['wavelength']
                    for _ in range(n_wlm)]
                wl_mean = sum(wls) / n_wlm
                wl_std  = float(np.std(wls)) if n_wlm > 2 else 0.0
                records.append({
                    'time_s':    time.perf_counter() - t0,
                    'piezo_V':   v,
                    'wl_mean_m': wl_mean,
                    'wl_std_m':  wl_std,
                })

            df_res = pd.DataFrame(records)

            # Auflösung berechnen
            wl_changes = np.abs(np.diff(df_res['wl_mean_m'].values))
            wl_noise   = df_res['wl_std_m'].mean()
            detectable = wl_changes > 3 * wl_noise   # SNR > 3

            tuning_rate = np.median(wl_changes[wl_changes > 0]) / v_step
            detectable_pct = detectable.sum() / len(detectable) * 100

            print(f"    Abstimmrate:        {tuning_rate*1e12:.3f} pm/V")
            print(f"    WLM Rauschen (std): {wl_noise*1e12:.3f} pm")
            print(f"    Erkennbar (SNR>3):  {detectable_pct:.0f}% der Schritte")
            if detectable_pct > 80:
                print(f"    {self.GREEN}→ Schritt gut auflösbar{self.RESET}")
            elif detectable_pct > 40:
                print(f"    {self.YELLOW}→ Schritt grenzwertig{self.RESET}")
            else:
                print(f"    {self.RED}→ Schritt nicht auflösbar{self.RESET}")

            results["resolution"][v_step] = df_res

        # ================================================================
        # TEST B: Reproduzierbarkeit
        # n_scans Hin- und Rückweg über v_range
        # Quantifiziert Hysterese und Scan-zu-Scan Reproduzierbarkeit
        # ================================================================
        print(f"\n{self.MAGENTA}--- Test B: Reproduzierbarkeit ---{self.RESET}")
        print(f"  {n_scans} Scans hin und zurück über ±{v_range} V\n")

        v_step_repro = v_steps[0]   # größter Schritt für Reproduzierbarkeitstest
        v_forward  = [round(v_center - v_range + i * v_step_repro, 6)
                    for i in range(int(2 * v_range / v_step_repro) + 1)]
        v_backward = v_forward[::-1]
        v_forward  = [v for v in v_forward
                    if v_min_limit <= v <= v_max_limit]
        v_backward = [v for v in v_backward
                    if v_min_limit <= v <= v_max_limit]

        for scan_i in range(n_scans):
            print(f"  Scan {scan_i+1}/{n_scans} ...")
            t0 = time.perf_counter()
            records_fwd = []
            records_bwd = []

            # Vorwärts
            for v in v_forward:
                self.master_diode.set_piezo(value=v, unit="V", silent=True)
                wls = [self.wlm.read(silent=silent)['wavelength']
                    for _ in range(n_wlm)]
                records_fwd.append({
                    'time_s':    time.perf_counter() - t0,
                    'piezo_V':   v,
                    'wl_mean_m': sum(wls) / n_wlm,
                    'wl_std_m':  float(np.std(wls)) if n_wlm > 2 else 0.0,
                    'direction': 'forward',
                    'scan_n':    scan_i + 1,
                })

            # Rückwärts
            for v in v_backward:
                self.master_diode.set_piezo(value=v, unit="V", silent=True)
                wls = [self.wlm.read(silent=silent)['wavelength']
                    for _ in range(n_wlm)]
                records_bwd.append({
                    'time_s':    time.perf_counter() - t0,
                    'piezo_V':   v,
                    'wl_mean_m': sum(wls) / n_wlm,
                    'wl_std_m':  float(np.std(wls)) if n_wlm > 2 else 0.0,
                    'direction': 'backward',
                    'scan_n':    scan_i + 1,
                })

            df_scan = pd.DataFrame(records_fwd + records_bwd)

            # Hysterese berechnen
            df_fwd = df_scan[df_scan['direction'] == 'forward'].set_index('piezo_V')
            df_bwd = df_scan[df_scan['direction'] == 'backward'].set_index('piezo_V')
            common = df_fwd.index.intersection(df_bwd.index)
            if len(common) > 0:
                hysteresis = np.abs(
                    df_fwd.loc[common, 'wl_mean_m'].values -
                    df_bwd.loc[common, 'wl_mean_m'].values
                )
                print(f"    Hysterese: mean={hysteresis.mean()*1e12:.3f} pm, "
                    f"max={hysteresis.max()*1e12:.3f} pm")

            results["reproducibility"].append(df_scan)

        # Scan-zu-Scan Reproduzierbarkeit
        if n_scans > 1:
            print(f"\n  Scan-zu-Scan Reproduzierbarkeit:")
            # gemeinsame Piezo-Positionen über alle Scans
            all_fwd = [df[df['direction'] == 'forward'].set_index('piezo_V')
                    for df in results["reproducibility"]]
            common_v = all_fwd[0].index
            for df in all_fwd[1:]:
                common_v = common_v.intersection(df.index)

            if len(common_v) > 0:
                wl_matrix = np.array([
                    df.loc[common_v, 'wl_mean_m'].values
                    for df in all_fwd
                ])
                scan_std = np.std(wl_matrix, axis=0)
                print(f"    std über Scans: mean={scan_std.mean()*1e12:.3f} pm, "
                    f"max={scan_std.max()*1e12:.3f} pm")

        print(f"\n{self.GREEN}Test abgeschlossen.{self.RESET}")

        if plot:
            lp.plot_piezo_resolution(results, v_steps, save_path=save_path)

        return results
    
    def _plot_piezo_resolution(self, results: dict,
                                v_steps: list,
                                save_path: str = None):
        '''Plot results of test_piezo_resolution().'''
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
        import matplotlib.cm as cm

        n_res   = len(results["resolution"])
        n_scans = len(results["reproducibility"])

        fig = plt.figure(figsize=(14, 5 + 4 * n_res))
        gs  = GridSpec(n_res + 1, 2, figure=fig,
                    hspace=0.5, wspace=0.35)

        # --- Test A: Auflösung – eine Zeile pro v_step ---
        for row, (v_step, df) in enumerate(results["resolution"].items()):
            ax_wl  = fig.add_subplot(gs[row, 0])
            ax_diff = fig.add_subplot(gs[row, 1])

            wl_nm = df['wl_mean_m'] * 1e9
            err_nm = df['wl_std_m'] * 1e9

            # Wellenlänge vs. Piezo
            ax_wl.errorbar(df['piezo_V'], wl_nm, yerr=err_nm,
                        fmt='o-', color='tab:blue',
                        markersize=3, linewidth=1.0,
                        capsize=2, elinewidth=0.6)
            ax_wl.set_title(f"Auflösung: v_step = {v_step} V", fontsize=9)
            ax_wl.set_xlabel("Piezo [V]", fontsize=8)
            ax_wl.set_ylabel("λ [nm]", fontsize=8)
            ax_wl.grid(True, linestyle='--', alpha=0.4)

            # Differenz zwischen aufeinanderfolgenden Punkten
            wl_diff_pm = np.diff(wl_nm.values) * 1e3
            noise_pm   = err_nm.mean() * 1e3
            ax_diff.bar(range(len(wl_diff_pm)), wl_diff_pm,
                        color=['tab:green' if abs(d) > 3 * noise_pm
                            else 'tab:red'
                            for d in wl_diff_pm],
                        width=0.8, alpha=0.8)
            ax_diff.axhline(3 * noise_pm,  color='gray',
                            linewidth=0.8, linestyle='--',
                            label=f'3σ = {3*noise_pm:.3f} pm')
            ax_diff.axhline(-3 * noise_pm, color='gray',
                            linewidth=0.8, linestyle='--')
            ax_diff.axhline(0, color='black', linewidth=0.5)
            ax_diff.set_title(f"Δλ pro Schritt (grün = auflösbar)", fontsize=9)
            ax_diff.set_xlabel("Schritt-Index", fontsize=8)
            ax_diff.set_ylabel("Δλ [pm]", fontsize=8)
            ax_diff.legend(fontsize=7)
            ax_diff.grid(True, linestyle='--', alpha=0.4)

        # --- Test B: Reproduzierbarkeit ---
        ax_repro  = fig.add_subplot(gs[n_res, 0])
        ax_hyst   = fig.add_subplot(gs[n_res, 1])

        colors = cm.tab10(np.linspace(0, 1, n_scans))

        for i, df_scan in enumerate(results["reproducibility"]):
            df_fwd = df_scan[df_scan['direction'] == 'forward']
            df_bwd = df_scan[df_scan['direction'] == 'backward']

            ax_repro.plot(df_fwd['piezo_V'], df_fwd['wl_mean_m'] * 1e9,
                        'o-', color=colors[i], markersize=3,
                        linewidth=1.0, label=f'Scan {i+1} →')
            ax_repro.plot(df_bwd['piezo_V'], df_bwd['wl_mean_m'] * 1e9,
                        's--', color=colors[i], markersize=3,
                        linewidth=0.8, alpha=0.6, label=f'Scan {i+1} ←')

            # Hysterese
            df_f = df_fwd.set_index('piezo_V')
            df_b = df_bwd.set_index('piezo_V')
            common = df_f.index.intersection(df_b.index)
            if len(common) > 0:
                hyst_pm = (df_f.loc[common, 'wl_mean_m'].values -
                        df_b.loc[common, 'wl_mean_m'].values) * 1e12
                ax_hyst.plot(common, hyst_pm,
                            'o-', color=colors[i], markersize=3,
                            linewidth=1.0, label=f'Scan {i+1}')

        ax_repro.set_title("Reproduzierbarkeit: Hin- und Rückweg", fontsize=10)
        ax_repro.set_xlabel("Piezo [V]", fontsize=9)
        ax_repro.set_ylabel("λ [nm]", fontsize=9)
        ax_repro.legend(fontsize=7, ncol=2)
        ax_repro.grid(True, linestyle='--', alpha=0.4)

        ax_hyst.axhline(0, color='black', linewidth=0.8, linestyle='-')
        ax_hyst.set_title("Hysterese (Vorwärts − Rückwärts) [pm]", fontsize=10)
        ax_hyst.set_xlabel("Piezo [V]", fontsize=9)
        ax_hyst.set_ylabel("Δλ [pm]", fontsize=9)
        ax_hyst.legend(fontsize=7)
        ax_hyst.grid(True, linestyle='--', alpha=0.4)

        fig.suptitle("Piezo Auflösung & Reproduzierbarkeit",
                    fontsize=13, fontweight='bold')
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"{self.GREEN}Plot gespeichert: {save_path}{self.RESET}")

        plt.show(block=True)
        # plt.pause(0.5)
        # plt.close(fig)



    def measure_tuning_rates(self,
                            current_min_mA: float = 30.0,
                            current_max_mA: float = 200.0,
                            current_step_mA: float = 10.0,
                            piezo_points: list = None,
                            n_wlm: int = 3,
                            silent: bool = False,
                            plot: bool = True,
                            save_path: str = None,
                            ) -> pd.DataFrame:
        '''
        Measures wavelength as function of master current and piezo voltage.
        Determines:
        - Current tuning rate [pm/mA] and [nm/A]
        - Piezo tuning rate [pm/V] at each current step
        - Target current for a given wavelength (e.g. 667.91 nm)

        Parameters
        ----------
        current_min_mA  : start current [mA]
        current_max_mA  : stop current [mA]
        current_step_mA : step size [mA]
        piezo_points    : piezo voltages to measure at each current step
                        default: [-6, 0, 6] V  – fast, 3 points per step
        n_wlm           : WLM measurements to average per point
        '''
        if piezo_points is None:
            piezo_points = [-6.0, 0.0, 6.0]

        current_limits = self.master_diode.current['limits']
        i_min_A = current_limits['min']
        i_max_A = current_limits['max']

        # Stromliste aufbauen
        n_steps   = int((current_max_mA - current_min_mA) / current_step_mA) + 1
        i_list_mA = [round(current_min_mA + i * current_step_mA, 3)
                    for i in range(n_steps)]
        i_list_mA = [i for i in i_list_mA
                    if i_min_A * 1e3 <= i <= i_max_A * 1e3]

        print(f"\n{self.CYAN}{'='*60}")
        print(f"  measure_tuning_rates()")
        print(f"  Strom: {current_min_mA} – {current_max_mA} mA, "
            f"Schritt: {current_step_mA} mA ({len(i_list_mA)} Punkte)")
        print(f"  Piezo: {piezo_points} V ({len(piezo_points)} Punkte pro Strom)")
        print(f"  Gesamt: {len(i_list_mA) * len(piezo_points)} Messungen")
        print(f"{'='*60}{self.RESET}\n")

        records = []
        t0 = time.perf_counter()

        for i_idx, i_mA in enumerate(i_list_mA):
            i_A = i_mA * 1e-3
            self.master_diode.set_current(i_A, unit="A", silent=True)
            time.sleep(0.5)   # kurz warten bis Strom stabil

            wl_at_piezo = []

            for v in piezo_points:
                self.master_diode.set_piezo(value=v, unit="V", silent=True)

                wls = [self.wlm.read(silent=True)['wavelength']
                    for _ in range(n_wlm)]
                wl_mean = sum(wls) / n_wlm
                wl_std  = float(np.std(wls)) if n_wlm > 2 else 0.0
                wl_at_piezo.append(wl_mean)

                records.append({
                    'time_s':        time.perf_counter() - t0,
                    'current_mA':    i_mA,
                    'piezo_V':       v,
                    'wl_mean_m':     wl_mean,
                    'wl_std_m':      wl_std,
                })

                if not silent:
                    print(f"  I={i_mA:6.1f} mA, V={v:6.1f} V  →  "
                        f"λ={wl_mean*1e9:.6f} nm")

            # Piezo-Abstimmrate bei diesem Strom
            if len(piezo_points) >= 2:
                dv  = piezo_points[-1] - piezo_points[0]
                dwl = wl_at_piezo[-1] - wl_at_piezo[0]
                piezo_rate_pm_per_V = dwl / dv * 1e12 if dv != 0 else np.nan
            else:
                piezo_rate_pm_per_V = np.nan

            wl_mid = wl_at_piezo[len(wl_at_piezo) // 2]
            print(f"  I={i_mA:6.1f} mA  →  "
                f"λ={wl_mid*1e9:.5f} nm  |  "
                f"Piezo-Rate={piezo_rate_pm_per_V:.3f} pm/V")

        # Piezo zurück auf Mitte
        self.master_diode.set_piezo(value=0.0, unit="V", silent=True)

        df = pd.DataFrame(records)

        # --- Auswertung ---
        print(f"\n{self.CYAN}--- Auswertung ---{self.RESET}")

        # Mittelwert pro Strom (über Piezo-Punkte gemittelt)
        df_mean = df.groupby('current_mA')['wl_mean_m'].mean().reset_index()
        df_mean.columns = ['current_mA', 'wl_mean_m']

        # Strom-Abstimmrate: lineare Regression über alle Punkte
        if len(df_mean) >= 2:
            coeffs = np.polyfit(df_mean['current_mA'].values,
                                df_mean['wl_mean_m'].values, 1)
            rate_m_per_mA = coeffs[0]
            rate_pm_per_mA = rate_m_per_mA * 1e12
            rate_nm_per_A  = rate_m_per_mA * 1e9 / 1e-3

            print(f"  Strom-Abstimmrate:  {rate_pm_per_mA:.3f} pm/mA"
                f"  =  {rate_nm_per_A:.4f} nm/A")
            print(f"  Vorzeichen: "
                f"{'positiv (↑I → ↑λ)' if rate_pm_per_mA > 0 else 'negativ (↑I → ↓λ)'}")

            # Zielstrom für 667.91 nm extrapolieren
            target_m   = 667.91e-9
            i_target_mA = (target_m - coeffs[1]) / coeffs[0]
            print(f"\n  Zielwellenlänge:    667.91 nm")
            print(f"  Benötigter Strom:   {i_target_mA:.1f} mA")
            if i_min_A * 1e3 <= i_target_mA <= i_max_A * 1e3:
                print(f"  {self.GREEN}→ innerhalb der Stromgrenzen "
                    f"({i_min_A*1e3:.0f}–{i_max_A*1e3:.0f} mA){self.RESET}")
            else:
                print(f"  {self.RED}→ außerhalb der Stromgrenzen! "
                    f"Wellenlänge möglicherweise nicht erreichbar.{self.RESET}")

            # Piezo-Abstimmrate Mittelwert
            df_piezo = df.groupby('current_mA').apply(
                lambda g: (g['wl_mean_m'].iloc[-1] - g['wl_mean_m'].iloc[0]) /
                        (g['piezo_V'].iloc[-1]   - g['piezo_V'].iloc[0])
                        if len(g) >= 2 else np.nan,
                include_groups=False
            ).reset_index()
            df_piezo.columns = ['current_mA', 'piezo_rate_m_per_V']
            piezo_rate_mean = df_piezo['piezo_rate_m_per_V'].mean() * 1e12

            print(f"\n  Piezo-Abstimmrate:  {piezo_rate_mean:.3f} pm/V "
                f"(Mittelwert über alle Stromschritte)")
            print(f"  → tuning_rate_current = {rate_m_per_mA*1e3:.4e} m/A "
                f"für set_wavelength()")
            print(f"  → tuning_rate_piezo   = {piezo_rate_mean*1e-12:.4e} m/V "
                f"für set_wavelength()")

        print(f"\n{self.GREEN}measure_tuning_rates() finished. "
            f"{len(df)} Messungen in {time.perf_counter()-t0:.1f} s{self.RESET}")

        if plot:
            lp.plot_tuning_rates(df, df_mean, save_path=save_path)

        return df


    def _plot_tuning_rates(self,
                            df: pd.DataFrame,
                            df_mean: pd.DataFrame,
                            save_path: str = None):
        '''Plot results of measure_tuning_rates().'''
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
        import matplotlib.cm as cm

        fig = plt.figure(figsize=(14, 9))
        gs  = GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

        ax_main  = fig.add_subplot(gs[0, :])   # λ vs. Strom – volle Breite
        ax_piezo = fig.add_subplot(gs[1, 0])   # Piezo-Rate vs. Strom
        ax_resid = fig.add_subplot(gs[1, 1])   # Residuen vom linearen Fit

        # Farben für Piezo-Punkte
        colors = cm.coolwarm(np.linspace(0, 1, len(df['piezo_V'].unique())))
        piezo_vals = sorted(df['piezo_V'].unique())

        # --- Hauptplot: λ vs. Strom ---
        for col, v in zip(colors, piezo_vals):
            df_v = df[df['piezo_V'] == v]
            ax_main.plot(df_v['current_mA'],
                        df_v['wl_mean_m'] * 1e9,
                        'o-', color=col, markersize=4,
                        linewidth=1.0, alpha=0.8,
                        label=f'Piezo = {v:.0f} V')

        # Mittelwert + linearer Fit
        ax_main.plot(df_mean['current_mA'],
                    df_mean['wl_mean_m'] * 1e9,
                    's--', color='black', markersize=5,
                    linewidth=1.5, label='Mittelwert')

        if len(df_mean) >= 2:
            coeffs = np.polyfit(df_mean['current_mA'].values,
                                df_mean['wl_mean_m'].values, 1)
            i_fit  = np.linspace(df_mean['current_mA'].min(),
                                df_mean['current_mA'].max(), 100)
            wl_fit = np.polyval(coeffs, i_fit) * 1e9
            ax_main.plot(i_fit, wl_fit,
                        '-', color='tab:red', linewidth=1.5,
                        alpha=0.7, label='Linearer Fit')

            rate_pm_per_mA = coeffs[0] * 1e12
            ax_main.text(
                0.97, 0.05,
                f"Abstimmrate: {rate_pm_per_mA:.3f} pm/mA\n"
                f"             {rate_pm_per_mA*1e3/1e9*1e9:.4f} nm/A",
                transform=ax_main.transAxes,
                fontsize=9, ha='right', va='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.85)
            )

            # Referenzlinie 667.91 nm
            ax_main.axhline(667.91, color='gray', linewidth=0.8,
                            linestyle=':', label='667.91 nm (Ziel)')

        ax_main.set_xlabel("Master-Strom [mA]", fontsize=11)
        ax_main.set_ylabel("Wellenlänge [nm]", fontsize=11)
        ax_main.set_title("Abstimmkurve: λ vs. Master-Strom", fontsize=11)
        ax_main.legend(fontsize=8, loc='upper left')
        ax_main.grid(True, linestyle='--', alpha=0.4)

        # --- Piezo-Rate vs. Strom ---
        piezo_rates = []
        for i_mA, grp in df.groupby('current_mA'):
            if len(grp) >= 2:
                dv  = grp['piezo_V'].iloc[-1] - grp['piezo_V'].iloc[0]
                dwl = grp['wl_mean_m'].iloc[-1] - grp['wl_mean_m'].iloc[0]
                piezo_rates.append({
                    'current_mA': i_mA,
                    'rate_pm_per_V': dwl / dv * 1e12 if dv != 0 else np.nan
                })

        if piezo_rates:
            df_pr = pd.DataFrame(piezo_rates)
            ax_piezo.plot(df_pr['current_mA'], df_pr['rate_pm_per_V'],
                        'o-', color='tab:blue', markersize=5, linewidth=1.2)
            ax_piezo.axhline(df_pr['rate_pm_per_V'].mean(),
                            color='tab:red', linewidth=0.8, linestyle='--',
                            label=f"Mittel: {df_pr['rate_pm_per_V'].mean():.3f} pm/V")
            ax_piezo.set_xlabel("Master-Strom [mA]", fontsize=10)
            ax_piezo.set_ylabel("Piezo-Rate [pm/V]", fontsize=10)
            ax_piezo.set_title("Piezo-Abstimmrate vs. Strom", fontsize=10)
            ax_piezo.legend(fontsize=8)
            ax_piezo.grid(True, linestyle='--', alpha=0.4)

        # --- Residuen ---
        if len(df_mean) >= 2:
            wl_fit_at_points = np.polyval(coeffs, df_mean['current_mA'].values)
            residuals_pm = (df_mean['wl_mean_m'].values - wl_fit_at_points) * 1e12
            ax_resid.bar(df_mean['current_mA'].values, residuals_pm,
                        width=current_step * 0.6
                        if (current_step := df_mean['current_mA'].diff().median()) > 0
                        else 1.0,
                        color='tab:blue', alpha=0.7)
            ax_resid.axhline(0, color='black', linewidth=0.8)
            ax_resid.set_xlabel("Master-Strom [mA]", fontsize=10)
            ax_resid.set_ylabel("Residuen [pm]", fontsize=10)
            ax_resid.set_title("Residuen vom linearen Fit", fontsize=10)
            ax_resid.grid(True, linestyle='--', alpha=0.4)

        fig.suptitle("Abstimmraten-Messung Master-Laser",
                    fontsize=13, fontweight='bold')
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"{self.GREEN}Plot gespeichert: {save_path}{self.RESET}")

        plt.show(block=True)
        # plt.pause(0.5)
        # plt.close(fig)


if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n {style.MAGENTA}========= lif.py ========={style.RESET}")
    # print(f"{data_path=}")
    # print(f"{current_file=}")
    # print(f"{project_root=}")


    laser_warmup_s = 20     # Wartezeit nach laser_on() in Sekunden zum Temperieren

    r_man = LIFManager()

    print("\n--- read_state() Test ---")
    readout = r_man.read_state()
    for key, value in readout.items(): 
        print(f"  {key}: {value}")


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


    def test_laser():
        r_man.laser_on()
        time.sleep(laser_warmup_s)
        print(f"    Waiting {laser_warmup_s} sec for laser warmup")
        readout = r_man.read_state()
        for key, value in readout.items(): 
            print(f"  {key}: {value}")
        r_man.laser_off()

    # test_laser()


    def test_scan_piezo():
        try: 
            r_man.laser_on()
            time.sleep(laser_warmup_s)
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            df = r_man.scan_piezo(
                v_step=3,
                v_unit="[V]",
                n_wlm=5,
                zigzag=True,
            )
        finally: 
            r_man.laser_off()
        
    # test_scan_piezo()


    def SETTLING_TEST(): 
        try:
            r_man.laser_on()
            time.sleep(laser_warmup_s)
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            results = r_man.measure_laser_settling(
                n_measurements=30,
                sleep=0.1,
                plot=True, 
                save_path="/home/erikh/Schreibtisch/Studium/Nextcloud Manz/laser_settling/laser_settling17_n=30_half-range_warmup=0.png"
            )
        finally:
            r_man.laser_off()
    
    # SETTLING_TEST()


    def SCAN_AND_SETTLING_TEST():
        try:
            r_man.laser_on()
            time.sleep(laser_warmup_s)
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            df = r_man.scan_piezo(
                v_step=3,
                v_unit="[V]",
                n_wlm=5,
                zigzag=True,
                plot=True,
                save_path="/home/erikh/Schreibtisch/Studium/Nextcloud Manz/scan_piezo/scan_piezo1.png"
            )
            results = r_man.measure_laser_settling(
                n_measurements=20,
                sleep=0.1,
                plot=True,
                save_path="/home/erikh/Schreibtisch/Studium/Nextcloud Manz/laser_settling/laser_settling11_n=20_worst-case_warmup=0.png"
            )
        finally:
            r_man.laser_off()
            
    # SCAN_AND_SETTLING_TEST()


    def WARMUP_TEST(): 
        try: 
            r_man.laser_on()
            # no laser warmup time!
            results = r_man.measure_laser_warmup(
                n_measurements=20, 
                sleep=0.1,
                plot=True, 
                save_path=None # "/home/erikh/Schreibtisch/Studium/Nextcloud Manz/laser_warmup/laser_warmup_4_n=20.png"
            )
        finally: 
            r_man.laser_off()

    # WARMUP_TEST()



    def LIF_SCAN(): 
        try: 
            r_man.laser_on()
            r_man.aom_on(frequency_Hz=1000.0, amplitude_V=1.0)
            time.sleep(laser_warmup_s)
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            df = r_man.scan_piezo(v_step=1, n_wlm=5)
        finally: 
            r_man.aom_off()
            r_man.laser_off()
        return df
    
    # df_lif = LIF_SCAN()
    # print(df_lif)


    def SET_WAVELENGTH_TEST():
        try: 
            r_man.laser_on()
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            time.sleep(laser_warmup_s)

            reached = r_man.set_wavelength(
                target_wavelength_m = 667.91e-9, 
                tolerance_pm        = 1.0, 
                coarse_tolerance_pm = 100.0, 
                n_wlm               = 5,
                silent              = False, 
            )
            if reached: 
                print(f"\n Zielwellenlänge erreicht - bereit für Messung!")
            else: 
                print(f"Zielwellenlänge nicht erreicht - prüfe Strom und Piezo!")
        finally: 
            r_man.laser_off()

    # SET_WAVELENGTH_TEST()



    def DRIFT_MONITOR_TEST():
        try:
            r_man.laser_on()
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            time.sleep(laser_warmup_s)

            df_drift = r_man.drift_monitor(
                duration_s = 60,     # Zeit in Sekunden
                interval_s = 5,      # alle 5 Sekunden --> tatsächlich ca. 7,75 sek
                plot       = True,
                save_path  = "/home/erikh/Schreibtisch/Studium/Nextcloud Manz/drift_monitor/drift-monitor_4_20min.png",
                silent     = False,
            )
        finally:
            r_man.laser_off()

    # DRIFT_MONITOR_TEST()
    


    def RESOLUTION_TEST():
        try:
            r_man.laser_on()
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            time.sleep(laser_warmup_s)

            results = r_man.test_piezo_resolution(
                v_center = 0.0,       # Mitte des Scans
                v_range  = 3.0,       # ±3 V
                v_steps  = [1.0, 0.5, 0.1, 0.05, 0.01],
                n_scans  = 3,
                n_wlm    = 5,
                plot     = True,
                save_path= "/home/erikh/Schreibtisch/Studium/Nextcloud Manz/resolution_test/piezo-resolution-test_1.png"
            )
        finally:
            r_man.laser_off()

    # RESOLUTION_TEST()


    def TUNING_RATE_TEST():
        try:
            r_man.laser_on()
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            time.sleep(laser_warmup_s)

            df_tuning = r_man.measure_tuning_rates(
                current_min_mA  = 50.0,
                current_max_mA  = 550.0,
                current_step_mA = 20.0,
                piezo_points    = [-6.0, -3.0, 0.0, 3.0, 6.0],
                n_wlm           = 3,
                plot            = True,
                save_path       = "/home/erikh/Schreibtisch/Studium/Nextcloud Manz/tuning_rates/tuning-rates_2_50-550mA.png"
            )
        finally:
            r_man.laser_off()

    # TUNING_RATE_TEST()


    def TEST_MASTER_DIODE_CURRENT():
        try: 
            r_man.laser_on()
            print(f"    Waiting {laser_warmup_s} sec for laser warmup")
            time.sleep(laser_warmup_s)

            for I_mA in [50, 100, 200, 300, 400]:
                r_man.master_diode.set_current(I_mA * 1e-3, "A", silent=False)
                time.sleep(2)
                i_set  = r_man.master_diode.read_setcurrent()
                i_act  = r_man.master_diode.read_current()
                wl     = r_man.wlm.read()['wavelength']
                print(f"I_set={i_set}, I_act={i_act}, λ={wl*1e9:.5f} nm")
        finally: 
            r_man.laser_off()

    # TEST_MASTER_DIODE_CURRENT()

    # r_man.master_diode.scan_laser_parameters(silent=False)
    
    
    def TEST_LASER_TEMPERATURE_SETTLING():
        try: 
            r_man.laser_on()
            r_man.master_diode.set_current(70.0, unit="mA", silent=True)
            r_man.master_diode.set_temperature(value=20, unit="C", silent=True)
            print(f"    Waiting 20 sec for laser warmup")
            time.sleep(20)

            r_man.measure_temperature_settling(
                n_measurements  = 300,
                plot            = True, 
                save_path       = "/home/erikh/Schreibtisch/Studium/Nextcloud Manz/verschiedenes/temperature_settling/temperature_settling_2.png"
            )
        finally: 
            r_man.laser_off()
    
    TEST_LASER_TEMPERATURE_SETTLING()


    # master_readout = r_man.master_diode.read_laser()
    # print(master_readout)
    # r_man.laser_on(silent=True)
    # r_man.laser_off(silent=True)

    

    r_man.disconnect_all()