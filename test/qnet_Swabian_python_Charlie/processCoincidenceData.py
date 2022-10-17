# -*- coding: utf-8 -*-
"""
Created on Tue Mar 29 10:09:31 2022

@author: qlab
"""

import numpy as np
import matplotlib.pyplot as plt
from ismember import ismember
import yaml

class TTdata():
    def __init__(self, yamlfn, data, chan, sync, pps, Calibrate = True, calFactor = 1):
        
        self.yamlfn = yamlfn
        yfn   = open(self.yamlfn,'r')
        self.dicty = yaml.load(yfn, Loader=yaml.SafeLoader)
        yfn.close()
        
        self.calibration = calFactor
        self.channel     = data[0::2] & (2**32-1)
        self.time        = data[1::2]     
        self.ovflw       = data[0::2] >> 56
        self.event       = data[0::2] >> 32        
        self.sync_ch     = sync
        self.pps_ch      = pps
        self.chan_ch     = chan
        self.syncrate    = float(self.dicty["sync_rate"])

        
        # delete first element in case it starts with a sync
        if self.channel[0] == self.sync_ch: 
            self.delete_index(0)
        
        
        # delete last element in case it ends with a photon
        if self.channel[-1:] == self.chan_ch: 
            #print(self.channel[-1:])
            self.delete_index(len(self.channel)-1)
        
        
        # find pps events
        idx = np.where(self.channel == self.pps_ch)
        self.pps = self.time[idx]
        self.delete_index(idx)
        
        # find multiple sync events
        idx1 = np.where(self.channel == self.sync_ch)
        idx2 = np.where(np.diff(idx1[0]) == 1)[0] + 1
        #print(idx2)
        if idx2.size != 0:
            idx  = np.take(idx1, idx2)
            self.delete_index(idx)
            
        # find multiple chan events
        idx1 = np.where(self.channel == self.chan_ch)
        idx2 = np.where(np.diff(idx1[0]) == 1)[0] + 1
        #print(idx2)
        if idx2.size != 0:
            idx  = idx1[idx2]
            self.delete_index(idx)
        
        if Calibrate:
            self.calibration = 1e12/np.mean(np.diff(self.pps))
        
    #def alignAndApplyCalibration(self):    # align channels to calibration
        idx = np.where(self.channel == self.sync_ch)
        self.sync = (np.double(self.time[idx]) - np.double(self.pps[0]) ) * self.calibration
        
        idx = np.where(self.channel == self.chan_ch)
        self.phot = (np.double(self.time[idx]) - np.double(self.pps[0]) ) * self.calibration
        
        self.dt      = self.sync - self.phot
        self.syncbin = np.floor(self.sync/(1e12/self.syncrate))
        
        
    def delete_index(self, idx):
       
        self.channel = np.delete(self.channel, idx)
        self.time = np.delete(self.time, idx)
        self.ovflw = np.delete(self.ovflw, idx)
        self.event = np.delete(self.event, idx)
                


