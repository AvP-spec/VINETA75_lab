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
import matplotlib.pyplot as plt

from pathlib import Path
import sys
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.plt_styler_avp import PlotStyler

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
        self.IDN = None


    def after_connect(self, silent=True):
        if not silent:
            print("\n=== PilotPZ after_connect() ===")
        
        try:
            # claer instrument
            self.connection.write("*CLS")
            self.flush_buffer(silent=silent)
            self.send_command(":SYSTem:Echo OFF", silent=silent)
            self.send_command(":SYSTem:ACKnowledge ON", silent=silent)
            # self.send_command("*IDN?")
        except Exception as e:
            print(f"{self.RED}IDN query failed:{self.RESET}", e)
        if not silent:
            print("=== PilotPZ after_connect() endend ===")

        return self
    
    def connect(self, silent=True):
        '''
        Overrides BaseDevice.connect to handle multiple devices with identical HWIDs.
        Iterates through all ports matching the Pilot series HWID and validates 
        the connection by comparing the '*IDN?' response with the expected model.
        '''
        if not silent:
            print("=+=+= PilotPZ.connect() =+=+=")
        if not self.IDN:
            print(f"{self.RED} Select subclass PilotPZ500 or PilotPC4000{self.RESET}")
            return self
        device_list = self._get_COM_connections()
        # print(device_list)
        # print(self.hwid)
        pilot_list = [dev for dev in device_list if self.hwid in dev[2]]    # <-- dev[2] kann jetzt VID:PID:SER = 0403:6001:None sein
        # print(pilot_list)
        for pilot in pilot_list:
            self.port = self._com_to_visa(pilot[0])
            try:
                BaseDevice.connect(self, silent=silent)
                IDN_ = self.read_value("*IDN?")
                if not silent:
                    print(f"{IDN_=}")
                if IDN_ == self.IDN:
                    print(f"\n{self.BLUE}{self.name}{self.GREEN} connected" 
                          f" on port {self.BLUE}{self.port}{self.RESET} \n")
                    if not silent:
                        print("=+=+= PilotPZ.connect() ended =+=+=")
                    return self
                else:
                    print(f"{self.YELLOW} Wrong device on {self.port}, disconnecting..."
                          f"{self.RESET}")
                    self.disconnect()

            except Exception as e:
                print(f"Port {self.port} failed: {e}")
                continue
        print(f"\n{self.RED}PilotPZ.connect() ERROR:{self.name} NOT FOUND!{self.RESET}")
        print(f"Please check if the device is POWERED ON and cables are connected.\n")

    ##### general functions #######
    def flush_buffer(self, silent=False):
        '''
        critical for stable and synchronysed connection of the instrument with pyvisa 
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


    def send_command(self, cmd:str, silent=False):
        ''' the most general function for communication with instrument'''
        x = self.connection.query(cmd)
        # time.sleep(self.time_sleep) ## works well, but *OPS? is faster, left to fix stability problems
        ops_ = self.connection.query("*OPC?")
        if not silent:
            print(f"[{self.name}] send_command({self.BLUE}{cmd}{self.RESET}) = {x}")
            print(f"command status ops = {ops_}")
        self.flush_buffer(silent=silent)
        return self 


    def read_value(self, cmd, silent=True):
        if self.connection is None:
            print(f"Error in read_value(): Device not connected")
            return None  # oder raise ConnectionError(...)
        response = self.connection.query(cmd)
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
    
    def read_laser(self, device_read_time=True):
        '''read all Pilot state parameters'''
        t0 = time.perf_counter()
        data = {
            "current_A": float(self.read_current()),
            "photo_diode_current_A": float(self.read_pdiode_current()),
            "temperature_C": float(self.read_temperature()),
            "set_current_A": float(self.read_setcurrent()),
            "set_temperature_C": float(self.read_settemperature()),
            "power": float(self.read_power()),
            "laser_mode": self.read_mode()
        }
        if self.piezo: 
            data["piezo_off_set_V"] = self.read_piezo()

        dt = time.perf_counter() - t0 

        result = {}
        if device_read_time:
            result.update( {"time_s": t0,
                            "duration_s": dt })
            
        result.update(data)
    
        return result


    def laser_monitor_df(self, n_measurements=5, sleep=None, silent=False):
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
    

    def laser_monitor(self, n_measurements=5, sleep=None, plot=True, silent=False):
        if sleep is None:
            sleep= self.time_sleep

        results = []
        if plot:
            time_x = []
            current = []
            temperature = []
            current_drift = []
            temperature_drift = []
            photo_diode = []
            power = []
            plt.ion()
            fig, axs = plt.subplots(2, 3, figsize=(6, 5), facecolor="#AEDB0D")
                
            ax_current, ax_temperature = axs[0, 0], axs[0, 1]
            ax_diff_curr, ax_diff_temp = axs[1, 0], axs[1, 1]
            ax_photo, ax_power = axs[0, 2], axs[1, 2]

            line_curr, = ax_current.plot([], [], 'b-o', label='Current (A)')
            line_temp, = ax_temperature.plot([], [], 'r-o', label='Temperature (C)')
            line_d_curr, = ax_diff_curr.plot([], [], 'g--', label='Δ Current')
            ax_diff_curr.axhline(0, color='black', linewidth=1, linestyle='-')
            line_d_temp, = ax_diff_temp.plot([], [], 'm--', label='Δ Temperature')
            ax_diff_temp.axhline(0, color='black', linewidth=1, linestyle='-')

            line_photo, = ax_photo.plot([], [], 'b-o', label='')
            line_power, = ax_power.plot([], [], 'b-o', label='')

            for ax in axs.flat:
                PlotStyler.set_scale_steps(ax)
                ax.set_facecolor("#ecdd08ff") # ax colour
                ax.grid(True, linestyle=':', alpha=0.6) 
                ax.set_xlabel('Time (s)')
                ax.legend(loc='upper right')

            ax_current.set_title("Current [mA]")
            ax_temperature.set_title("Temperature [C]")
            ax_diff_curr.set_title("Current drift (Set - Actual) [mA]")
            ax_diff_temp.set_title("Temperature drift (Set - Actual)[C]")
            ax_photo.set_title("Photo diode current [mA]")
            ax_power.set_title("Laser power [W?]")

            plt.tight_layout() # Чтобы графики не наплывали друг на друга
            plt.show()

        t0 = None
        for i in range(n_measurements):
            if not silent:
                print(f"laser_monitor measurement No.{i}")

            data = self.read_laser()
            if t0 is None:
                t0 = data['time_s']
            data["time_s"] -= t0
            results.append(data)

            if plot:
                time_x.append(data["time_s"])
                current.append(data["current_A"]*1E3)
                temperature.append(data["temperature_C"])
                current_drift.append((data["current_A"] - data["set_current_A"])*1E3)
                temperature_drift.append(data["temperature_C"] - data["set_temperature_C"])
                photo_diode.append(data["photo_diode_current_A"]*1E3)
                power.append(data["power"])
                line_curr.set_data(time_x, current)
                line_d_curr.set_data(time_x, current_drift)
                line_temp.set_data(time_x, temperature)
                line_d_temp.set_data(time_x, temperature_drift)
                line_photo.set_data(time_x, photo_diode)
                line_power.set_data(time_x, power)
                for ax in axs.flat:
                    ax.relim()
                    ax.autoscale_view()
                plt.pause(0.01)

            time.sleep(sleep)

        plt.ioff()
        print("laser_monitor() finished. Close the plot window to exit.")
        df = pd.DataFrame(results)
        plt.show(block=True)
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

    def switch_on(self, silent=True, timeout=10):
        # self.connection.timeout = 10_000
        self.send_command("Laser:STATus ON", silent=silent)
        start_time = time.perf_counter()
        while True:
            if self.connection.query("Laser:STATus?") == "ON":
                status = self.read_status(silent=silent)
                print(f"{self.name} is {self.BLUE}{status}{self.RESET}")
                return self
            if (time.perf_counter() - start_time) > timeout:
                raise TimeoutError(f"Laser {self.RED}{self.name}{self.RESET} did not turn on within {timeout}s")
            time.sleep(self.time_sleep)
        


    def switch_off(self, silent=True):
        self.send_command("Laser:STATus OFF", silent=silent)
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
        self.hwid = "VID:PID = 0403:6001"   # <-- ist in base_devise geregelt
        
        self.IDN = "Sacher Lasertechnik, PilotPC 500, SN14092044, SW V8.00 HW V9.0 PZ V8.0"
        self.name = "PilotPC 500"
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


class PilotPC4000(PilotPZ):
    DEFOLT_SETTINGS = [
                       ":Laser:CURRent 0.3020",
                       ":Laser:MODe IMODE",
                       ":TEC:TEMPerature 17", 
                       ]

    def __init__(self):
        super().__init__()
        self.hwid = "VID:PID = 0403:6001"   # <-- ist in base_devise geregelt

        self.name = "PilotPC4000"
        self.IDN = "Sacher Lasertechnik, PilotPC 4000, SN15093017, SW V8.00 HW V9.0"
        self.current = {
             "limits": {"max":4.100, "min": 0.000, "unit": "[A]", "resolution": 0.1E-3},
            "unit_map": {"A": 1, "[A]": 1, "mA": 0.001, "[mA]": 0.001},
            "cmd": ":Laser:CURRent",
            "name": f"{self.BLUE}current{self.RESET}"
        }
        self.temperature = {
            "limits": {"max":30.000, "min": -5.000, "unit": "[C]", "resolution": 1E-3},
            "unit_map": {"C": 1, "[C]": 1, },
            "cmd": ":TEC:TEMPerature",
            "name": f"{self.BLUE}temperature{self.RESET}"
        }


if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    master_diode = PilotPZ500()
    master_diode.connect(silent=True)
    amplifier_diode = PilotPC4000()
    amplifier_diode.connect()
    print()


    def read_limits(laser:object):
        if laser.connection is None:
            print("read_limits() aborted: Device not connected")
            return
        print(f"\n=== {laser.GREEN} scan_laser_parameters() {laser.RESET}===")
        I_max = laser.read_value(":Laser:ILIMit? MAX")
        I_min = laser.read_value(":Laser:ILIMit? MIN")
        # resolution is from manual
        print(
            f"{laser.MAGENTA} current limits {laser.RESET} \n"
            f' "limits": {{"max":{I_max}, "min": {I_min}, "unit": "[A]", "resolution": 0.1E-3}}'
        )
        T_max = laser.read_value(":TEC:TEMPerature:Set? MAX")
        T_min = laser.read_value(":TEC:TEMPerature:LIMit:MIN?")
        print(
            f"{laser.MAGENTA} temperature limits {laser.RESET} \n"
            f' "limits": {{"max":{T_max}, "min": {T_min}, "unit": "[C]", "resolution": 1E-3}}'
        )
        if laser.piezo:
            v_max = laser.read_value(":Piezo:OFFSet? MAX")
            v_min = laser.read_value(":Piezo:OFFSet? MIN")
            print(
                f"{laser.MAGENTA} piezo limits {laser.RESET} \n"
                f' "limits": {{"max":{v_max}, "min": {v_min}, "unit": "[V]", "resolution": 1E-3}}'
            )

        print("="*100)


    read_limits(master_diode)
    read_limits(amplifier_diode)
    print(master_diode.read_laser())
    print(amplifier_diode.read_laser())

    # print(master_diode.laser_monitor_df(n_measurements=5))
    # print(amplifier_diode.laser_monitor_df(n_measurements=5))

    def test_laser_monitor(
            master_diode:object=amplifier_diode,
            amplifier_diode:object=amplifier_diode,
            ):
        master_diode.switch_on()
        amplifier_diode.switch_on()
        # print(master_diode.laser_monitor(n_measurements=20,
        #                                 plot=True))
        print(amplifier_diode.laser_monitor(n_measurements=20,
                                plot=True))
        master_diode.switch_off()
        amplifier_diode.switch_off()

    test_laser_monitor()




    def scan_laser_parameters(laser:object, silent=False):
        print(f"=== {laser.GREEN} scan_laser_parameters() {laser.RESET}===")
        laser.send_command(":Laser:STATus?")
        laser.send_command(":Laser:POLarity?")
        ## laser current 
        print(f"{laser.MAGENTA} Current {laser.RESET}")
        print("actual current =", laser.read_current(silent=silent))
        print("actual set current = ", laser.read_setcurrent())
        laser.send_command(":SYSTem:BAUDrate?", silent=silent)
        laser.send_command(":Laser:ILIMit? MIN", silent=silent)
        laser.send_command(":Laser:ILIMit? MAX", silent=silent)
        laser.send_command(":Laser:MODe?", silent=silent)
        laser.send_command(":Laser:CURRent:Set?", silent=silent)
        laser.send_command(":Laser:POWer?", silent=silent)
        laser.send_command(":Laser:TEC:Required?")
        laser.send_command("Laser:IU:ENAble?")
        laser.send_command(":PDiode:CURRent?")
        laser.send_command(":CCoupling:ENAble?")
        ## laser temperature
        print(f"{laser.MAGENTA} temperature {laser.RESET}")
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
        if laser.piezo:
            print(f"{laser.MAGENTA} Piezo {laser.RESET}")
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

    # test_laser_monitor(master_diode)

    master_diode.disconnect()
    amplifier_diode.disconnect()