# \devices\Advanttest_Q8326.py
from base_device import BaseDevice
import pandas as pd
import pyvisa
import os
import sys
import time
import subprocess

class Q8326(BaseDevice):

    CONNECTION_SETTINGS = {
        'read_termination': '\r\n', #  manual defoult "D0" mode
        'write_termination': '\r\n', #  manual
        'timeout': 5000 # 5 sec, measure averaged wavelength takes about 2.6 sec
    }

    CMD_DIKT = {
        "Z": "MASTER RESET", # clears the settings on the panel 
        "C" : "RESET",       # clear data",
        "E" : "SINGLE Measurement", 
        "H0": "HEADER OFF",  # header control for output data
        "H1": "HEADER ON",   # header control for output data
        "K0": "nm",          # wavelength measuremets
        "K1": "MHz",         # frequency measurements
        "F0": "CHECK",       # function CHECK for wavelength measurements
        "F1": "LASER",       # function LASER for measurement of a laser wavelength/frequency
        "F2": "LED",         # function LED for measurement of a LED wavelength/frequency
        "F3": "CHOP",        # function CHOP for measurement of a choped signal
        "W0": "480-1000 nm", # "set wavelength range: 480-1000 nm",
        "RE0": "RSOLUTION MAX", # 0.0001 nm / 10 MHz, when set to AVG
        "RE1": "RESOLUTION HIGH", # 0.001 nm / 100 MHz
        "RE2": "RESOLUTION MODERATE", # 0.01 nm / 1 GHz
        "RE3": "RESOLUTION LOW", # 0.1 nm / 10 GHz
        "RE4": "RESOLUTION MIN", # 1 nm / 100 GHz
        "M0": "RUN",          #"Sample Mode RUN",
        "M1": "HOLD",         #"Sample Mode HOLD",
        "A0": "AVG OFF",      # average off
        "A1": "AVG ON",       # average on
        "CA0": "CAL 0m",      # set altitude 0m - sea level
        "B1": "BUZZER ON",   # set Beap when error
        "RF0": "DRIFT OFF",  # - show only current wavelength / frequency,
        "RF1": "DRIFT ON",   # show drift (change) of the wavelngth / frequency

    }

    ## to use auto filling 
    UNITS = {
            "WAVELENGTH": "nm",
            "FREQUENCY": "THz"
        }


    def __init__(self):
        super().__init__()
        self.hwid = "USB0::0x03EB::0x2065::GPIB_06_4423030363035131A1C0::INSTR"
        self.name = self.DEVICE_DICT[self.hwid]
        self.port = self.hwid
        self.time_sleep = 0.1 # might work with 0.01
        self.units = None


    def after_connect(self, silent=True):
        print("Advantest_Q8326 after_connect()")
        try: 
            self.connection.clear()
        except pyvisa.errors.VisaIOError as e: 
            print(f"[{self.name}] clear() nicht unterstützt, übersprungen: {e}")
        time.sleep(self.time_sleep)
        slow = False
        print("1", end="", flush=True)
        self.send_command("M1", silent=silent, slow=slow)      #"Sample Mode HOLD",
        print("1", end="", flush=True)
        self.flush_buffer_GPIB(silent=silent)
        print("1", end="", flush=True)
        self.send_command("F1", silent=silent, slow=slow)    # function LASER for measurement of a laser wavelength/frequency
        print("1", end="", flush=True)
        self.send_command("W0", silent=silent, slow=slow)    # "set wavelength range: 480-1000 nm",
        print("1", end="", flush=True)
        self.send_command("RF0", silent=silent, slow=slow)   # drift off
        print("1", end="", flush=True)
        self.send_command("CA0", silent=silent, slow=slow)   # set altitude 0m - sea level
        print("1", end="", flush=True)
        self.send_command("B1", silent=silent, slow=slow)    # set Beap when error
        print("1", end="", flush=True)
        self.send_command("A1", silent=silent, slow=slow)    # average on
        print("1", end="", flush=True)
        self.send_command("RE0", silent=silent, slow=slow)   # "RSOLUTION MAX", # 0.0001 nm / 10 MHz,
        print("1", end="", flush=True)
        self.set_units(self.UNITS["WAVELENGTH"], silent=silent, slow=slow)
        print("1", end="")
        
        print(f"\n{self.BLUE}{self.name}{self.GREEN} connected" 
                f" on port {self.BLUE}{self.port}{self.RESET} \n")

        return self
    

    def send_command(self, cmd:str, silent=True, slow=False):
        """
        Sends a command to the Advantest Q8326 and checks the Status Byte (STB).
        If the device reports an error (if stb), it flushes the buffer and retries once.
        """
        
        cmd_name = self.CMD_DIKT.get(cmd, "cmd is not in self.CMD_DIKT")

        self.connection.write(cmd)

        if slow: 
            time.sleep(self.time_sleep)
            print(f"Q8326.send_command(): wlm.time_sleep = {self.time_sleep}")

        # status_byte = self.connection.stb
        status_byte = self._get_status_byte()
        status = self._get_status_msg(status_byte)
        if not silent:
            print(f"[{self.name}] send_command({self.BLUE}{cmd}: {cmd_name}"
                  f"{self.RESET}) = {status}, {status_byte=}")
        
        self.flush_buffer_GPIB(silent=silent)

        if status_byte: # != 0:
            print(f"--- {self.YELLOW}second attempt to send command{self.RESET} ---")
            status_byte = self.connection.stb
            print(f"initial {status_byte=} \n")
            
            ## the read command to clean the status byte
            print("self.read()")
            print(self.read())
            print(f"waite {self.time_sleep} s")
            time.sleep(self.time_sleep)
            status_byte = self.connection.stb
            print(f"after 'read' {status_byte=}\n")

            print("write(cmd)")
            self.connection.write(cmd)
            print(f"waite {self.time_sleep} s")
            time.sleep(self.time_sleep)
            status_byte = self.connection.stb
            print(f"[{self.name}] send_command({self.BLUE}{cmd}: {cmd_name}"
                  f"{self.RESET}) = {status}")
            
            self.flush_buffer_GPIB(silent=False)
            
        return self

    def _get_status_msg(self, stb):
        ''' interpreate status byte and get massage
                STB Interpretation Table:
        -  0 (0000 0000): O.K. Device is idle and ready.
        - 64 (0100 0000): RQS (Request Service) bit active.
        - 65 (0100 0001): Data Ready. Measurement finished, data waiting in buffer.
        - 66 (0100 0010): Syntax Error. Command not recognized.
        - 67 (0100 0011): Syntax Error + Data. Error occurred, buffer not empty.
        - None: was not possible to read STB
        '''
        if stb == 0: return f"{self.GREEN}O.K.{self.RESET}"
        if stb in [66, 67]: return f"{self.RED}Syntax Error{self.RESET}"
        if stb == 65: return f"{self.BLUE}Data in buffer{self.RESET}"
        if stb == 64: return f"{self.YELLOW}RQS bit only{self.RESET}"
        if stb == None: return f"{self.YELLOW}stb not avalible{self.RESET}"
        return f"{self.RED}Unknown State {stb}{self.RESET}"

    def _get_status_byte(self) -> int:
        """linux drivers might does not work propaly
           the command self.connection.stb often failed
        """
        try:
            status_byte = self.connection.stb
            # print(f"get_{status_byte=}, {type(status_byte)=}")
            return status_byte
        except Exception as e:
            if sys.platform == 'linux':
                print(f"{self.GREEN}[{self.name}]: linux detected {self.RESET}")
                print(f"NI-VISA probably not installed")
                return None
             
            print(f"{self.RED}[{self.name}]: get_status_byte error: {self.RESET}")
            print(f"{e}")
            return None


    def flush_buffer_GPIB(self, silent=False):
        '''
        critical for stable and synchronysed connectoin of the instrument with pyvisa 
        silent=False will print the buffer content
        '''
        # print("Q8326.flush_buffer_GPIB()")

        self.connection.timeout = 500
        start_time = time.time()
        max_duration = 120  # 2 minutes in seconds
        count = 0
        while True:
            if time.time() - start_time > max_duration:
                self.connection.timeout = self.CONNECTION_SETTINGS["timeout"]
                raise TimeoutError(f"[{self.name}] Critical Error:" 
                                 f" {self.RED} Buffer flush exceeded {max_duration}s.{self.RESET} "
                               "The instrument might be stuck in continuous mode.")
            try:
                junk = self.connection.read_raw()
                count += 1
                print(f"Flushed junk No.{count}: {junk}")
            except pyvisa.errors.VisaIOError:
                if not silent:
                    print(f"[{self.name}]: {self.GREEN} buffer is empty {self.RESET}")
                break
        self.connection.timeout = self.CONNECTION_SETTINGS["timeout"]

        return self
    

    def average_on(self, silent=False, slow=False):
        self.send_command("A1", silent=silent, slow=slow)
        self.send_command("RE0", silent=silent, slow=slow)
        self.average = "ON"
        return self

    
    def average_off(self, silent=False, slow=False):
        self.send_command("A0", silent=silent, slow=slow)
        self.send_command("RE1", silent=silent, slow=slow)
        self.average = "OFF"
        return self


    def set_units(self, unit:str="nm", silent=False, slow=False):
        if unit == "nm":
            self.send_command("K0", silent=silent, slow=slow)
            self.units = "nm"
        elif unit == "THz":
            self.send_command("K1", silent=silent, slow=slow)
            self.units = "THz"
        else:
            print(f"[{self.name}] {self.RED}Error: {self.RESET} "
                  f"Unit '{unit}' is not supported. Use 'nm' or 'THz'.")
        return self


    def read(self, device_read_time=False, slow=False, silent=True,) -> dict:
        """Read wavelength with optional timing metadata."""
        if slow:
            self.flush_buffer_GPIB(silent=silent) # takes 0.6 sec

        factor = {"nm": 1E9, "THz": 1E-12}
        t0 = time.perf_counter()
        value = self.connection.query("E")
        dt = time.perf_counter() - t0

        readout = {}
        if device_read_time:
            readout.update({'wlm_time_s': t0, 
                            'wlm_duration_s': dt}) 
        readout[str(self.units)] = float(value)*factor[self.units]
        return readout

    
    def wlm_monitor(self, n_measurements=1, silent=False):
        t0 = None
        results = []
        for i in range(n_measurements):
            data = self.read(silent=True, device_read_time=True)
            if t0 is None:
                t0 = data['wlm_time_s']

            if not silent:
                print(f"wlm_monitor measurement No.{i}: "
                      f"{data[str(self.units)]:.4f} {self.units}, {data['wlm_time_s']-t0:.2f} s ")
            results.append(data)
            time.sleep(self.time_sleep)
 
        df = pd.DataFrame(results)
        if not df.empty:
            #t0 = df['time_s'].min()
            df['wlm_time_s'] = df['wlm_time_s'] - t0
            df.set_index('wlm_time_s', inplace=True)

        return df


    def disconnect(self):
        if self.connection is None: 
            print(f"[{self.name}] Keine aktive Verbindung, überspringe control_ren.")
            return BaseDevice.disconnect(self)
        
        try:
            ## set the device to local mode (Go To Local) before disconnecting
            ## otherwise the device will stay in remote mode and will not respond to front panel commands
            self.connection.control_ren(6)
            ## dublicate of the command if code 6 is not correct 
            ## self.connection.control_ren(pyvisa.constants.VI_GPIB_REN_ADDRESS_GTL)
        except Exception as e:
            if sys.platform == 'linux':
                print(f"{self.GREEN}[{self.name}]: linux detected {self.RESET}")
                print(f"{self.YELLOW}[NOTE] Programmatic GTL is not supported by this USBTMC adapter on Linux ({e}).{self.RESET}")
                print(f"Please press the physical {self.GREEN}'ADDRESS/LOCAL'{self.RESET} button on the front panel of the Q8326.")
            else:
                print(f"[{self.name}] {self.RED}Go To Local error:{self.RESET} {e}")
                print(f"Please press the physical {self.GREEN}'ADDRESS/LOCAL'{self.RESET} button on the front panel of the Q8326.")
        return BaseDevice.disconnect(self)

