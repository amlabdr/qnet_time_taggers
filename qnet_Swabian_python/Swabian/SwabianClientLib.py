# -*- coding: utf-8 -*-
"""
Created on Mon Feb  7 14:22:09 2022

@author: qlab
"""

# this server will provide either time tag data as requested or histograms as requested

import numpy as np
import matplotlib.pyplot as plt
import time
import datetime
import yaml
import Pyro5, io, base64

try:
    import Pyro5.api
except ModuleNotFoundError:
    import sys
    print('Please install Pyro5 module. "python -m pip install Pyro5"')
    sys.exit()

def load_numpy_array(classname, data):
    assert classname == 'numpy.ndarray'
    buffer = io.BytesIO(base64.b64decode(data['data'].encode('ASCII')))
    return np.load(buffer, allow_pickle=False)

class TimeTag():
    def __init__(self,IP,yaml_fn, party):
        
        fn = open(yaml_fn,'r')
        dicty = yaml.load(fn, Loader=yaml.SafeLoader)    
        fn.close()
               
        Pyro5.api.register_dict_to_class(classname='numpy.ndarray', converter=load_numpy_array)
        mes = "PYRO:TimeTagger@" + IP + ":23000"
        print(mes)
        self.TimeTagger = Pyro5.api.Proxy(mes)
        
        self.tt = self.TimeTagger.createTimeTagger(dicty[party]["serial"])
        self.tt.reset() # Reset all settings to default values
        print('Time Tagger serial:', self.tt.getSerial())
        
        
        self.fn = (dicty["filename"])
        self.dr = (dicty["directory"])
        
        self.activeChannels = dicty[party]["active_ch"]
        
        for n in range(len(dicty[party]["active_ch"])):
            self.tt.setInputDelay((dicty[party]["active_ch"])[n], (dicty[party]["input_delay"])[n])
            self.tt.setDeadtime((dicty[party]["active_ch"])[n], (dicty[party]["deadtime"])[n])
            self.tt.setTriggerLevel((dicty[party]["active_ch"])[n], (dicty[party]["threshold"])[n])

        self.int_time   = int(dicty["int_time"]*1e12)

        # histogram and correlations
        self.START_CH = int(dicty[party]["histogram"]["start_ch"])
        self.CLICK_CH = int(dicty[party]["histogram"]["click_ch"])           
        self.resolution = int(dicty[party]["histogram"]["resolution"])
        self.bins       = int(dicty[party]["histogram"]["bins"])
        self.sumstart   = int(dicty[party]["histogram"]["sum_start"])
        self.sumstop    = int(dicty[party]["histogram"]["sum_stop"])
      
        # 2d histogram
        self.START_CH2d = int(dicty[party]["histogram2d"]["start_ch"])
        self.CLICK_CH1 = int(dicty[party]["histogram2d"]["click_ch1"])    
        self.CLICK_CH2 = int(dicty[party]["histogram2d"]["click_ch2"])    
        self.resolution_1 = int(dicty[party]["histogram2d"]["resolution_ch1"])
        self.resolution_2 = int(dicty[party]["histogram2d"]["resolution_ch2"])
        self.bins_1 = int(dicty[party]["histogram2d"]["bins_ch1"])
        self.bins_2 = int(dicty[party]["histogram2d"]["bins_ch2"])
        
        
        # timetags
        self.ttagData = np.array([], dtype=np.uint64)
        
        if bool((dicty[party]["condFilter"]["status"])):
            self.tt.setConditionalFilter((dicty[party]["condFilter"]["trigger"]), (dicty[party]["condFilter"]["filtered"]))
    
    def getActiveChannels(self):
        return self.activeChannels
    
    def initCounts(self, channels = [1, 2]):
        self.rate = self.TimeTagger.Countrate(self.tt, channels)
        time.sleep(1)   
    
    def getCounts(self):
        return self.rate.getData()
    
    def initHistogram(self):
        self.histogram  = self.TimeTagger.Histogram(self.tt, self.CLICK_CH, self.START_CH, self.resolution, self.bins)
        self.histogram.clear()
    
    def getHistogram(self):
        self.histogram.startFor(self.int_time, clear=True)
        while self.histogram.isRunning():
            time.sleep(0.001)
        
        counts = self.histogram.getData()
        tm     = self.histogram.getIndex()        
        return tm, counts        
               
    def initCorrelation(self):
        self.corr = self.TimeTagger.Correlation(self.tt, self.START_CH, self.CLICK_CH, self.resolution, self.bins);
        self.corr.clear()
    
    def getCorrelation(self):
        self.corr.startFor(self.int_time, clear=True)
        #t0 = time.time()        
        while self.corr.isRunning():
            time.sleep(0.001)
        #print(time.time()-t0)
        counts = self.corr.getData();                    
        tm     = self.corr.getIndex();            
        return tm, counts        
    
    def getCoincidenceSum(self, corr, start = 1, stop = 1):
        coinc_sum = np.sum(corr[1][np.where(corr[0] > start*1000)[0][0]:np.where(corr[0] > stop*1000)[0][0]-1])
        return coinc_sum
    
    def init2dHisto(self):
        self.histogram2d = self.TimeTagger.Histogram2D(self.tt, self.START_CH2d, self.CLICK_CH1, self.CLICK_CH2, self.resolution_1, self.resolution_2, self.bins_1, self.bins_1)
        self.histogram2d.clear()
    
    def get2dHisto(self):
        self.histogram2d.startFor(self.int_time, clear=True)
        #t0 = time.time()        
        while self.histogram2d.isRunning():
            time.sleep(0.001)
        #print(time.time()-t0)
        counts = self.histogram2d.getData();                    
        tm     = self.histogram2d.getIndex();            
        return tm, counts        
        
    def initTimeTagStream(self, max_buf_size = 10**7, channels = [1, 2]):        
        self.stream = self.TimeTagger.TimeTagStream(self.tt, max_buf_size, channels)
        time.sleep(0.1)
                
    def clearTimeTagStream(self):
        self.stream.clear()
        
    def startTimeTagStream(self):        
        self.stream.start()
        
    def stopTimeTagStream(self):        
        self.stream.stop()
    
    
    def getCaptureDuration(self):        
        return self.stream.getCaptureDuration()

        
    def getTimeTagStream(self):
        self.ttagData = self.stream.getData()
        print('received %d timetags'%len(self.ttagData))        
        return self.ttagData
    
    def startTimeTagStreamFor(self):        
        self.stream.startFor(self.int_time, clear=True)
    
    def getTimeTagStreamFor(self):
        
        while self.stream.isRunning():
            time.sleep(0.01)
            self.ttagData = np.hstack((self.ttagData,self.stream.getData()))
     
        print('received %d timetags'%len(self.ttagData))        
        return self.ttagData

            

        '''
        # ttag data structure: 
            #   8 bit overflow getEventType()
            #   8 bit reserved nothing
            #   16 bit missed events GetMissedEvents()
            #   32 bit channel number getChannels()
            #   64 bit timestamp in ps getTimeStamps()
            # ------------------------
            #   128 bit total
    
        a = np.array(dat.getEventTypes(),dtype=np.uint64)
        b = np.array(dat.getMissedEvents(),dtype=np.uint64)
        c = np.array(dat.getChannels(),dtype=np.uint64)
        d = np.array(dat.getTimestamps(),dtype = np.uint64)
        
        # prepare 2, 64 bit packets and join those
        ttagData = np.vstack((np.left_shift(a,56) + np.left_shift(b,32) + c  ,d)).reshape((-1,),order='F')       
        
                
        # short timestamp
        # 58 bits for time tag, 6 bits for channel number -> this will overfloww once every 80 hours
        # if overflow occurs: 4 bits for overflow type, 48 bits for missed events
        
        if dat.hasOverflows:
            print('overflow')
        else:
            compTTdata = np.array(np.left_shift(np.array(d & (2**58 -1), dtype=np.uint64),6) + c, dtype=np.uint64)
                    
            
        '''
    
    
    
    def openTTFile(self,basefn):     
        tim  = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        fn   = basefn + '_' + tim + '.bin'
        print('opening output file: ' + fn)
        self.binwrite = open(fn,'ab')
        
    def writeTTFile(self):        
        self.ttagData.tofile(self.binwrite)          
        print('writing to output file')
        
    def closeTTFile(self):
        self.binwrite.close()
        
    def close(self):
        self.TimeTagger.freeTimeTagger(self.tt)
        

