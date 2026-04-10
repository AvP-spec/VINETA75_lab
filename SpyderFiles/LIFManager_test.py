# -*- coding: utf-8 -*-
"""
Created on Wed Apr  8 16:57:36 2026

@author: Andrei
"""
#%%
from managers.lif import LIFManager

#%%
rm = LIFManager()
#%%
rm.laser_on()
#%%

print(rm.master_diode.read_piezo())
rm.master_diode.set_piezo(0, "[V]")
print(rm.master_diode.read_piezo())

#%%
rm.wlm.average_on()

#%%
df_wlm = rm.wlm.wlm_monitor(
    n_measurements=10, 
    silent=False
    )
print(df_wlm.describe())

#%%
df = rm.scan_piezo(
    v_step=5,
    )
#%%
import utils.file_utils as fu
data_dir = fu.get_data_dir()
file_path = fu.get_data_file_name(
    data_dir=data_dir,
    base_name="laser_scan_test"
    )
#%%
fu.save_dataframe(df, file_path)

#%%
print(df)

#%%
print(file_path)

#%%


#%%
rm.laser_off()
rm.disconnect_all()