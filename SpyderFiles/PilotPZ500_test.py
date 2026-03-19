# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 15:40:16 2026

@author: TheMa
"""
#%%
from devices.pilot_pz import PilotPZ500

#%%
print("cell 1")
pl = PilotPZ500()
#%%
print("cell 2")
pl.print_connections()
#%%
print("cell 3")
pl.get_COM_port().connect()

#%%
print("cell opreation 1")
pl.read_value(":Laser:STATus?")

#%%
print("bytes_in_buffer", pl.connection.bytes_in_buffer)

#%%
pl.print_buffer()




#%%
print("pl.connection.read_bytes(pl.connection.bytes_in_buffer)")
print(pl.connection.read_bytes(pl.connection.bytes_in_buffer))

#%%
x = pl.connection.read_raw()
print(x)
#%%
print("cell 4")
pl.disconnect()

#%%

#%%

#%%
