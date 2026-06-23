"""
Generic Lock-In Amplifier class.
Reads the demodulated fluorescence signal (R, X, Y, phase)
synchronized with the AOM modulation frequency.

To adapt for a specific device:
1. Set self.hwid to the device's hardware ID
2. Set self.IDN to the device's *IDN? response
3. Fill in the CMD_DIKT with device-specific commands
4. Implement the marked sections in each method

--- not yet tested ---
"""

from base_device import BaseDevice
import time
import numpy as np
import pandas as pd
import os


class LockInAmplifier(BaseDevice):

    # ================================================================
    # DEVICE-SPECIFIC: fill in commands for your device
    # ================================================================
    CMD_DIKT = {
        "IDN":        "*IDN?",          # identification
        "RST":        "*RST",           # reset
        # Output channels
        "X":          "OUTP? 1",        # X (in-phase) component      → DEVICE-SPECIFIC
        "Y":          "OUTP? 2",        # Y (quadrature) component     → DEVICE-SPECIFIC
        "R":          "OUTP? 3",        # R (magnitude) = sqrt(X²+Y²) → DEVICE-SPECIFIC
        "THETA":      "OUTP? 4",        # phase angle                  → DEVICE-SPECIFIC
        # Reference
        "REF_FREQ":   "FREQ?",          # reference frequency          → DEVICE-SPECIFIC
        "REF_SOURCE": "FMOD?",          # reference source (int/ext)   → DEVICE-SPECIFIC
        # Sensitivity and time constant
        "SENS":       "SENS?",          # sensitivity setting          → DEVICE-SPECIFIC
        "TC":         "OFLT?",          # time constant                → DEVICE-SPECIFIC
        "SET_TC":     "OFLT",           # set time constant            → DEVICE-SPECIFIC
        "SET_SENS":   "SENS",           # set sensitivity              → DEVICE-SPECIFIC
        # Filter
        "FILTER":     "OFSL?",          # filter slope (dB/oct)        → DEVICE-SPECIFIC
    }

    CONNECTION_SETTINGS = {
        # ================================================================
        # DEVICE-SPECIFIC: fill in connection settings for your device
        # ================================================================
        'read_termination':  '\n',      # → DEVICE-SPECIFIC
        'write_termination': '\n',      # → DEVICE-SPECIFIC
        'timeout':           5000,
    }

    def __init__(self):
        super().__init__()
        # ================================================================
        # DEVICE-SPECIFIC: set hwid and IDN for your device
        # ================================================================
        self.hwid = None    # → DEVICE-SPECIFIC
        self.IDN  = None    # → DEVICE-SPECIFIC
        self.name = "LockInAmplifier"
        self.port = self.hwid

        self.time_sleep       = 0.05
        self.time_constant_s  = None   # will be read after connect
        self.sensitivity      = None   # will be read after connect
        self.reference_source = None   # "INT" or "EXT"


    def after_connect(self, silent=True):
        print(f"{self.name} after_connect()")
        try:
            self.flush_buffer(silent=silent)
            # ================================================================
            # DEVICE-SPECIFIC: add initialization commands here
            # ================================================================
            # e.g. for SR830:
            # self.send_command("FMOD 1")   # external reference
            # self.send_command("ISRC 1")   # input: A-B differential
            # self.send_command("ICPL 0")   # AC coupling

            # read initial state
            self.time_constant_s  = self._parse_time_constant()
            self.sensitivity      = self._parse_sensitivity()
            self.reference_source = self.read_value(
                self.CMD_DIKT["REF_SOURCE"], silent=silent)

            if not silent:
                print(f"  time_constant = {self.time_constant_s} s")
                print(f"  sensitivity   = {self.sensitivity}")
                print(f"  ref_source    = {self.reference_source}")

        except Exception as e:
            print(f"{self.RED}[{self.name}] after_connect error: {e}{self.RESET}")
        return self


    def flush_buffer(self, silent=True):
        """Flush the input buffer."""
        try:
            n = self.connection.bytes_in_buffer
            if n:
                buf = self.connection.read_bytes(n)
                if not silent:
                    print(f"[{self.name}] flushed {n} bytes: {buf}")
            else:
                if not silent:
                    print(f"{self.GREEN}[{self.name}] buffer empty{self.RESET}")
        except Exception as e:
            if not silent:
                print(f"[{self.name}] flush_buffer error: {e}")
        return self


    def send_command(self, cmd: str, silent=True):
        """Send a command and flush buffer."""
        response = self.connection.query(cmd)
        time.sleep(self.time_sleep)
        if not silent:
            print(f"[{self.name}] send_command({self.BLUE}{cmd}{self.RESET}) = {response}")
        self.flush_buffer(silent=silent)
        return response


    def read_value(self, cmd: str, silent=True):
        """Query a value from the device."""
        response = self.connection.query(cmd)
        if not silent:
            print(f"[{self.name}] read_value({self.BLUE}{cmd}{self.RESET}) = {response}")
        return response


    # ----------------------------------------------------------------
    # Device-specific parsing helpers
    # ----------------------------------------------------------------

    def _parse_time_constant(self) -> float:
        """
        Parse the time constant from the device response.
        Many lock-ins return an index (0,1,2,...) not a value in seconds.
        ================================================================
        DEVICE-SPECIFIC: implement parsing for your device
        ================================================================
        Example for SR830 (index → seconds):
        TC_MAP = {0: 10e-6, 1: 30e-6, 2: 100e-6, 3: 300e-6,
                  4: 1e-3,  5: 3e-3,  6: 10e-3,  7: 30e-3,
                  8: 100e-3,9: 300e-3,10: 1.0,   11: 3.0,
                  12: 10.0, 13: 30.0, 14: 100.0, 15: 300.0, 16: 1000.0}
        idx = int(self.read_value(self.CMD_DIKT["TC"]))
        return TC_MAP.get(idx, None)
        """
        response = self.read_value(self.CMD_DIKT["TC"])
        return float(response)   # → DEVICE-SPECIFIC: may need index mapping


    def _parse_sensitivity(self):
        """
        Parse the sensitivity from the device response.
        ================================================================
        DEVICE-SPECIFIC: implement parsing for your device
        ================================================================
        """
        response = self.read_value(self.CMD_DIKT["SENS"])
        return response          # → DEVICE-SPECIFIC: may need index mapping


    # ----------------------------------------------------------------
    # Set functions
    # ----------------------------------------------------------------

    def set_time_constant(self, tc_index: int, silent=True):
        """
        Set the time constant.
        ================================================================
        DEVICE-SPECIFIC: tc_index meaning depends on your device
        For SR830: 0=10µs, 1=30µs, ..., 10=1s, ...
        ================================================================
        """
        cmd = f"{self.CMD_DIKT['SET_TC']} {tc_index}"   # → DEVICE-SPECIFIC
        self.send_command(cmd, silent=silent)
        self.time_constant_s = self._parse_time_constant()
        if not silent:
            print(f"[{self.name}] time constant set to index {tc_index}"
                  f" = {self.time_constant_s} s")
        return self


    def set_sensitivity(self, sens_index: int, silent=True):
        """
        Set the input sensitivity.
        ================================================================
        DEVICE-SPECIFIC: sens_index meaning depends on your device
        For SR830: 0=2nV, 1=5nV, ..., 26=1V
        ================================================================
        """
        cmd = f"{self.CMD_DIKT['SET_SENS']} {sens_index}"  # → DEVICE-SPECIFIC
        self.send_command(cmd, silent=silent)
        self.sensitivity = self._parse_sensitivity()
        return self


    # ----------------------------------------------------------------
    # Read functions
    # ----------------------------------------------------------------

    def read_X(self, silent=True) -> float:
        """Read X (in-phase) component."""
        return float(self.read_value(self.CMD_DIKT["X"], silent=silent))

    def read_Y(self, silent=True) -> float:
        """Read Y (quadrature) component."""
        return float(self.read_value(self.CMD_DIKT["Y"], silent=silent))

    def read_R(self, silent=True) -> float:
        """Read R (magnitude) = sqrt(X² + Y²)."""
        return float(self.read_value(self.CMD_DIKT["R"], silent=silent))

    def read_theta(self, silent=True) -> float:
        """Read phase angle θ in degrees."""
        return float(self.read_value(self.CMD_DIKT["THETA"], silent=silent))

    def read_XY(self, silent=True) -> dict:
        """
        Read X and Y simultaneously.
        ================================================================
        DEVICE-SPECIFIC: some devices support reading both in one query
        e.g. SR830: "SNAP? 1,2" returns "X,Y" in one response
        ================================================================
        """
        # default: two separate queries
        x = self.read_X(silent=silent)
        y = self.read_Y(silent=silent)
        r = np.sqrt(x**2 + y**2)
        theta = np.degrees(np.arctan2(y, x))
        return {"X": x, "Y": y, "R": r, "theta_deg": theta}


    def read_signal(self, silent=True, device_read_time=False) -> dict:
        """
        Main read function – returns the demodulated LIF signal.
        This is called by LIFManager.read_state() and scan_piezo().

        Returns R (magnitude) as the primary LIF signal,
        plus X, Y, phase for diagnostics.
        """
        t0 = time.perf_counter()
        data = self.read_XY(silent=silent)
        dt = time.perf_counter() - t0

        result = {}
        if device_read_time:
            result.update({"time_s": t0, "duration_s": dt})
        result.update(data)
        return result


    def monitor(self,
                n_measurements: int = 10,
                sleep: float = None,
                silent: bool = True) -> pd.DataFrame:
        """
        Read the lock-in signal n times and return a DataFrame.
        Useful for checking signal stability before a scan.
        sleep defaults to 3 × time_constant for proper settling.
        """
        if sleep is None:
            sleep = (self.time_constant_s * 3
                     if self.time_constant_s else 0.1)

        records = []
        t0 = None
        for i in range(n_measurements):
            data = self.read_signal(silent=silent, device_read_time=True)
            if t0 is None:
                t0 = data["time_s"]
            data["time_s"] -= t0
            if not silent:
                print(f"[{self.name}] monitor {i+1}/{n_measurements}: "
                      f"R={data['R']:.6e}, θ={data['theta_deg']:.2f}°")
            records.append(data)
            time.sleep(sleep)

        return pd.DataFrame(records).set_index("time_s")


    def disconnect(self):
        return BaseDevice.disconnect(self)


# ================================================================
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== LockInAmplifier test ===")

    lia = LockInAmplifier()
    lia.print_connections()

    # lia.connect()
    # print(lia.read_signal(silent=False))
    # print(lia.monitor(n_measurements=5, silent=False))
    # lia.disconnect()