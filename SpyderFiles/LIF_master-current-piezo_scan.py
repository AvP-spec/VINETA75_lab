# -*- coding: utf-8 -*-
"""
21.04.2026
Measurements of the wavelength range for 
full scane of laser piezo for different currents

@author: Andrei
"""
#%%
MODULAR_MODE = True

assert not MODULAR_MODE, "Modular MODE is ON, Run ALL is aborted"
print("Modular Mod is off")
#%%
### import of general moduls
from datetime import datetime
import time
import pandas as pd

#%%
### import project related moduls
from managers.lif import LIFManager
import utils.file_utils as fu
import utils.scan_utils as su

#%%
rm = LIFManager()
rm_start_time = time.perf_counter()
#%%
rm.laser_on()
laser_start_time =time.perf_counter()

#%%
def file_meta_data():
    meta_data = {
        "datetime": str(datetime.now()),
        "timestemp": str(time.perf_counter()),
        "rm_start_time": str(rm_start_time),
        "laser_start_time": str(laser_start_time),
        "comment": "Measurements of the wavelength responds"
                    "on change of the master current"
        }
    return meta_data

#%%
def scan_piezo_aver_off(n=10):
    
    rm.wlm.average_off()
    rm.master_diode.set_piezo(0, "[V]")
    df_list = []
    for i in range(n):
        df = rm.scan_piezo(v_step=2)
        df['scan_number'] = i + 1
        df_list.append(df)
        
    return pd.concat(df_list, ignore_index=True)
        
#%%
current_scan_list = su.get_scan_list_linear(
    min_val = 0.05, 
    max_val = 0.6, 
    n_points = 10
    )

print(current_scan_list)

#%%
data_dir = fu.make_data_dir(base_name="LIF/master_scan_n01_wlm-av-off")
# number of piezo scans for each current
n=1
for current in current_scan_list:
    print(f"setting master curren of {current*1000} mA")
    rm.master_diode.set_current(value=current, unit='[A]', silent=True)
    df = scan_piezo_aver_off(n=n)
    current_mA = int(current*1000)
    fname = f"mcurrent_{current_mA:03d}_mA"
    meta = file_meta_data()
    meta_ext = {
        'master_set_current': current,
        'number of piezo scans': n,
        }
    meta.update(meta_ext)
    
    file_path = fu.make_data_file_name(
                                    data_dir=data_dir,
                                    base_name=fname,
                                    extension="csv"
                                    )
    
    fu.save_dataframe(df=df,
                      file_path=file_path,
                      metadata=meta,
                      sep="\t",
                      index=True,
                      silent=False,  
                      )

    
#%%
data_dir = fu.make_data_dir(base_name="LIF/master_scan_n5_wlm-av-off")
# number of piezo scans for each current
n=5
for current in current_scan_list:
    rm.master_diode.set_current(value=current, unit='[A]', silent=True)
    df = scan_piezo_aver_off(n=n)
    current_mA = int(current*1000)
    fname = f"mcurrent_{current_mA:03d}_mA"
    meta = file_meta_data()
    meta_ext = {
        'master_set_current': current,
        'number of piezo scans': n,
        }
    meta.update(meta_ext)
    
    file_path = fu.make_data_file_name(
                                    data_dir=data_dir,
                                    base_name=fname,
                                    extension="csv"
                                    )
    
    fu.save_dataframe(df=df,
                      file_path=file_path,
                      metadata=meta,
                      sep="\t",
                      index=True,
                      silent=False,  
                      )


#%%
def scan_piezo_aver_on(n=1):
    
    rm.wlm.average_on()
    rm.master_diode.set_piezo(0, "[V]")
    df_list = []
    for i in range(n):
        df = rm.scan_piezo(v_step=2)
        df['scan_number'] = i + 1
        df_list.append(df)
        
    return pd.concat(df_list, ignore_index=True)

#%%
data_dir = fu.make_data_dir(base_name="LIF/master_scan_n1_wlm-av-on")
# number of piezo scans for each current
n=1
for current in current_scan_list:
    rm.master_diode.set_current(value=current, unit='[A]', silent=True)
    
    df = scan_piezo_aver_on(n=n)
    
    current_mA = int(current*1000)
    fname = f"mcurrent_{current_mA:03d}_mA"
    meta = file_meta_data()
    meta_ext = {
        'master_set_current': current,
        'number of piezo scans': n,
        }
    meta.update(meta_ext)
    
    file_path = fu.make_data_file_name(
                                    data_dir=data_dir,
                                    base_name=fname,
                                    extension="csv"
                                    )
    
    fu.save_dataframe(df=df,
                      file_path=file_path,
                      metadata=meta,
                      sep="\t",
                      index=True,
                      silent=False,  
                      )


#%%
data_dir = fu.make_data_dir(base_name="LIF/master_scan_n5_wlm-av-on")
# number of piezo scans for each current
n=5
for current in current_scan_list:
    rm.master_diode.set_current(value=current, unit='[A]', silent=True)
    
    df = scan_piezo_aver_on(n=n)
    
    current_mA = int(current*1000)
    fname = f"mcurrent_{current_mA:03d}_mA"
    meta = file_meta_data()
    meta_ext = {
        'master_set_current': current,
        'number of piezo scans': n,
        }
    meta.update(meta_ext)
    
    file_path = fu.make_data_file_name(
                                    data_dir=data_dir,
                                    base_name=fname,
                                    extension="csv"
                                    )
    
    fu.save_dataframe(df=df,
                      file_path=file_path,
                      metadata=meta,
                      sep="\t",
                      index=True,
                      silent=False,  
                      )


#%%
MODULAR_MODE = True

assert not MODULAR_MODE, "Modular MODE is ON, Run ALL is aborted"
print("Modular Mod is off")



#%%
rm.laser_off()
rm.disconnect_all()