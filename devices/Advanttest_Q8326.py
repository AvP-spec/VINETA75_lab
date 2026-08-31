# WLM class new version
# \devices\Advanttest_Q8326.py
from base_device import BaseDevice
import pandas as pd
import pyvisa
import os
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
        self.name = self.DEVICE_DIKT[self.hwid]
        self.port = self.hwid
        self.time_sleep = 0.1 # might work with 0.01
        self.units = None
        ## whether the connection/adapter supports Serial Poll (.stb).
        ## None = not tested yet, set to True/False on first send_command() call.
        self.stb_available = None


    def after_connect(self, silent=True):
        print("Advantest_Q8326 after_connect()")
        try: 
            self.connection.clear()
        except pyvisa.errors.VisaIOError as e: 
            print(f"[{self.name}] clear() nicht unterstützt, übersprungen: {e}")
        time.sleep(self.time_sleep)
        slow = False
        print("1", end="")
        self.send_command("M1", silent=silent, slow=slow)      #"Sample Mode HOLD",
        print("1", end="")
        self.flush_buffer_GPIB(silent=silent)
        print("1", end="")
        self.send_command("F1", silent=silent, slow=slow)    # function LASER for measurement of a laser wavelength/frequency
        print("1", end="")
        self.send_command("W0", silent=silent, slow=slow)    # "set wavelength range: 480-1000 nm",
        print("1", end="")
        self.send_command("RF0", silent=silent, slow=slow)   # drift off
        print("1", end="")
        self.send_command("CA0", silent=silent, slow=slow)   # set altitude 0m - sea level
        print("1", end="")
        self.send_command("B1", silent=silent, slow=slow)    # set Beap when error
        print("1", end="")
        self.send_command("A1", silent=silent, slow=slow)    # average on
        print("1", end="")
        self.send_command("RE0", silent=silent, slow=slow)   # "RSOLUTION MAX", # 0.0001 nm / 10 MHz,
        print("1", end="")
        self.set_units(self.UNITS["WAVELENGTH"], silent=silent, slow=slow)
        print("1", end="")
        
        print(f"\n{self.BLUE}{self.name}{self.GREEN} connected" 
                f" on port {self.BLUE}{self.port}{self.RESET} \n")

        return self
    

    def send_command(self, cmd:str, silent=False, slow=False):
        """
        Sends a command to the Advantest Q8326 and checks the Status Byte (STB).
        If the device reports an error (stb != 0), it flushes the buffer and retries once.

        STB Interpretation Table:
        -  0 (0000 0000): O.K. Device is idle and ready.
        - 64 (0100 0000): RQS (Request Service) bit active.
        - 65 (0100 0001): Data Ready. Measurement finished, data waiting in buffer.
        - 66 (0100 0010): Syntax Error. Command not recognized.
        - 67 (0100 0011): Syntax Error + Data. Error occurred, buffer not empty.

        Note: some GPIB-over-USB adapters do not support Serial Poll (.stb).
        In that case status_byte falls back to 0 ("stb n/a") instead of raising,
        see self.stb_available.
        """
        
        cmd_name = self.CMD_DIKT.get(cmd, "cmd is not in self.CMD_DIKT")

        def get_status_msg(stb):
            ''' interpreate status byte and get massage'''
            if stb == 0: return f"{self.GREEN}O.K.{self.RESET}"
            if stb in [66, 67]: return f"{self.RED}Syntax Error{self.RESET}"
            if stb == 65: return f"{self.BLUE}Data in buffer{self.RESET}"
            if stb == 64: return f"{self.YELLOW}RQS bit only{self.RESET}"
            return f"{self.RED}Unknown State {stb}{self.RESET}"

        self.connection.write(cmd)

        if slow: 
            time.sleep(self.time_sleep)
            print(f"Q8326.send_command(): wlm.time_sleep = {self.time_sleep}")

        try:
            status_byte = self.connection.stb
            if self.stb_available is None:
                self.stb_available = True
            status = get_status_msg(status_byte)
        except pyvisa.errors.VisaIOError:
            if self.stb_available is None:
                self.stb_available = False
                print(f"[{self.name}] {self.YELLOW}stb nicht verfügbar "
                      f"– Syntaxfehler-Erkennung deaktiviert{self.RESET}")
            status_byte = 0
            status = f"{self.YELLOW}stb n/a{self.RESET}"

        if not silent:
            print(f"[{self.name}] send_command({self.BLUE}{cmd}: {cmd_name}"
                  f"{self.RESET}) = {status}, {status_byte=}")
        
        self.flush_buffer_GPIB(silent=silent)

        if status_byte != 0:
            print(f"--- {self.YELLOW}second attempt to send command{self.RESET} ---")
            try:
                status_byte = self.connection.stb
            except pyvisa.errors.VisaIOError:
                status_byte = 0
            print(f"initial {status_byte=} \n")
            
            ## the read command to clean the status byte
            print("self.read()")
            print(self.read())
            print(f"waite {self.time_sleep} s")
            time.sleep(self.time_sleep)
            try:
                status_byte = self.connection.stb
            except pyvisa.errors.VisaIOError:
                status_byte = 0
            print(f"after 'read' {status_byte=}\n")

            print("write(cmd)")
            self.connection.write(cmd)
            print(f"waite {self.time_sleep} s")
            time.sleep(self.time_sleep)
            try:
                status_byte = self.connection.stb
                status = get_status_msg(status_byte)
            except pyvisa.errors.VisaIOError:
                status_byte = 0
                status = f"{self.YELLOW}stb n/a{self.RESET}"
            print(f"[{self.name}] send_command({self.BLUE}{cmd}: {cmd_name}"
                  f"{self.RESET}) = {status}")
            
            self.flush_buffer_GPIB(silent=False)
            
        return self


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
        """
        Read wavelength with optional timing metadata.

        Returns the unit-tagged key ('nm' or 'THz', used by lif_avp.py's
        live plotter) AND, for backward compatibility with managers/lif.py
        (which expects the historic interface), a 'wavelength' key holding
        the raw value in meters -- only added while in wavelength/'nm' mode,
        since that's the only mode where 'wavelength' is a meaningful name.
        """
        if slow:
            self.flush_buffer_GPIB(silent=silent) # takes 0.6 sec

        factor = {"nm": 1E9, "THz": 1E-12}
        t0 = time.perf_counter()
        value = self.connection.query("E")
        dt = time.perf_counter() - t0

        ## the instrument returns its native SI value here:
        ## meters when in wavelength/'nm' mode, Hz when in frequency/'THz' mode
        raw_si = float(value)

        readout = {}
        if device_read_time:
            readout.update({'wlm_time_s': t0, 
                            'wlm_duration_s': dt}) 
        readout[str(self.units)] = raw_si*factor[self.units]

        ## backward-compat key expected by managers/lif.py
        if self.units == "nm":
            readout['wavelength'] = raw_si

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
            print(f"[{self.name}] {self.RED}Go To Local error:{self.RESET} {e}")
        return BaseDevice.disconnect(self)

