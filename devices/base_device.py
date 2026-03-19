'''
v.01 - property: self.connection become protected via self.__instr
'''

import serial.tools.list_ports
import pyvisa

class BaseDevice:
    DEVICE_DIKT = {
        "USB0::0x03EB::0x2065::GPIB_06_4423030363035131A1C0::INSTR": "wavelength meter",
        "VID:PID:SER = 0403:6001:6": "Pilot PZ 500",
        "VID:PID:SER = 2341:0043:24238313635351910130": "Arduino-AvP",
    }

    CONNECTION_SETTINGS = {}

    RED = "\033[31m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    YELLOW = "\033[33m"
    YELLOW2 = "\033[93m"
    YELLOW3 = "\033[1;33m"

    RESET = "\033[0m"

    def __init__(self):
        self.rm = None
        try:
            self.rm = pyvisa.ResourceManager()
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
    
        
    def get_COM_connections(self):
        device_list = []
        ports = serial.tools.list_ports.comports()
        for port in ports:
            vid = f"{port.vid:04X}" if port.vid is not None else "None"
            pid = f"{port.pid:04X}" if port.pid is not None else "None"       
            serial_no = f"{port.serial_number}" if port.serial_number is not None else "None"
            
            # constract hardware identificator
            hwid_ = f"VID:PID:SER = {vid}:{pid}:{serial_no}" 
            if hwid_ in self.DEVICE_DIKT:
                device_list.append([port.device, self.DEVICE_DIKT[hwid_], hwid_ ])
            else:  
                device_list.append([port.device, "not in DEVICE_DIKT", hwid_])
        return device_list
        
    def get_GPIB_connections(self):
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
    
    def print_device_list(self, dv_list):
        for el in dv_list:
            if "not in DEVICE_DIKT" in el:
                print(el)
            else:
                print(f"{self.GREEN}{el}{self.RESET}")

    def print_connections(self):
        COM_list = self.get_COM_connections()
        GPIB_list = self.get_GPIB_connections()

        print(" COM connectios ".center(50, '-'))
        self.print_device_list(COM_list)
        print(" GPIB/VISA connectios ".center(50, '-'))
        self.print_device_list(GPIB_list)
        print(" print_connections() ended ".center(50, '-'))

    def _com_to_visa(self, port):
        ''' transfer "COMx" to 'ASRLx::INSTR'
        '''
        port_number = str(port).upper().replace("COM", "").strip()
        return f"ASRL{port_number}::INSTR"

    def get_COM_port(self):

        # test if hwid given
        if self.hwid is None:
            print(f"{self.RED}Error in get_COM_port() of BaseDevice")
            print(f"{self.RED} It is BaseDevice, no connections {self.RESET}")
            return self
        # test if the devive known and in DEVICE_DIKT
        if self.hwid not in self.DEVICE_DIKT:
            print(f"{self.RED}Error in get_COM_port() of BaseDevice")
            print(f"Device {self.hwid} not in DEVICE_DIKT {self.RESET}")
            return self
        
        device_list = self.get_COM_connections()
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


    def connect(self):
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
            self.after_connect()
        except Exception as e:
            print(f_id)
            print(f"{self.RED}Connection failed: {e}{self.RESET}")
            
        return self


    def after_connect(self):
        '''hook for particular device connections'''
        print("BaseDevice after_connect")
        return self
    

    def disconnect(self):
        f_id = "\n BaseDevice.disconnect() "
        if self.connection is None:
            print(f_id)
            print(f"{self.name}.connection=None, may be it was not open")
            return self
        else:
            try:
                # self.__inst.close()  # for Stefan scripts can be useful
                self.connection.close()
                print(f"{self.GREEN}[{self.name}] Connecton closed.{self.RESET}")
                self.__inst = None
            except Exception as e:
                print(f_id)
                print(f"[{self.RED}{self.name}] Error at closing:{self.RESET} {e}")

            finally:
                return self


    def print_coulors(self):
            '''
            List avalible coulour names and check visibility on the screen for
            VS code / Spyder or Light / Dark schema
            '''
            print(f"{self.RED} I am RED {self.RESET}")
            print(f"{self.MAGENTA} I am MAGENTA {self.RESET}")
            print(f"{self.BLUE} I am BLUE {self.RESET}")
            print(f"{self.CYAN} I am CYAN {self.RESET}")
            print(f"{self.GREEN} I am GREEN {self.RESET}")
            print(f"{self.YELLOW} I am YELLOW {self.RESET}")
            print(f"{self.YELLOW2} I am YELLOW2 {self.RESET}")
            print(f"{self.YELLOW3} I am YELLOW3 {self.RESET}")
            


if __name__ == "__main__":
    print("== hallo =="*10)      
    dvc = BaseDevice()
    # for el in dvc.get_COM_connections():
    #     print(el)

    # for el in dvc.get_GPIB_connections():
    #     print(el)

    dvc.print_connections()