if (__name__ == '__main__'):
    
    IP = "129.6.168.224"


    TT = TimeTag(IP,"TimeTagger.yaml")
    TT.initCounts()
    print(TT.getCounts())
    
    print('time tags')    
    TT.initTimeTagStream(max_buf_size=10**7, channels = [1, 7, 8])
    TT.clearTimeTagStream()
    TT.startTimeTagStreamFor()
    print(TT.getTimeTagStreamFor())
    
    print('histogram')
    TT.initHistogram()
    print(TT.getHistogram())
    
    print('Correlation')
    TT.initCorrelation()
    print(TT.getCorrelation())
    
    print('histogram2D')
    TT.init2dHisto()
    print(TT.get2dHisto())
    

    
    #for n in range(2):
    #    test = TT.getTimeTagStream()
    #    print(test)
        
        
    TT.close()
    
    

'''

    Alice = TimeTag(IP,"Alice.yaml")
    Bob = TimeTag(IP,"Bob.yaml")
    fig1 = plt
    
    
    Alice.initCounts(Alice.getActiveChannels())
    Bob.initCounts(Bob.getActiveChannels())
    
    print('Alice counts:')
    print(Alice.getCounts())
    print('Bob counts:')
    print(Bob.getCounts())
    
    
    Alice.openTTFile('AliceTTagADVRsourceWith10MHzSync0_5pps')
    Bob.openTTFile('BobTTagADVRsourceWith10MHzSync0_5pps')
    
    Alice.initTimeTagStream(max_buf_size=10**7, channels = [1, 7, 8])
    Bob.initTimeTagStream(max_buf_size=10**7, channels = [1, 3, 4])
    
    Alice.clearTimeTagStream()
    Bob.clearTimeTagStream()
    Alice.startTimeTagStream()
    Bob.startTimeTagStream()
    
    for n in range(1):
        test = Alice.getTimeTagStream()
        test = Bob.getTimeTagStream()
        time.sleep(0.5)
        Alice.writeTTFile()
        Bob.writeTTFile()
    Alice.closeTTFile()
    Bob.closeTTFile()
    
    
  
    ttag.initHistogram()
    for n in range(10):
        a = ttag.getHistogram()
        print(max(a[1]))
        fig1.plot(a[0], a[1])
        fig1.show()

    Alice.close()
    Bob.close()
'''