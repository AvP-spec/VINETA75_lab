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
        def worker(index, label, method, kwargs):
            try:
                readout = method(**kwargs)
                task_results[index] = self._label_keys(readout, label)
                # data.update(labeled)
            except Exception as e:
                task_results[index] = {f"{label}_error": str(e)}
                # data[f"{label}_error"] = str(e)

        tasks = [
            (0, 'wlm', self.wlm.read, 
             {'silent': silent, 'device_read_time': device_read_time}),

            (1, 'master', self.master_diode.read_laser, 
             {'device_read_time': device_read_time}),

            (2, 'amplif', self.amplifier_diode.read_laser, 
             {'device_read_time': device_read_time})

            (3, 'lia', self.lia.read_signal, 
             {'silent': silent, 'device_read_time': device_read_time})

            (4, 'daq', self.daq.read_lif_signal, 
             {'silent': silent, 'device_read_time': device_read_time})
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
                   v_step:float=3, # piezo voltage step 
                   v_max:float=None, # max piezo voltage
                   v_min:float=None, # min piezo voltage
                   v_unit:str="[V]", # piezo voltage units 
                   n_wlm:int=5, # number of wavelength measurements
                   zigzag:bool=True,
                   # device_read_time=False,
                   silent: bool = True # only for wlm in current implementation
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

            wls = [s['wlm_wavelength'] for s in states]
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
        return df



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
                (v_min, v_max,  "min → max (worst case)"),
                (v_max, v_min,  "max → min (worst case reverse)"),
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
            self._plot_settling(all_results, scenarios, save_path=save_path)

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

        plt.show(block=False)
        plt.pause(1)
        plt.close(fig)




    def drift_monitor(self, duration_s=60, interval_s=5, silent=False):

        print(f"Starting Drift Monitor for {duration_s} s ...")

        drift_records = []
        t_start = time.perf_counter()

        n_steps = int(duration_s / interval_s)

        try: 
            for i in range(n_steps): 
                t_current = time.perf_counter() - t_start

                wlm_data = self.wlm.read(silent=True, device_read_time=True)
                wavelength = wlm_data['wavelength']

                lia_data = self.lia.read_signal(silent=True, device_read_time=True)
                intensity = lia_data['R']

                laser_data = self.laser.read_laser(device_read_time=False)

                record = {
                    "time_s": t_current, 
                    "wavelength_nm": wavelength, 
                    "lif_intensity_R": intensity, 
                    "laser_current_A": laser_data["current_A"], 
                    "laser_temp_C": laser_data["temperature_C"]
                }

                drift_records.append(record)

                if not silent: 
                    print(f"t = {t_current:.1f} s | $\lambda$ = {wavelength:.5f} nm | R = {intensity:.3e}")

                time.sleep(interval_s)

        except KeyboardInterrupt: 
            print("Drift monitor stopped by user.")

        df_drift = pd.DataFrame(drift_records)
        df_drift.set_index("time_s", inplace=True)

        return df_drift




if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    # print(f"{data_path=}")
    # print(f"{current_file=}")
    # print(f"{project_root=}")

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
        time.sleep(5)
        readout = r_man.read_state()
        for key, value in readout.items(): 
            print(f"  {key}: {value}")
        r_man.laser_off()

    # test_laser()


    def test_scan_piezo():
        try: 
            r_man.laser_on()
            time.sleep(5)
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
            time.sleep(5)
            results = r_man.measure_laser_settling(
                n_measurements=15,
                sleep=0.1,
                plot=True, 
                save_path="/home/erikh/Schreibtisch/Studium/Nextcloud Manz/laser_settling/laser_settling"
            )
        finally:
            r_man.laser_off()
    
    # SETTLING_TEST()


    def SCAN_AND_SETTLING_TEST():
        try:
            r_man.laser_on()
            time.sleep(5)
            df = r_man.scan_piezo(
                v_step=3,
                v_unit="[V]",
                n_wlm=5,
                zigzag=True,
            )
            results = r_man.measure_laser_settling(
                n_measurements=30,
                sleep=0.1,
                plot=True,
                save_path="/home/erikh/Schreibtisch/Studium/settling_test.png"
            )
        finally:
            r_man.laser_off()
            
    # SCAN_AND_SETTLING_TEST()


    def LIF_SCAN(): 
        try: 
            r_man.laser_on()
            r_man.aom_on(frequency_Hz=1000.0, amplitude_V=1.0)
            time.sleep(5)
            df = r_man.scan_piezo(v_step=1, n_wlm=5)
        finally: 
            r_man.aom_off()
            r_man.laser_off()
        return df
    
    # df_lif = LIF_SCAN()
    # print(df_lif)
   


    # master_readout = r_man.master_diode.read_laser()
    # print(master_readout)
    # r_man.laser_on(silent=True)
    # r_man.laser_off(silent=True)
    r_man.disconnect_all()