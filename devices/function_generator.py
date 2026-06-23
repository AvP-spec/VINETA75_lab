"""
Generic Function Generator class.
Controls the AOM modulation frequency and provides the Lock-In reference signal.

To adapt for a specific device:
1. Set self.hwid to the device's hardware ID
2. Set self.IDN to the device's *IDN? response
3. Fill in the CMD_DIKT with device-specific commands
4. Implement the marked sections in each method

--- not yet tested ---
"""

from base_device import BaseDevice
import time
import os


class FunctionGenerator(BaseDevice):

    # ================================================================
    # DEVICE-SPECIFIC: fill in commands for your device
    # ================================================================
    CMD_DIKT = {
        "IDN":       "*IDN?",           # identification
        "RST":       "*RST",            # reset
        "FREQ":      "FREQ",            # set frequency          → DEVICE-SPECIFIC
        "FREQ_Q":    "FREQ?",           # query frequency        → DEVICE-SPECIFIC
        "AMP":       "VOLT",            # set amplitude          → DEVICE-SPECIFIC
        "AMP_Q":     "VOLT?",           # query amplitude        → DEVICE-SPECIFIC
        "OUT_ON":    "OUTP ON",         # output on              → DEVICE-SPECIFIC
        "OUT_OFF":   "OUTP OFF",        # output off             → DEVICE-SPECIFIC
        "OUT_Q":     "OUTP?",           # query output state     → DEVICE-SPECIFIC
        "WAVEFORM":  "FUNC",            # set waveform           → DEVICE-SPECIFIC
    }

    CONNECTION_SETTINGS = {
        # ================================================================
        # DEVICE-SPECIFIC: fill in connection settings for your device
        # ================================================================
        'read_termination':  '\n',      # → DEVICE-SPECIFIC
        'write_termination': '\n',      # → DEVICE-SPECIFIC
        'timeout':           5000,      # 5 sec
    }

    def __init__(self):
        super().__init__()
        # ================================================================
        # DEVICE-SPECIFIC: set hwid and IDN for your device
        # ================================================================
        self.hwid = None    # e.g. "VID:PID = 0403:6001" or GPIB address → DEVICE-SPECIFIC
        self.IDN  = None    # expected *IDN? response string              → DEVICE-SPECIFIC
        self.name = "FunctionGenerator"
        self.port = self.hwid

        self.time_sleep = 0.05

        # state
        self.frequency_Hz = None
        self.amplitude_V  = None
        self.output_on    = None
        self.waveform     = None


    def after_connect(self, silent=True):
        print(f"{self.name} after_connect()")
        try:
            self.flush_buffer(silent=silent)
            # ================================================================
            # DEVICE-SPECIFIC: add initialization commands here
            # ================================================================
            # e.g.:
            # self.send_command("RST", silent=silent)
            # self.send_command("WAVEFORM SIN", silent=silent)
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
        """Send a command and read acknowledgement if available."""
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
    # Set functions
    # ----------------------------------------------------------------

    def set_frequency(self, frequency_Hz: float, silent=True):
        """
        Set the output frequency in Hz.
        This controls the AOM modulation frequency = Lock-In reference.
        """
        # ================================================================
        # DEVICE-SPECIFIC: adjust command format for your device
        # ================================================================
        cmd = f"{self.CMD_DIKT['FREQ']} {frequency_Hz:.6f}"   # → DEVICE-SPECIFIC
        self.send_command(cmd, silent=silent)
        self.frequency_Hz = frequency_Hz
        if not silent:
            print(f"[{self.name}] frequency set to {frequency_Hz} Hz")
        return self


    def set_amplitude(self, amplitude_V: float, silent=True):
        """Set the output amplitude in Volts (peak-to-peak or amplitude → DEVICE-SPECIFIC)."""
        # ================================================================
        # DEVICE-SPECIFIC: adjust command format for your device
        # ================================================================
        cmd = f"{self.CMD_DIKT['AMP']} {amplitude_V:.4f}"     # → DEVICE-SPECIFIC
        self.send_command(cmd, silent=silent)
        self.amplitude_V = amplitude_V
        if not silent:
            print(f"[{self.name}] amplitude set to {amplitude_V} V")
        return self


    def set_waveform(self, waveform: str = "SIN", silent=True):
        """
        Set the output waveform.
        Typical options: SIN, SQU, TRI, RAMP → DEVICE-SPECIFIC
        For AOM modulation usually SIN or SQU.
        """
        # ================================================================
        # DEVICE-SPECIFIC: adjust command format for your device
        # ================================================================
        cmd = f"{self.CMD_DIKT['WAVEFORM']} {waveform}"       # → DEVICE-SPECIFIC
        self.send_command(cmd, silent=silent)
        self.waveform = waveform
        return self


    # ----------------------------------------------------------------
    # Switch functions
    # ----------------------------------------------------------------

    def output_on(self, silent=True):
        """Enable the output signal → starts AOM modulation."""
        self.send_command(self.CMD_DIKT["OUT_ON"], silent=silent)
        self.output_on = True
        print(f"[{self.name}] {self.GREEN}output ON{self.RESET}")
        return self


    def output_off(self, silent=True):
        """Disable the output signal → stops AOM modulation."""
        self.send_command(self.CMD_DIKT["OUT_OFF"], silent=silent)
        self.output_on = False
        print(f"[{self.name}] {self.RED}output OFF{self.RESET}")
        return self


    # ----------------------------------------------------------------
    # Read functions
    # ----------------------------------------------------------------

    def read_frequency(self, silent=True) -> float:
        """Read the current output frequency in Hz."""
        # ================================================================
        # DEVICE-SPECIFIC: adjust parsing for your device response
        # ================================================================
        response = self.read_value(self.CMD_DIKT["FREQ_Q"], silent=silent)
        return float(response)                                 # → DEVICE-SPECIFIC


    def read_amplitude(self, silent=True) -> float:
        """Read the current output amplitude in V."""
        # ================================================================
        # DEVICE-SPECIFIC: adjust parsing for your device response
        # ================================================================
        response = self.read_value(self.CMD_DIKT["AMP_Q"], silent=silent)
        return float(response)                                 # → DEVICE-SPECIFIC


    def read_output_state(self, silent=True) -> str:
        """Read whether output is ON or OFF."""
        # ================================================================
        # DEVICE-SPECIFIC: adjust parsing for your device response
        # ================================================================
        response = self.read_value(self.CMD_DIKT["OUT_Q"], silent=silent)
        return response                                        # → DEVICE-SPECIFIC


    def read_state(self, silent=True) -> dict:
        """Read all relevant state parameters."""
        t0 = time.perf_counter()
        data = {
            "frequency_Hz":  self.read_frequency(silent=silent),
            "amplitude_V":   self.read_amplitude(silent=silent),
            "output_state":  self.read_output_state(silent=silent),
        }
        data["duration_s"] = time.perf_counter() - t0
        return data


    def disconnect(self):
        try: 
            if self.connection is not None: 
                self.output_off()
        except Exception as e:
            pass # print(f"[{self.name}] output_off at disconnect failed: {e}")
        return BaseDevice.disconnect(self)


# ================================================================
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== FunctionGenerator test ===")

    fg = FunctionGenerator()
    fg.print_connections()

    # fg.connect()
    # print(fg.read_state())
    # fg.set_frequency(1000)       # 1 kHz für AOM
    # fg.set_amplitude(1.0)
    # fg.set_waveform("SIN")
    # fg.output_on()
    # time.sleep(1)
    # fg.output_off()
    # fg.disconnect()