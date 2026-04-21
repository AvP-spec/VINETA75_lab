# -*- coding: utf-8 -*-
"""
Created on Wed Apr  8 16:57:36 2026

@author: Andrei
"""
#%%
MODULAR_MODE = True

assert not MODULAR_MODE, "Modular MODE is ON, Run ALL is aborted"
print("Modular Mod is off")
#%%
from managers.lif import LIFManager
import utils.file_utils as fu

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
rm.wlm.average_off()
#%%
df_wlm = rm.wlm.wlm_monitor(
    n_measurements=10, 
    silent=False
    )
print(df_wlm.describe())

#%%
df = rm.scan_piezo(
    v_step=1,
    )
#%%
print(df)

#%%

data_dir = fu.make_data_dir(
    base_name="piezo_scan"
    )

#%%
file_path = fu.get_data_file_name(
    data_dir=data_dir,
    base_name="piezo_scan_test_average_OFF"
    )
#%%
fu.save_dataframe(df, file_path)

#%%
print(df.columns)

#%%
print(file_path)

#%%


#%%
rm.laser_off()
rm.disconnect_all()