'''
scope_ni5170r.py
NI PXIe-5170R Oscilloscope driver class
Analogous structure to pilot_pz.py / BaseDevice pattern.

NI PXIe-5170R specs:
  - 8 channels, 250 MHz bandwidth
  - 14-bit resolution
  - 1 GS/s sample rate
  - Controlled via niscope (NI-SCOPE driver), NOT pyvisa

v01 - initial version
'''

import niscope
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys
import time
from pathlib import Path

##### import project related modules #####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.terminal_styler import TerminalColours
style = TerminalColours()


class ScopeNI5170R(TerminalColours):
    '''
    Driver class for NI PXIe-5170R oscilloscope.

    Usage:
        scope = ScopeNI5170R()
        scope.connect()
        waveforms = scope.read_waveform(channels=[0, 1])
        scope.disconnect()
    '''

    # Default acquisition settings – override per instance or subclass
    DEFAULT_SETTINGS = {
        "sample_rate":      250e6,   # [S/s]  250 MS/s
        "record_length":    10000,   # [samples]
        "ref_position":     50.0,    # [%] trigger position in record
        "vertical_range":  10.0,    # [V] peak-to-peak range per channel
        "vertical_offset":  0.0,    # [V]
        "probe_attenuation": 1.0,   # probe factor
        "coupling": niscope.VerticalCoupling.DC,
        "trigger_source":   "0",    # channel 0 as trigger source
        "trigger_level":    0.0,    # [V]
        "trigger_slope": niscope.TriggerSlope.POSITIVE,
        "trigger_type":  niscope.TriggerType.EDGE,
        "timeout":          5.0,    # [s] acquisition timeout
    }

    def __init__(self, resource_name: str = "Jakobs"):
        '''
        Parameters
        ----------
        resource_name : str
            NI-MAX alias or resource string, e.g. "Jakobs" or "PXI1Slot2"
        '''
        self.resource_name = resource_name
        self.name = "NI PXIe-5170R"
        self.n_channels = 8
        self.__session = None   # private, access via self.connection

        # copy defaults so per-instance changes don't affect class
        self.settings = dict(self.DEFAULT_SETTINGS)

    # ------------------------------------------------------------------
    # connection property (mirrors BaseDevice pattern)
    # ------------------------------------------------------------------
    @property
    def connection(self):
        if self.__session is None:
            print(f"\n[{self.name}] ScopeNI5170R.connection")
            print(f"{self.RED}Device is not connected{self.RESET}")
        return self.__session

    # ------------------------------------------------------------------
    # connect / disconnect
    # ------------------------------------------------------------------
    def connect(self, silent: bool = True) -> "ScopeNI5170R":
        '''Open niscope session and apply default settings.'''
        if not silent:
            print(f"\n=+=+= ScopeNI5170R.connect() =+=+=")
        try:
            self.__session = niscope.Session(self.resource_name)
            print(f"{self.GREEN}Connected to {self.name} [{self.resource_name}]{self.RESET}")
            self.after_connect(silent=silent)
        except Exception as e:
            print(f"{self.RED}Connection failed: {e}{self.RESET}")
        return self

    def after_connect(self, silent: bool = True) -> "ScopeNI5170R":
        '''Configure default vertical/horizontal settings after connect.'''
        if not silent:
            print("=== ScopeNI5170R after_connect() ===")
        try:
            self.configure_channels(
                channels=list(range(self.n_channels)),
                vertical_range=self.settings["vertical_range"],
                vertical_offset=self.settings["vertical_offset"],
                coupling=self.settings["coupling"],
                probe_attenuation=self.settings["probe_attenuation"],
                silent=silent,
            )
            self.configure_timing(
                sample_rate=self.settings["sample_rate"],
                record_length=self.settings["record_length"],
                ref_position=self.settings["ref_position"],
                silent=silent,
            )
        except Exception as e:
            print(f"{self.RED}after_connect error: {e}{self.RESET}")
        if not silent:
            print("=== ScopeNI5170R after_connect() ended ===")
        return self

    def disconnect(self) -> "ScopeNI5170R":
        '''Close niscope session.'''
        if self.__session is None:
            print(f"\n[{self.name}] connection=None, may not have been open")
            return self
        try:
            self.__session.close()
            print(f"{self.GREEN}[{self.name}] Connection closed.{self.RESET}")
        except Exception as e:
            print(f"{self.RED}[{self.name}] Error closing: {e}{self.RESET}")
        finally:
            self.__session = None
        return self

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    def configure_channels(
        self,
        channels: list = None,
        vertical_range: float = None,
        vertical_offset: float = None,
        coupling=None,
        probe_attenuation: float = None,
        silent: bool = True,
    ) -> "ScopeNI5170R":
        '''Configure vertical settings for one or more channels.'''
        if self.__session is None:
            print(f"{self.RED}configure_channels(): not connected{self.RESET}")
            return self

        channels         = channels         or list(range(self.n_channels))
        vertical_range   = vertical_range   or self.settings["vertical_range"]
        vertical_offset  = vertical_offset  or self.settings["vertical_offset"]
        coupling         = coupling         or self.settings["coupling"]
        probe_attenuation = probe_attenuation or self.settings["probe_attenuation"]

        ch_str = ",".join(str(c) for c in channels)
        try:
            self.__session.channels[ch_str].configure_vertical(
                range=vertical_range,
                offset=vertical_offset,
                coupling=coupling,
                probe_attenuation=probe_attenuation,
                enabled=True,
            )
            if not silent:
                print(f"Channels {ch_str} configured: range={vertical_range}V, "
                      f"offset={vertical_offset}V")
        except Exception as e:
            print(f"{self.RED}configure_channels() error: {e}{self.RESET}")
        return self

    def configure_timing(
        self,
        sample_rate: float = None,
        record_length: int = None,
        ref_position: float = None,
        silent: bool = True,
    ) -> "ScopeNI5170R":
        '''Configure horizontal timing (sample rate, record length).'''
        if self.__session is None:
            print(f"{self.RED}configure_timing(): not connected{self.RESET}")
            return self

        sample_rate    = sample_rate    or self.settings["sample_rate"]
        record_length  = record_length  or self.settings["record_length"]
        ref_position   = ref_position   or self.settings["ref_position"]

        try:
            self.__session.configure_horizontal_timing(
                min_sample_rate=sample_rate,
                min_num_pts=record_length,
                ref_position=ref_position,
                num_records=1,
                enforce_realtime=True,
            )
            if not silent:
                print(f"Timing configured: sample_rate={sample_rate/1e6:.1f} MS/s, "
                      f"record_length={record_length}")
        except Exception as e:
            print(f"{self.RED}configure_timing() error: {e}{self.RESET}")
        return self

    def configure_trigger(
        self,
        trigger_source: str = None,
        trigger_level: float = None,
        trigger_slope=None,
        silent: bool = True,
    ) -> "ScopeNI5170R":
        '''Configure edge trigger.'''
        if self.__session is None:
            print(f"{self.RED}configure_trigger(): not connected{self.RESET}")
            return self

        trigger_source = trigger_source or self.settings["trigger_source"]
        trigger_level  = trigger_level  or self.settings["trigger_level"]
        trigger_slope  = trigger_slope  or self.settings["trigger_slope"]

        try:
            self.__session.configure_trigger_edge(
                trigger_source=trigger_source,
                level=trigger_level,
                trigger_coupling=niscope.TriggerCoupling.DC,
                slope=trigger_slope,
            )
            if not silent:
                print(f"Trigger: source={trigger_source}, level={trigger_level}V")
        except Exception as e:
            print(f"{self.RED}configure_trigger() error: {e}{self.RESET}")
        return self

    # ------------------------------------------------------------------
    # acquisition
    # ------------------------------------------------------------------
    def read_waveform(
        self,
        channels: list = None,
        timeout: float = None,
        silent: bool = True,
    ) -> dict:
        '''
        Acquire one waveform per channel.

        Returns
        -------
        dict with keys:
            "time_s"   : np.ndarray  – time axis [s]
            "ch{n}"    : np.ndarray  – voltage data per channel [V]
            "dt_s"     : float       – sample interval [s]
            "duration_s": float      – acquisition wall-clock time [s]
        '''
        if self.__session is None:
            print(f"{self.RED}read_waveform(): not connected{self.RESET}")
            return {}

        channels = channels or [0]
        timeout  = timeout  or self.settings["timeout"]
        ch_str   = ",".join(str(c) for c in channels)

        t0 = time.perf_counter()
        try:
            self.__session.initiate()
            waveform_infos = self.__session.channels[ch_str].fetch(
                timeout=timeout
            )
            dt = time.perf_counter() - t0

            result = {"duration_s": dt}
            for i, wfm in enumerate(waveform_infos):
                data = np.array(wfm.samples)
                if i == 0:
                    n = len(data)
                    dt_s = 1.0 / self.__session.actual_meas_wfm_size if hasattr(
                        self.__session, "actual_meas_wfm_size") else (
                        1.0 / self.settings["sample_rate"])
                    result["time_s"] = np.arange(n) * dt_s
                    result["dt_s"]   = dt_s
                result[f"ch{channels[i]}"] = data

            if not silent:
                print(f"read_waveform(): {len(channels)} ch, "
                      f"{len(result['time_s'])} pts, dt={dt:.3f}s")
            return result

        except Exception as e:
            print(f"{self.RED}read_waveform() error: {e}{self.RESET}")
            return {}

    def read_waveform_df(
        self,
        channels: list = None,
        timeout: float = None,
        silent: bool = True,
    ) -> pd.DataFrame:
        '''Same as read_waveform() but returns a pandas DataFrame.'''
        data = self.read_waveform(channels=channels, timeout=timeout, silent=silent)
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame({k: v for k, v in data.items()
                           if k not in ("dt_s", "duration_s")})
        df.set_index("time_s", inplace=True)
        return df

    # ------------------------------------------------------------------
    # read helpers
    # ------------------------------------------------------------------
    def read_actual_settings(self) -> "ScopeNI5170R":
        '''Print current session settings.'''
        if self.__session is None:
            print(f"{self.RED}read_actual_settings(): not connected{self.RESET}")
            return self
        print(f"\n=== {self.GREEN}read_actual_settings() [{self.name}]{self.RESET} ===")
        try:
            print(f"  sample_rate      = {self.__session.horz_sample_rate/1e6:.1f} MS/s")
            print(f"  record_length    = {self.__session.horz_record_length} pts")
            print(f"  ref_position     = {self.__session.horz_record_ref_position} %")
        except Exception as e:
            print(f"{self.RED}  Error reading settings: {e}{self.RESET}")
        print("=" * 50)
        return self

    # ------------------------------------------------------------------
    # plot helper
    # ------------------------------------------------------------------
    def plot_waveform(
        self,
        channels: list = None,
        timeout: float = None,
    ) -> "ScopeNI5170R":
        '''Acquire and immediately plot waveforms.'''
        channels = channels or [0]
        data = self.read_waveform(channels=channels, timeout=timeout, silent=False)
        if not data:
            return self

        t = data["time_s"] * 1e3  # → ms for readability
        fig, ax = plt.subplots(figsize=(10, 4))
        for ch in channels:
            key = f"ch{ch}"
            if key in data:
                ax.plot(t, data[key], label=f"CH{ch}")
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Voltage (V)")
        ax.set_title(f"{self.name} – waveform")
        ax.legend()
        ax.grid(True, linestyle=":", alpha=0.6)
        plt.tight_layout()
        plt.show()
        return self


