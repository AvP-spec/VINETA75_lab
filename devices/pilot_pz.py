''' 
v02->v03  working version
re-writing PilotPZ500 and set_value() - archetectur change
implemented *OPC? instead of time.sleep(0.1)
'''

from base_device import BaseDevice
import pyvisa
import time
import os
import math
import pandas as pd

class PilotPZ(BaseDevice):
    CONNECTION_SETTINGS = {
        'baud_rate': 9600,
        'data_bits': 8,
        'stop_bits': pyvisa.constants.StopBits.one, # variants: one, two
        'parity': pyvisa.constants.Parity.none,     # variants: none, even, odd
        'read_termination': '\r\n', # Stefan: '\r\n', manual: '\r'
        'write_termination': '\r',
        'timeout': 3000 # 1 sec
    }
    
    # list of command for reseting the instument
    # the actual settings belongs to device subclass, here is a place holder
    DEFOLT_SETTINGS = ["*IDN?"] 


    def __init__(self):
        super().__init__()
        self.time_sleep = 0.01 # deley after read/write command to the port
        self.current = None
        self.temperature = None
        self.piezo = None
        self.laser_mode = None


    def after_connect(self):
        print("=== PilotPZ after_connect() ===")
        
        try:
            # claer instrument
            self.connection.write("*CLS")
            self.flush_buffer(silent=True)
            self.send_command(":SYSTem:Echo OFF")
            self.send_command(":SYSTem:ACKnowledge ON")
            self.send_command("*IDN?")
        except Exception as e:
            print("IDN query failed:", e)
        print("=== PilotPZ after_connect() endend ===")
        return self
    
    ##### general functions #######
    def flush_buffer(self, silent=False):
        '''
        critical for stable and synchronysed connectoin of the instrument with pyvisa 
        silent=False will print the buffer content
        '''
        n = self.connection.bytes_in_buffer
        if n:
            buffer_ = self.connection.read_bytes(n)
            if not silent:
                print(f"buffer = {self.RED}{buffer_ }{self.RESET}" )
        else:
            if not silent:
                print(f"{self.GREEN}bytes in buffer = {n}{self.RESET}")
        return self


    def send_command(self, cmd:str, silent=True):
        ''' the most general function for communication with instrument'''
        x = self.connection.query(cmd)
        print(f"[{self.name}] send_command({self.BLUE}{cmd}{self.RESET}) = {x}")
        # time.sleep(self.time_sleep) ## works well, but *OPS? is faster, left to fix stability problems
        ops_ = self.connection.query("*OPC?")
        if not silent:
            print(f"command status ops = {ops_}")
        self.flush_buffer(silent=silent)
        return self 


    def read_value(self, cmd:str, silent=True):
        ''' similar to send command, but returns instrument response '''
        response = self.connection.query(cmd) 
        time.sleep(self.time_sleep)
        # print(f"{cmd}: {response}" )
        self.flush_buffer(silent=silent)
        return response


    def _set_value(self, parameter_dickt, value:float=None, unit:str=None, silent=True):
        '''
        internal function, parameter_dickt should be defined, see: 
        self.current, self.temperature, self.piezo in PilotPZ500 class
        '''
        ## unpack dickt
        name = parameter_dickt["name"]
        cmd_base = parameter_dickt["cmd"]
        unit_map = parameter_dickt["unit_map"]
        if unit not in unit_map:
            print(f"{self.RED}Invalid unit '{unit}'. Please use unit='A', '[A]', 'mA', or '[mA]'.{self.RESET}")
            return self
        limits = parameter_dickt["limits"]
        if not limits:
            print(f"{self.RED} Limits of {name} are not defined.{self.RESET} ")
            return self
        ## prepare command (cmd)
        value_ = value * unit_map[unit] # transfer to defoult instrument units
        min_ = limits["min"] # * unit_map[limits["unit"]] ## = 1
        max_ = limits["max"] # * unit_map[limits["unit"]] ## = 1
        res_ = limits["resolution"]
        precision = int(round(abs(math.log10(res_))))
        ## send the command
        if min_ <= value_ <= max_:
            cmd = f"{cmd_base} {value_:.{precision}f}"
            self.send_command(cmd, silent=silent)

        else:
            print(f"{self.RED}{name} {value} {unit} is out of range [{min_}-{max_}] {limits['unit']}{self.RESET}")

        return self
    

    ###### read functions ######
    def read_current(self, silent=True):
        return self.read_value(":Laser:CURRent?", silent=silent)
    
    def read_setcurrent(self, silent=True):
        return self.read_value(":Laser:CURRent:set?", silent=silent)
    
    def read_temperature(self, silent=True):
        return self.read_value(":TEC:TEMPerature?", silent=silent)
    
    def read_settemperature(self, silent=True):
        return self.read_value(":TEC:TEMPerature:Set?", silent=silent)
    
    def read_piezo(self, silent=True):
        return self.read_value(":Piezo:OFFSet?", silent=silent)
    
    def read_power(self, silent=True):
        return self.read_value(":Laser:POWer?", silent=silent)
    
    def read_pdiode_current(self, silent=True):
        return self.read_value(":PDiode:CURRent?", silent=silent)
    
    def read_mode(self, silent=True):
        return self.read_value(":Laser:MODe?", silent=silent)
    
    def read_status(self, silent=True):
        return self.read_value(":Laser:STATus?", silent=silent)
    
    def read_laser(self):
        start_time = time.perf_counter()
        current= self.read_current()
        temperature= self.read_temperature()
        piezo = self.read_piezo()
        end_time = time.perf_counter()
        return {
            "time_s": start_time,
            "duration": end_time - start_time,
            "current_A": current,
            "temperature_C": temperature,
            "piezo_off_set_V": piezo
        }
    
    def laser_monitor(self, n_measurements, sleep=None, silent=False):
        if sleep is None:
            sleep= self.time_sleep

        results = []
        for i in range(n_measurements):
            if not silent:
                print(f"laser_monitor measurement No.{i}")
                results.append(self.read_laser())
                time.sleep(sleep)

        df = pd.DataFrame(results)
        if not df.empty:
            t0 = df['time_s'].min()
            df['time_s'] = df['time_s'] - t0
            df.set_index('time_s', inplace=True)

        return df      

    ####### set functions #######
    def set_defoults(self):
        for cmd in self.DEFOLT_SETTINGS:
            self.send_command(cmd)
        return self
    
    def set_current(self, value:float, unit:str=None, silent=True):
        self._set_value(self.current, value=value, unit=unit, silent=silent)
        return self
    
    def set_temperature(self, value:float, unit:str=None, silent=True):
        self._set_value(self.temperature, value=value, unit=unit, silent=silent)
        return self
    
    def set_piezo(self, value:float, unit:str=None, silent=True):
        self._set_value(self.piezo, value=value, unit=unit, silent=silent)
        return self
    
    ####### switch functions #######
    def switch_laser_mode(self, silent=True):
        mode = {"IMODE": "PMODE", "PMODE": "IMODE"}
        actual_mode = self.read_mode()
        set_mode = mode[actual_mode]
        cmd = f"Laser:MODe {set_mode}"
        self.send_command(cmd=cmd, silent=silent)
        actual_mode = self.read_mode()
        print(f"the laser switched to {self.BLUE}{actual_mode}{self.RESET}")
        return self

    def switch_on(self, silent=True):
        # self.connection.timeout = 10_000
        self.send_command("Laser:STATus ON")
        while self.connection.query("Laser:STATus?") != "ON":
            time.sleep(self.time_sleep)

        # time.sleep(5)
        status = self.read_status(silent=silent)
        print(f"{self.name} is {self.BLUE}{status}{self.RESET}")
        return self

    def switch_off(self, silent=True):
        self.send_command("Laser:STATus OFF")
        status = self.read_status(silent=silent)
        print(f"{self.name} is {self.BLUE}{status}{self.RESET}")
        return self

