# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 09:24:41 2026
test file for connection to Arduino 
solving problems with imports and learning Spyder

@author: AvP 
"""



#%% ## General imports
import time

#%%  ## import of device classes 

# from LIF.base_device import BaseDevice
from devices.arduino_AvP import ArduinoAvP

#%%  ## create arduino instance

arduino = ArduinoAvP()
arduino.print_connections()

#%% ## connect arduino instance with arduino device

arduino.get_COM_port().connect()
print(f"{arduino.connection=}")
time.sleep(5)

#%% ## drive arduino, acepting x or y

print("waiting for key input, press x or y then enter:")
key = input()
print(key)
arduino.connection.write(key)

#%%

print(arduino.connection)
arduino.disconnect()
print(arduino.connection)


#%%
from  pathlib import Path
current_dir = Path.cwd()
this_file = Path(__file__)
this_dir = Path(__file__).parent
main_dir = Path(__file__).parents[1]

print(current_dir)
print(this_file)
print(this_dir)
print(main_dir)