if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
    print("---- starting Advanttest_Q8326.py ------")

    wlm = Q8326()
 #   wlm.print_connections()
    wlm.connect()

    # test pyvisa query and status byte avalibility (prblems with Lynux?)
    print()
    print(f"direct pyvisa query wavelength: {wlm.connection.query('E')}")
    try: 
        print(f"[{wlm.name}] {wlm.GREEN}stb: {wlm.connection.stb}{wlm.RESET}")
    except pyvisa.errors.VisaIOError:
        print(f"[{wlm.name}] {wlm.RED}stb nicht verfügbar{wlm.RESET}")

    # test self.read() method
    time1 = time.perf_counter()
    readout = wlm.read(device_read_time=False, slow=False, silent=True,)
    time2 = time.perf_counter()
    print(f"self.read() time:  {time2 - time1}")
    print(f"self.read() readout: {readout}")

    # test stability of the averaged measurements
    print("\n----- averaged measurements -----")
    wlm.average_on()
    print(f"{wlm.average=}")
    print(wlm.wlm_monitor(5))

    # test stability of the single measurements
    print("\n----- fast measurements -----")
    wlm.average_off()
    print(f"{wlm.average=}")
    print(wlm.wlm_monitor(5))

    # test unit setting
    print("\n----- testing unit setting -----")
    wlm.average_on()
    wlm.set_units(wlm.UNITS["WAVELENGTH"])
    print(wlm.read())
    wlm.set_units(wlm.UNITS["FREQUENCY"])
    result = wlm.read()
    print(result)
    f = result[wlm.units]
    if f != 0:
        x = 299792.458/f
        print(f"frequency in vacuum nm: {x} nm")

    wlm.wlm_monitor(n_measurements=5, silent=False)


    wlm.disconnect()