class PilotPZ500(PilotPZ):
    DEFOLT_SETTINGS = [
                       ":Laser:CURRent 0.0515",
                       ":Laser:MODe IMODE",
                       ":TEC:TEMPerature 16", 
                       ":Piezo:OFFSet 2",
                       ]
    

    def __init__(self):
        super().__init__()
        self.hwid = "VID:PID:SER = 0403:6001:6"
        self.name = self.DEVICE_DIKT[self.hwid]
        self.current = {
            "limits": {"max": 0.6, "min": 0, "unit": "[A]", "resolution": 0.1E-3},
            "unit_map": {"A": 1, "[A]": 1, "mA": 0.001, "[mA]": 0.001},
            "cmd": ":Laser:CURRent",
            "name": f"{self.BLUE}current{self.RESET}"
        }
        self.temperature = {
            "limits": {"max": 30, "min": -5, "unit": "[C]", "resolution": 1E-3},
            "unit_map": {"C": 1, "[C]": 1, },
            "cmd": ":TEC:TEMPerature",
            "name": f"{self.BLUE}temperature{self.RESET}"
        }
        self.piezo = {
            "limits": {"max": 13.5, "min": -13.5, "unit": "[V]", "resolution": 1E-3},
            "unit_map": {"V": 1, "[V]": 1, "mV": 0.001, "[mV]": 0.001},
            "cmd": ":Piezo:OFFSet",
            "name": f"{self.BLUE}piezo offset{self.RESET}"
        }