class Coincidences():
    def __init__(self, yamlfn, Alice, Bob):
        
        self.yamlfn = yamlfn
        yfn   = open(self.yamlfn,'r')
        self.dicty = yaml.load(yfn, Loader=yaml.SafeLoader)
        yfn.close()
        
        self.Alice = Alice
        self.Bob   = Bob

        if self.Alice.phot[0] > self.Bob.phot[0]:
            self.start = Alice.phot
            self.stop  = Bob.phot
        else:
            self.stop  = Alice.phot
            self.start = Bob.phot
        
        self.trange     = float(self.dicty["trange"]) # in ns
        self.binwidth   = float(self.dicty["binwidth"]) # in ns
        self.offset     = float(self.dicty["offset"]) # in ns
        self.samplesize = int(self.dicty["samplesize"]) # samples from data to find peak
        self.syncrate   = float(self.dicty["sync_rate"])
        self.resolution = float(self.dicty["resolution"]) # in ps
        
        
    def findPeak(self): # this should be run once at the beginning and will find a rough peak value
        
        self.bins       = np.arange(-self.trange, self.trange+self.binwidth, self.binwidth)
        self.dt         = np.zeros([2*self.samplesize,1])
        
        for n in range(self.samplesize):
            tempA = np.double(self.start[n]) - self.offset*1000
            idx   = np.where(self.stop > tempA)[0][0]
            tempB = np.double(self.stop[idx-1:idx+1])
            np.put(self.dt, [2*n, 2*n+1], tempB-tempA)


        idx     = np.where(self.dt > self.trange*1000)
        self.dt = np.delete(self.dt, idx)
        idx     = np.where(self.dt < -self.trange*1000)
        self.dt = np.delete(self.dt, idx)
        
        self.H_rough, self.edge = np.histogram(self.dt, self.bins*1000)
        self.edge_rough         = self.edge[1:]/1000

        mxidx        = np.mean(np.where(self.H_rough == max(self.H_rough)))
        self.peakval = (self.edge_rough[int(mxidx)] - self.offset)
        self.bin100  = np.round(self.peakval / (1e9/self.syncrate))
                
        
    def CoincidenceAndRates(self, bin100):
        
        #something like:
        #if not('self.bin100' in locals()):
        #    self.findPeak or load from yaml?
        
        self.bin100 = bin100        
        yfn   = open(self.yamlfn,'r')
        self.dicty = yaml.load(yfn, Loader=yaml.SafeLoader)
        yfn.close()
        
        idx1 = np.where(ismember(self.Alice.syncbin, self.Bob.syncbin - self.bin100)[0] == True)
        idx2 = np.where(ismember(self.Bob.syncbin - self.bin100, self.Alice.syncbin)[0] == True)
        
            
        #self.bins100 = np.arange(self.bin100-1,self.bin100+1,self.resolution*(self.syncrate/1e12)) * 1e12/self.syncrate # in ps          
        self.bins100 = np.arange(-1,+1,self.resolution*(self.syncrate/1e12)) * 1e12/self.syncrate # in ps          
        self.H, self.edge = np.histogram((self.Bob.dt[idx2] - self.Alice.dt[idx1]), self.bins100)
        
        
        # find values for singles and coincidences
        
        mxtim = self.edge[np.int32(np.mean(np.where(max(self.H)==self.H)[0]))]/1000
    
        self.coin_windw_1 = float(mxtim - self.dicty["coin_window"]["radius"]) # in ns
        self.coin_windw_2 = float(mxtim + self.dicty["coin_window"]["radius"]) # in ns
        self.acc_windw_1  = self.coin_windw_1 + self.dicty["coin_window"]["accidental_offset"]
        self.acc_windw_2  = self.coin_windw_2 + self.dicty["coin_window"]["accidental_offset"]

        self.coin_idx1 = np.where(self.bins100 > self.coin_windw_1*1000)[0][0]
        self.coin_idx2 = np.where(self.bins100 > self.coin_windw_2*1000)[0][0]


        self.acc_idx1 = np.where(self.bins100 > (self.coin_windw_1 + self.dicty["coin_window"]["accidental_offset"])*1000)[0][0]
        self.acc_idx2 = np.where(self.bins100 > (self.coin_windw_2 + self.dicty["coin_window"]["accidental_offset"])*1000)[0][0]


        self.totalCoincidences = sum(self.H[self.coin_idx1:self.coin_idx2])
        self.totalAccidentals  = sum(self.H[self.acc_idx1:self.acc_idx2])
       
        
        tempA   = (self.Alice.sync[idx1])
        self.totalSinglesAlice = len(np.where( (self.Alice.sync >= tempA[0]) & (self.Alice.sync <= tempA[-1:]) )[0]);
        
        tempB   = (self.Bob.sync[idx2])
        self.totalSinglesBob   = len(np.where( (self.Bob.sync >= tempB[0]) & (self.Bob.sync <= tempB[-1:]) )[0]);

        # per second        
        self.tA = (tempA[-1:] - tempA[0])*1e-12
        self.tB = (tempB[-1:] - tempB[0])*1e-12


        self.coincidencesPerSecond = self.totalCoincidences/np.mean([self.tA, self.tB])
        self.accidentalsPerSecond  = self.totalAccidentals/np.mean([self.tA, self.tB])
        self.singlesAlicePerSecond = self.totalSinglesAlice/self.tA
        self.singlesBobPerSecond   = self.totalSinglesBob/self.tB
        

        
if __name__ == '__main__':

    Alice = 'AliceTTagADVRsourceWith10MHzSync1pps_2022_03_16_09_47_05.bin'
    Bob   = 'BobTTagADVRsourceWith10MHzSync1pps_2022_03_16_09_47_05.bin'


    Adata = TTdata('config.yaml', np.fromfile(Alice, dtype=np.uint64), 1, 8, 7)
    Bdata = TTdata('config.yaml', np.fromfile(Bob, dtype=np.uint64), 1, 4, 3)

    coinc = Coincidences('config.yaml', Adata, Bdata)
    coinc.findPeak()
    coinc.CoincidenceAndRates()

    fig = plt
    fig.plot(coinc.edge[1:]/1000,coinc.H)
    fig.plot([coinc.coin_windw_1, coinc.coin_windw_1],[0, max(coinc.H)*1.1])
    fig.plot([coinc.coin_windw_2, coinc.coin_windw_2],[0, max(coinc.H)*1.1])
    fig.xlim([7.5, 15])

