"""
Generic DAQ (Data Acquisition) class.
Reads the analog output of the Lock-In Amplifier via BNC connection.

To adapt for a specific device:
1. Set self.hwid to the device's hardware ID
2. Fill in the marked sections in each method
3. Adjust n_channels and channel configuration

NI devices typically use the nidaqmx Python library

--- not yet tested ---
"""

from base_device import BaseDevice
import time
import numpy as np
import pandas as pd
import os


class DAQ(BaseDevice):

    # ================================================================
    # DEVICE-SPECIFIC: fill in for your device
    # ================================================================
    CONNECTION_SETTINGS = {
        # Only relevant if using pyvisa (e.g. NI DAQ via VISA)
        # For nidaqmx library: leave empty, override connect()
        'read_termination':  '\n',      # → DEVICE-SPECIFIC
        'write_termination': '\n',      # → DEVICE-SPECIFIC
        'timeout':           5000,
    }

    def __init__(self,
                 n_channels: int = 1,
                 sample_rate_Hz: float = 1000.0,
                 v_range: tuple = (-10.0, 10.0),
                 ):
        """
        Parameters
        ----------
        n_channels    : number of analog input channels to read
        sample_rate_Hz: sampling rate in Hz
        v_range       : (v_min, v_max) input voltage range in V
        """
        super().__init__()
        # ================================================================
        # DEVICE-SPECIFIC: set hwid for your device
        # ================================================================
        self.hwid = None    # e.g. "VID:PID = 0x3923:0x7270" for NI USB-6001
                            # or device name for nidaqmx: "Dev1"  → DEVICE-SPECIFIC
        self.name = "DAQ"
        self.port = self.hwid

        self.n_channels     = n_channels
        self.sample_rate_Hz = sample_rate_Hz
        self.v_min          = v_range[0]
        self.v_max          = v_range[1]
        self.time_sleep     = 0.01

        # ================================================================
        # DEVICE-SPECIFIC: for nidaqmx, store task handle here
        # ================================================================
        self._task = None   # nidaqmx task object → DEVICE-SPECIFIC


    def connect(self, silent=True):
        """
        Override BaseDevice.connect() if using nidaqmx instead of pyvisa.
        ================================================================
        DEVICE-SPECIFIC: choose one of the two options below
        ================================================================

        Option A – pyvisa (if DAQ supports VISA):
            Use BaseDevice.connect() as-is (no override needed).

        Option B – nidaqmx (NI DAQ):
            import nidaqmx
            self._task = nidaqmx.Task()
            self._task.ai_channels.add_ai_voltage_chan(
                f"{self.hwid}/ai0",
                min_val=self.v_min,
                max_val=self.v_max
            )
            self._task.timing.cfg_samp_clk_timing(
                rate=self.sample_rate_Hz,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS
            )
            self._task.start()
        """
        # ================================================================
        # DEVICE-SPECIFIC: implement connection here
        # ================================================================
        print(f"{self.YELLOW}[{self.name}] connect() not yet implemented."
              f" Fill in DEVICE-SPECIFIC section.{self.RESET}")
        return self


    def after_connect(self, silent=True):
        print(f"{self.name} after_connect()")
        # ================================================================
        # DEVICE-SPECIFIC: add initialization here if needed
        # ================================================================
        return self


    # ----------------------------------------------------------------
    # Read functions
    # ----------------------------------------------------------------

    def read_single(self,
                    channel: int = 0,
                    n_samples: int = 100,
                    silent: bool = True,
                    device_read_time: bool = False,
                    ) -> dict:
        if self.connection is None and self._task is None: 
            return {
                "voltageV_":    np.nan,
                "std_V":        np.nan,
                "n_samples":    0,
                "channel":      channel,
            }
        """
        Read n_samples from one channel and return mean and std.
        Averaging reduces noise from the analog signal.

        Parameters
        ----------
        channel  : analog input channel index (0-based)
        n_samples: number of samples to average

        Returns
        -------
        dict with keys: voltage_V, std_V, n_samples, channel
        """
        t0 = time.perf_counter()

        # ================================================================
        # DEVICE-SPECIFIC: implement reading for your device
        # ================================================================
        # Option A – pyvisa:
        #   raw = self.connection.query(f"READ? {channel}")
        #   voltage = float(raw)
        #   samples = np.array([voltage])   # single read

        # Option B – nidaqmx:
        #   samples = np.array(self._task.read(number_of_samples_per_channel=n_samples))

        # Placeholder – returns NaN until implemented
        samples = np.full(n_samples, np.nan)   # → DEVICE-SPECIFIC: replace this
        # ================================================================

        dt = time.perf_counter() - t0
        result = {
            "voltage_V": float(np.nanmean(samples)),
            "std_V":     float(np.nanstd(samples)),
            "n_samples": n_samples,
            "channel":   channel,
        }
        if device_read_time:
            result.update({"time_s": t0, "duration_s": dt})
        if not silent:
            print(f"[{self.name}] ch{channel}: "
                  f"{result['voltage_V']:.6f} ± {result['std_V']:.6f} V")
        return result


    def read_all_channels(self,
                          n_samples: int = 100,
                          silent: bool = True,
                          device_read_time: bool = False,
                          ) -> dict:
        """
        Read all n_channels and return a flat dict.
        Used by LIFManager.read_state().
        """
        t0 = time.perf_counter()
        result = {}
        for ch in range(self.n_channels):
            data = self.read_single(channel=ch,
                                    n_samples=n_samples,
                                    silent=silent)
            result[f"ch{ch}_voltage_V"] = data["voltage_V"]
            result[f"ch{ch}_std_V"]     = data["std_V"]
        dt = time.perf_counter() - t0
        if device_read_time:
            result.update({"time_s": t0, "duration_s": dt})
        return result


    def read_lif_signal(self,
                        channel: int = 0,
                        n_samples: int = 100,
                        silent: bool = True,
                        device_read_time: bool = False,
                        ) -> dict:
        """
        Read the LIF signal from the Lock-In analog output.
        This is the main method called during scan_piezo().

        The Lock-In output voltage is proportional to the
        fluorescence signal R at 750.59 nm.

        Returns
        -------
        dict with keys: lif_signal_V, lif_std_V
        """
        data = self.read_single(channel=channel,
                                n_samples=n_samples,
                                silent=silent,
                                device_read_time=device_read_time)
        result = {
            "lif_signal_V": data["voltage_V"],
            "lif_std_V":    data["std_V"],
        }
        if device_read_time:
            result.update({k: data[k] for k in ("time_s", "duration_s")
                           if k in data})
        return result


    def monitor(self,
                channel: int = 0,
                n_measurements: int = 20,
                n_samples: int = 100,
                sleep: float = 0.1,
                silent: bool = False,
                ) -> pd.DataFrame:
        """
        Monitor the DAQ signal over time. Returns a DataFrame.
        Useful for checking signal stability before a scan.
        """
        records = []
        t0 = None
        for i in range(n_measurements):
            data = self.read_single(channel=channel,
                                    n_samples=n_samples,
                                    silent=True,
                                    device_read_time=True)
            if t0 is None:
                t0 = data["time_s"]
            data["time_s"] -= t0
            if not silent:
                print(f"[{self.name}] monitor {i+1}/{n_measurements}: "
                      f"{data['voltage_V']:.6f} ± {data['std_V']:.6f} V")
            records.append(data)
            time.sleep(sleep)

        return pd.DataFrame(records).set_index("time_s")


    def disconnect(self):
        # ================================================================
        # DEVICE-SPECIFIC: close task if using nidaqmx
        # ================================================================
        # if self._task is not None:
        #     self._task.stop()
        #     self._task.close()
        #     self._task = None
        return BaseDevice.disconnect(self)


# ================================================================
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== DAQ test ===")

    daq = DAQ(n_channels=1, sample_rate_Hz=1000, v_range=(-10, 10))
    daq.print_connections()

    # daq.connect()
    # print(daq.read_lif_signal(n_samples=100, silent=False))
    # print(daq.monitor(n_measurements=10))
    # daq.disconnect()