if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    master_diode = PilotPZ500()
    master_diode.print_connections()
    master_diode.get_COM_port().connect()
    print()
    
    
    def scan_laser_parameters(laser:object):
        print(f"=== {laser.GREEN} scan_laser_parameters() {laser.RESET}===")
        laser.send_command(":Laser:STATus?")
        laser.send_command(":Laser:POLarity?")
        ## laser current 
        print(f"{laser.GREEN} Current {laser.RESET}")
        print("actual current =", laser.read_current(silent=False))
        print("actual set current = ", laser.read_setcurrent())
        laser.send_command(":SYSTem:BAUDrate?", silent=False)
        laser.send_command(":Laser:ILIMit? MIN", silent=False)
        laser.send_command(":Laser:ILIMit? MAX", silent=False)
        laser.send_command(":Laser:MODe?", silent=False)
        laser.send_command(":Laser:CURRent:Set?", silent=False)
        laser.send_command(":Laser:POWer?", silent=False)
        laser.send_command(":Laser:TEC:Required?")
        laser.send_command("Laser:IU:ENAble?")
        laser.send_command(":PDiode:CURRent?")
        laser.send_command(":CCoupling:ENAble?")
        ## laser temperature
        print(f"{laser.GREEN} temperature {laser.RESET}")
        print("actual temperature =", laser.read_temperature())
        laser.send_command(":TEC:ENAble?")
        laser.send_command(":TEC:ILIMit? MAX")
        laser.send_command(":TEC:ILIMit? MIN")
        laser.send_command(":TEC:TEMPerature:Set? MAX")
        laser.send_command(":TEC:TEMPerature:Set? MIN")
        laser.send_command(":TEC:TEMPerature:LIMit:MAX?")
        laser.send_command(":TEC:TEMPerature:LIMit:MIN?")
        laser.send_command(":TEC:WATch:ENAble?")
        ## piezo
        print(f"{laser.GREEN} Piezo {laser.RESET}")
        print("actual piezo offset =", laser.read_piezo())
        laser.send_command(":Piezo:ENAble?")
        laser.send_command(":Piezo:OFFSet?")
        laser.send_command(":Piezo:OFFSet? MAX")
        laser.send_command(":Piezo:OFFSet? MIN")
        laser.send_command(":Piezo:FREQuency:GENerator?")
        print(f"=== {laser.GREEN} scan_laser_parameters() ended {laser.RESET}===")
        print()
        return None
    
   # scan_laser_parameters(master_diode)

    def test_set_functions(laser:object):
        print(f"=== {laser.GREEN} test_set_functions {laser.RESET}===")
        laser.set_current(50, "mA")
        print("actual set_current = ", laser.read_setcurrent())
        print("actual current = ", laser.read_current())
        laser.set_temperature(15, "C")
        print("actual set_temperature = ", laser.read_settemperature())
        print("actual temperature = ", laser.read_temperature())
        time.sleep(1)
        laser.set_defoults()
        print("actual current = ", laser.read_setcurrent())
        print(f"=== {laser.GREEN} test_set_functions() ended {laser.RESET}===")
        print()

   # test_set_functions(master_diode)

    def read_actual_parameters(laser:object):
        print("actual status = ", laser.read_status())
        print("actual current = ", laser.read_current())
        print("actual temperature = ", laser.read_temperature())
        print("actual power = ", laser.read_power())
        print("actual temperature = ", laser.read_pdiode_current())

    # read_actual_parameters(master_diode)

    def test_switch_functions(laser:object):
        print(f"=== {laser.GREEN} test_switch_functions {laser.RESET}===")
        # laser.switch_laser_mode(laser) 
        read_actual_parameters(laser)
        laser.switch_on()
        time.sleep(1)
        read_actual_parameters(laser)
        laser.switch_off()

        print(f"=== {laser.GREEN} test_switch_functions() ended {laser.RESET}===")
        print()

    # test_switch_functions(master_diode)

    def test(laser:object):
        print(laser.connection.timeout)
        laser.connection.timeout = 5_000
        print(laser.connection.timeout)
    #test(master_diode)

    def test_laser_monitor(laser:object):
        laser.switch_on()
        results = laser.laser_monitor(n_measurements=5)
        laser.switch_off()
        print("\n", results)

    test_laser_monitor(master_diode)

    master_diode.disconnect()