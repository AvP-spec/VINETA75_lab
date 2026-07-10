# -*- coding: utf-8 -*-
"""
21.04.2026
Measurements of the wavelength range for full scane of laser piezo

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
### check print out format for time variables
now = datetime.now()
print(now)
timesamp = time.perf_counter()
print(timesamp)

#%%
### import project related moduls
from managers.lif import LIFManager
import utils.file_utils as fu

#%%assert 
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
        "comment": "Measurements of the wavelength range"
                    "for full scane of laser piezo and"
                    " its reproducibility"
        }
    return meta_data

#%%
### piezo scan Average ON
rm.wlm.average_on()
rm.master_diode.set_piezo(0, "[V]")
print(rm.master_diode.read_piezo())

scan_start_time = datetime.now()                # <-- exakter Startzeitpunkt bei Beginn der Messung
df = rm.scan_piezo(v_step=3)

df["abs_time"] = scan_start_time + pd.to_timedelta(df["start_time"], unit="s")

data_dir = fu.make_data_dir(base_name="LIF/piezo_scan")
file_path = fu.make_data_file_name(
    data_dir=data_dir,
    base_name="average_ON",
    extension="csv"
)

meta = file_meta_data()
meta["scan_start_time"] = str(scan_start_time)      # <-- Startzeitpunkt wird in den Header geschrieben
fu.save_dataframe(df=df,
                  file_path=file_path,
                  metadata=meta,
                  sep="\t",
                  index=True,
                  silent=False,  
                  )


#%%
### piezo scan Average OFF
rm.wlm.average_off()
rm.master_diode.set_piezo(0, "[V]")
print(rm.master_diode.read_piezo())

scan_start_time = datetime.now()
df = rm.scan_piezo(v_step=1)

df["abs_time"] = scan_start_time + pd.to_timedelta(df["start_time"], unit="s")

data_dir = fu.make_data_dir(base_name="LIF/piezo_scan")
file_path = fu.make_data_file_name(
    data_dir=data_dir,
    base_name="average_OFF",
    extension="csv"
)

meta = file_meta_data()
meta["scan_start_time"] = str(scan_start_time)
fu.save_dataframe(df=df,
                  file_path=file_path,
                  metadata=meta,
                  sep="\t",
                  index=True,
                  silent=False,  
                  )



#%%


#%%
rm.laser_off()
rm.disconnect_all()