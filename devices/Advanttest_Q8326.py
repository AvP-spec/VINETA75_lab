from base_device import BaseDevice
import pandas as pd
import pyvisa
import os
import time

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

    def __init__(self):
        super().__init__()
        self.hwid = "USB0::0x03EB::0x2065::GPIB_06_4423030363035131A1C0::INSTR"
        self.name = self.DEVICE_DIKT[self.hwid]
        self.port = self.hwid
        self.time_sleep = 0.05 # might work with 0.01


    def after_connect(self):
        print("Advantest_Q8326 after_connect()")
        self.connection.clear()
        time.sleep(self.time_sleep)
        self.send_command("M1")      #"Sample Mode HOLD",
        self.flush_buffer_GPIB()
        self.send_command("F1")    # function LASER for measurement of a laser wavelength/frequency
        self.send_command("W0")    # "set wavelength range: 480-1000 nm",
        self.send_command("RF0")   # drift off
        self.send_command("CA0")   # set altitude 0m - sea level
        self.send_command("B1")    # set Beap when error
        self.send_command("A1")    # average on
        self.send_command("RE0")   # "RSOLUTION MAX", # 0.0001 nm / 10 MHz,
        self.average = "ON"


        return self
    

    def send_command(self, cmd:str, silent=True, slow=True):
        """
        Sends a command to the Advantest Q8326 and checks the Status Byte (STB).
        If the device reports an error (stb != 0), it flushes the buffer and retries once.

        STB Interpretation Table:
        -  0 (0000 0000): O.K. Device is idle and ready.
        - 64 (0100 0000): RQS (Request Service) bit active.
        - 65 (0100 0001): Data Ready. Measurement finished, data waiting in buffer.
        - 66 (0100 0010): Syntax Error. Command not recognized.
        - 67 (0100 0011): Syntax Error + Data. Error occurred, buffer not empty.
        """
        
        cmd_name = self.CMD_DIKT.get(cmd, "cmd is not in self.CMD_DIKT")

        def get_status_msg(stb):
            ''' interpreate status byte and get massage'''
            if stb == 0: return f"{self.GREEN}O.K.{self.RESET}"
            if stb in [66, 67]: return f"{self.RED}Syntax Error{self.RESET}"
            if stb == 65: return f"{self.BLUE}Data in buffer{self.RESET}"
            if stb == 64: return f"{self.YELLOW}RQS bit only{self.RESET}"
            return f"{self.RED}Unknown State{self.RESET}"

        self.connection.write(cmd)
        if slow: time.sleep(self.time_sleep)
        status_byte = self.connection.stb
        status = get_status_msg(status_byte)
        print(f"[{self.name}] send_command({self.BLUE}{cmd}: {cmd_name}"
              f"{self.RESET}) = {status}, {status_byte=}")
        
        self.flush_buffer_GPIB(silent=silent)

        if status_byte != 0:
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
            
            ## commands DCL and clear() was not working
            ## commented for further investigations
            # print("DCL")
            # self.connection.write("DCL") # "C"
            # print(f"waite {self.time_sleep} s")
            # time.sleep(self.time_sleep)
            # status_byte = self.connection.stb
            # print(f"after 'DCL' {status_byte=}")
            # print()
            
            # print("clear()")
            # self.connection.clear()
            # print(f"waite {self.time_sleep} s")
            # time.sleep(self.time_sleep)
            # status_byte = self.connection.stb
            # print(f"after clear {status_byte=}")
            # print()

            print("write(cmd)")
            self.connection.write(cmd)
            print(f"waite {self.time_sleep} s")
            time.sleep(self.time_sleep)
            status_byte = self.connection.stb
            print(f"[{self.name}] send_command({self.BLUE}{cmd}: {cmd_name}"
                  f"{self.RESET}) = {status}")
            
            self.flush_buffer_GPIB(silent=False)
            
        return self


    def flush_buffer_GPIB(self, silent=False):
        '''
        critical for stable and synchronysed connectoin of the instrument with pyvisa 
        silent=False will print the buffer content
        '''
        self.connection.timeout = 500
        for _ in range(10):
            try:
                junk = self.connection.read_raw()
                print(f"Flushed junk No.{_}: {junk}")
            except pyvisa.errors.VisaIOError:
                if not silent:
                    print(f"[{self.name}]: {self.GREEN} buffer is empty {self.RESET}")
                break
        self.connection.timeout = self.CONNECTION_SETTINGS["timeout"]

        return self
    

    def average_on(self):
        self.send_command("A1")
        self.send_command("RE0")
        self.average = "ON"
        return self
    
    def average_off(self):
        self.send_command("A0")
        self.send_command("RE1")
        self.average = "OFF"
        return self

    def read(self, silent=True):
        self.flush_buffer_GPIB(silent=silent) # takes 0.6 sec
        start_time = time.perf_counter()
        value = self.connection.query("E")
        end_time = time.perf_counter()
        
        return {
            "time_s": start_time,
            "wavelength": value,
            "duration_s": end_time - start_time
              } 
    
    def wlm_monitor(self, n_measurements=1, sleep=None, silent=False):
        if sleep is None:
            sleep= self.time_sleep
        
        results = []
        for i in range(n_measurements):
            if not silent:
                print(f"wlm_monitor measurement No.{i}")
            results.append(self.read())
            time.sleep(sleep)
        ## for fast version
        # results = [self.read() for i in range(n_measurements)]
        df = pd.DataFrame(results)
        if not df.empty:
            t0 = df['time_s'].min()
            df['time_s'] = df['time_s'] - t0
            df.set_index('time_s', inplace=True)

        return df


    def disconnect(self):
        try:
            self.connection.control_ren(6)
            ## dublicate of the command if code 6 is not correct 
            ## self.connection.control_ren(pyvisa.constants.VI_GPIB_REN_ADDRESS_GTL)
        except Exception as e:
            print(f"[{self.name}] {self.RED}Go To Local error:{self.RESET} {e}")
        return BaseDevice.disconnect(self)

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("hallo")

    wlm = Q8326()
    wlm.print_connections()
    wlm.connect()
    print(wlm.connection.query("E"))
    print(wlm.connection.stb)
    
    print("----- averaged measurements -----")
    print(f"{wlm.average=}")
    print(wlm.wlm_monitor(5))

    print("----- fast measurements -----")
    wlm.average_off()
    print(f"{wlm.average=}")
    print(wlm.wlm_monitor(5))

    time1 = time.perf_counter()
    print(wlm.read())
    time2 = time.perf_counter()
    print(time2 - time1)
    
    print("----- averaged measurements -----")
    wlm.average_on()
    time1 = time.perf_counter()
    print(wlm.read())
    time2 = time.perf_counter()
    print(time2 - time1)


    wlm.disconnect()
   

