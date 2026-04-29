
import serial.tools.list_ports
import pyvisa
import os
import sys
from pathlib import Path

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.terminal_styler import TerminalColours

class BaseDevice(TerminalColours):
    DEVICE_DIKT = {
        # GPIB: 
        "USB0::0x03EB::0x2065::GPIB_06_4423030363035131A1C0::INSTR": "wavelength meter",
        # VID:PID fallback für Messgeräte ohne Seriennummer: 
        "VID:PID = 0403:6001": "Pilot series", 
        # Arduino per Seriennummer: 
        "VID:PID:SER = 2341:0043:24238313635351910130": "Arduino-AvP",
        "VID:PID:SER = 2341:0043:859373138373518122F1": "Arduino-Erik",
    }

    CONNECTION_SETTINGS = {}


    def __init__(self):
        self.rm = None
        try:
            self.rm = pyvisa.ResourceManager('@py')
        except Exception:
            print(self.RED)
            print("BaseDevice init Error, pyvisa.ResourceManager() not created")
            print("VISA not installed?")
            print(self.RESET)
        self.hwid = None # HardWare IDentification  
        self.name = None
        self.port = None
     #   self.connection = None # the property for protection
        self.__inst = None

    @property
    def connection(self):
        if self.__inst is None:
            print("\n BaseDevice.connection")
            print(f"{self.RED}Device is not connected{self.RESET}")
            # raise ConnectionError(f"{self.RED}Device is not connected{self.RESET}")
        return self.__inst
    
        
    def _get_COM_connections(self):
        device_list = []
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # ttyS Ports ohne VID/PID überspringen
            if port.vid is None and str(port.device).startswith('/dev/ttyS'):
                continue
            vid = f"{port.vid:04X}" if port.vid is not None else "None"
            pid = f"{port.pid:04X}" if port.pid is not None else "None"       
            serial_no = f"{port.serial_number}" if port.serial_number is not None else "None"
            
            # Symlink nur unter Linux prüfen
            symlink_name = None
            if os.name != 'nt':  # nicht Windows
                dev_path = Path(port.device)
                for link in Path("/dev").iterdir():
                    if link.name.startswith("ttyPilot"):
                        try:
                            if link.resolve() == dev_path.resolve():
                                symlink_name = link.name
                                break
                        except Exception:
                            pass
            
            # Priorität: SER+Symlink → SER → VID:PID
            hwid_full_sym = f"VID:PID:SER = {vid}:{pid}:{serial_no}:{symlink_name}" if symlink_name else None
            hwid_full     = f"VID:PID:SER = {vid}:{pid}:{serial_no}"
            hwid_short    = f"VID:PID = {vid}:{pid}"

            if hwid_full_sym and hwid_full_sym in self.DEVICE_DIKT:
                hwid_ = hwid_full_sym
            elif hwid_full in self.DEVICE_DIKT:
                hwid_ = hwid_full
            elif hwid_short in self.DEVICE_DIKT:
                hwid_ = hwid_short
            else:
                hwid_ = hwid_full  # für "not in DEVICE_DIKT" Ausgabe
                
            if hwid_ in self.DEVICE_DIKT:
                device_list.append([port.device, self.DEVICE_DIKT[hwid_], hwid_ ])
            else:  
                device_list.append([port.device, "not in DEVICE_DIKT", hwid_])
        return device_list
        
    def _get_GPIB_connections(self):
        if self.rm is None:
            return[["None", "VISA Manager not initialized"]]
        
        device_list = []
        #rm = pyvisa.ResourceManager()
        resources = self.rm.list_resources()
        for res in resources:
            if res.startswith("ASRL"):
                continue

            if res in self.DEVICE_DIKT:
                device_list.append([res, self.DEVICE_DIKT[res]])
            else:
                device_list.append([res, "not in DEVICE_DIKT"])
        return device_list
    
    def _print_device_list(self, dv_list):
        for el in dv_list:
            if "not in DEVICE_DIKT" in el:
                print(el)
            else:
                print(f"{self.GREEN}{el}{self.RESET}")

    def print_connections(self):
        COM_list = self._get_COM_connections()
        GPIB_list = self._get_GPIB_connections()

        print(" COM connections ".center(50, '-'))
        self._print_device_list(COM_list)
        print(" GPIB/VISA connections ".center(50, '-'))
        self._print_device_list(GPIB_list)
        print(" print_connections() ended ".center(50, '-'))

    def _com_to_visa(self, port):
        port = str(port)
        if port.upper().startswith("COM"):
            # Windows: COM3 → ASRL3::INSTR
            port_number = port.upper().replace("COM", "").strip()
            return f"ASRL{port_number}::INSTR"
        else:
            # Linux with Symlink: /dev/ttyACM0 → ASRL/dev/ttyACM0::INSTR
            return f"ASRL{port}::INSTR"

    def get_COM_port(self):
        # test if hwid given
        if self.hwid is None:
            print(f"{self.RED}Error in get_COM_port() of BaseDevice")
            print(f"{self.RED} It is BaseDevice, no hwd defined, no connections {self.RESET}")
            return self
        # test if the devive known and in DEVICE_DIKT
        if self.hwid not in self.DEVICE_DIKT:
            print(f"{self.RED}Error in get_COM_port() of BaseDevice")
            print(f"Device {self.hwid} not in DEVICE_DIKT {self.RESET}")
            return self
        
        device_list = self._get_COM_connections()
        for dv in device_list:
            if dv[-1] == self.hwid:
                self.port = self._com_to_visa(dv[0])
                print(f"{self.GREEN}Found {self.name} on {self.port}{self.RESET}")
                return self
            
        self.port = None # if not found in connections 
        print(f"{self.RED}Error in get_COM_port() of BaseDevice")
        print(f"Device {self.name} with HWID {self.hwid} not found!")
        print(f"probably it is not connected to COM port{self.RESET}")
        return self
    

    def get_COM_port_by_idn(self, idn_expected:str, silent=True):
        '''
        Findet den Port eines Geräts anhand seiner IDN-Antwort.
        Iteriert durch alle Ports mit passender VID:PID und sendet *IDN?.
        Plattformunabhängig – kein udev oder Seriennummer nötig.
        '''
        if self.hwid is None:
            print(f"{self.RED}Error in get_COM_port_by_idn(): no hwid defined{self.RESET}")
            return self

        vid_pid = self.hwid  # z.B. "VID:PID = 0403:6001"
        device_list = self._get_COM_connections()

        # alle Ports mit passender VID:PID sammeln
        candidates = [dv for dv in device_list if vid_pid in dv[-1]]

        if not candidates:
            print(f"{self.RED}No devices with {vid_pid} found!{self.RESET}")
            return self

        for dv in candidates:
            port = self._com_to_visa(dv[0])
            if not silent:
                print(f"Trying {port} ...")
            try:
                inst = self.rm.open_resource(port, **self.CONNECTION_SETTINGS)
                import time
                time.sleep(2)  # Arduino/Gerät Reset abwarten
                idn = inst.query('*IDN?').strip()
                if not silent:
                    print(f"  IDN: {idn}")
                if idn == idn_expected:
                    inst.close()
                    self.port = port
                    print(f"{self.GREEN}Found {self.name} on {self.port}{self.RESET}")
                    return self
                inst.close()
            except Exception as e:
                if not silent:
                    print(f"  Error: {e}")
                try:
                    inst.close()
                except:
                    pass

        self.port = None
        print(f"{self.RED}Device {self.name} with IDN '{idn_expected}' not found!{self.RESET}")
        return self


    def connect(self, silent=True):
        f_id = "\n BaseDevice.connect() "
        if self.port is None:
            print(f_id)
            print(f"{self.RED}Error: Port unknown. Run get_COM_port() first."
                  f"or set self.port property {self.RESET}")
            return self
        
        try: 
          #  self.connection = self.rm.open_resource(self.port, **self.CONNECTION_SETTINGS)
            self.__inst = self.rm.open_resource(self.port, **self.CONNECTION_SETTINGS)
            print(f"{self.GREEN}Connected to {self.name} on {self.port}{self.RESET}")
            self.after_connect(silent=silent)
        except Exception as e:
            print(f_id)
            print(f"{self.RED}Connection failed: {e}{self.RESET}")
            
        return self


    def after_connect(self, silent=True):
        '''hook for particular device connections'''
        print("BaseDevice after_connect")
        return self
    

    def disconnect(self):
        f_id = "\n BaseDevice.disconnect() "
        if self.__inst is None:
        # if self.connection is None: # it will initiate the print commands of self.connection if no connection
            print(f_id)
            print(f"{self.name}.connection=None, may be it was not open")
            return self
        else:
            try:
                # self.__inst.close()  # for Stefan scripts can be useful
                self.connection.close()
                print(f"{self.GREEN}[{self.name}] Connection closed.{self.RESET}")
                self.__inst = None
            except Exception as e:
                print(f_id)
                print(f"[{self.RED}{self.name}] Error at closing:{self.RESET} {e}")

            finally:
                return self


            


if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("======== base_device.py modul =========")      
    dvc = BaseDevice()
    # for el in dvc.get_COM_connections():
    #     print(el)

    # for el in dvc.get_GPIB_connections():
    #     print(el)

    dvc.print_connections()
    dvc.print_coulors()