# ======================================================================
# Concrete subclass – add experiment-specific defaults here
# ======================================================================
class ScopeJakobs(ScopeNI5170R):
    '''
    PXIe-5170R configured for the AvP-Lab setup ("Jakobs").
    Override DEFAULT_SETTINGS to match your typical measurement.
    '''
    DEFAULT_SETTINGS = {
        **ScopeNI5170R.DEFAULT_SETTINGS,   # inherit all defaults
        "sample_rate":     250e6,
        "record_length":   10000,
        "vertical_range":   2.0,           # [V] tighter range for lab signals
        "trigger_source":  "0",
        "trigger_level":   0.1,            # [V]
    }

    def __init__(self):
        super().__init__(resource_name="Jakobs")
        self.name = "NI PXIe-5170R (Jakobs)"


# ======================================================================
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{style.MAGENTA}======== scope_ni5170r.py module ========={style.RESET}")

    scope = ScopeJakobs()
    scope.connect(silent=False)

    scope.read_actual_settings()

    # configure trigger on channel 0
    scope.configure_trigger(trigger_source="0", trigger_level=0.1, silent=False)

    # read waveform from channels 0 and 1
    # df = scope.read_waveform_df(channels=[0, 1])
    # print(df.head())

    # quick plot
    # scope.plot_waveform(channels=[0, 1])

    scope.disconnect()