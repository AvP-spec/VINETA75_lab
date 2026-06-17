#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 20 09:49:56 2026

@author: erikh
"""

#%%
MODULAR_MODE = True

assert not MODULAR_MODE, "Modular MODE is ON, Run ALL is aborted"
print("Modular Mod is off")

#%%
from managers.lif import LIFManager
import utils.file_utils as fu

import time

import pyvisa

#%%

rm = LIFManager()

#%%

laser_warmup_s = 15

try:
    rm.laser_on()
    print(f"    Waiting {laser_warmup_s} sec for laser warmup")
    time.sleep(laser_warmup_s)

    rm.master_diode.set_current(0.1, "A", silent=False)
    i_set  = rm.master_diode.read_setcurrent()
    i_act  = rm.master_diode.read_current()
    wl     = rm.wlm.read()['wavelength']
    print(f"I_set={i_set}, I_act={i_act}, λ={wl*1e9:.5f} nm")
    
finally: 
    rm.laser_off()
    
    
#%%
rm.disconnect_all()

#%% 
import os
print(os.environ['PATH'])