if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
    print("---- starting Advanttest_Q8326.py ------")

    wlm = Q8326()
    # wlm.print_connections()

    def test_wlm_read(silent=True):
        """testing single wlm.read()"""
        time1 = time.perf_counter()
        readout = wlm.read(device_read_time=False, slow=False, silent=silent,)
        time2 = time.perf_counter()
        print(f"self.read() time:  {time2 - time1}")
        print(f"self.read() readout: {readout}")
        print("-"*50)

    def test_wlm_monitor(n=5, silent=True):
        """test stability of mesuremtns with and without avaraging
           n is number of measurements
        """
        print("\n----- averaged measurements -----")
        wlm.average_on(silent=silent)
        print(f"{wlm.average=}")
        print(wlm.wlm_monitor(5, silent=silent))

        print("\n----- fast measurements -----")
        wlm.average_off(silent=silent)
        print(f"{wlm.average=}")
        print(wlm.wlm_monitor(5, silent=silent))
        print("-"*50)

    def test_set_units(silent=True):
        print("\n----- testing unit setting -----")
        wlm.average_on(silent=silent)
        wlm.set_units(wlm.UNITS["WAVELENGTH"])
        readout_nm = wlm.read()
        # nm = readout_nm[wlm.UNITS["WAVELENGTH"]]
        print(f"{wlm.units=}")
        print(readout_nm)
        nm = readout_nm[wlm.units]
        print(f"{nm} {list(readout_nm)[-1]}")

        wlm.set_units(wlm.UNITS["FREQUENCY"])
        readout_THz = wlm.read()
        # f = readout_THz[wlm.UNITS["FREQUENCY"]]
        print(f"{wlm.units=}")
        f = readout_THz[wlm.units]
        print(f"{f} {list(readout_THz)[-1]}")
        
        if f != 0:
            x = 299792.458/f
            print(f"frequency corresponds to: {x} nm in vacuum")
        print("-"*50)

    def test_stb():
        print("\n----- test status byte reading -----")
        try: 
            print(f"[{wlm.name}] {wlm.GREEN}stb: {wlm.connection.stb}{wlm.RESET}")
        except pyvisa.errors.VisaIOError:
            print(f"[{wlm.name}] {wlm.RED}stb nicht verfügbar{wlm.RESET}")
        print("-"*50)


    try:
        wlm.connect(silent=True)

        test_wlm_read(silent=True)
        test_wlm_monitor(silent=True)
        test_set_units()
        test_stb()

        print(f"{wlm.GREEN} TEST PASSED {wlm.RESET}")

    except Exception as e:
        print(f"{wlm.RED} TEST FAILED {wlm.RESET}")
        print(e)

    finally:
        wlm.disconnect()

