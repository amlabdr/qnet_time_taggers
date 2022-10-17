# -*- coding: utf-8 -*-
"""
Created on Mon Mar 28 09:54:48 2022

@author: qlab
"""
#!/usr/bin/env python



import sys, json
sys.path.append("C:\\daq\\pythonScripts\\library")


from threading import Thread

import yaml, os, time

from Swabian import SwabianClientLib

url = '129.6.250.132:5672'


PERIOD = 30
DELAY = 5



import time
from proton import Message
from proton.handlers import MessagingHandler
from proton.reactor import Container
import json, sys, os

from datetime import datetime
from datetime import timedelta


class Send(MessagingHandler):
    def __init__(self, server,topic, messages):
        super(Send, self).__init__()
        self.server = server
        self.topic = topic
        self.confirmed = 0
        self.data = messages
        self.total = 1

    def on_connection_error(self, event):
        print("connection error")
        return super().on_connection_error(event)
    
    def on_transport_error(self, event) -> None:
        print("transport error")
        return super().on_transport_error(event)
    def on_released(self, event) -> None:
        print("relesed")
        return super().on_released(event)
    
        
    
    def on_start(self, event):
        conn = event.container.connect(self.server)
        event.container.create_sender(conn, self.topic)
   
    def on_sendable(self, event):
        msg = Message(body=json.dumps(self.data))
        event.sender.send(msg)
        event.sender.close()
        
    def on_rejected(self, event):
        print("msg Rejected")
        return super().on_rejected(event)
        
    def on_accepted(self, event):
        self.confirmed += 1
        if self.confirmed == self.total:
            print("spexx msg sent to",self.topic)
            event.connection.close()
    

    def on_disconnected(self, event):
        print("disconnected")
        self.sent = self.confirmed


        
class RecvSpecification(MessagingHandler):
    def __init__(self, server,topic):
        super(RecvSpecification, self).__init__()
        self.server = server
        self.topic = topic
        
        
    def on_start(self, event):
        conn = event.container.connect(self.server)
        event.container.create_receiver(conn, self.topic)
        
    def on_message(self, event):
        
        print("TIME: ",datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        jsonData = json.loads(event.message.body)
        print("recevied spec",jsonData)
        endpoint=jsonData['endpoint']
        name = jsonData['name']
        type = jsonData['parameters']['type']
        when = jsonData['when']
        exec_time = datetime.strptime(when, '%Y-%m-%d %H:%M:%S.%f')
        #2022-05-23 18:03:19.461738'
        print("type is ",type)
        print("the when is ",when)

        #agent will publish a receipt for spec
        print(" Agent will send %s receipt" %type)
        specification_receiptData=jsonData.copy()
        specification_receiptData['receipt'] = jsonData['specification']
        del specification_receiptData['specification']
        topic = event.message.reply_to
        Container(Send(url,topic, specification_receiptData)).run()
        print(" Agent will do measurement")
        #########
        n = int(jsonData['parameters']['samples_size'])

        TEMP=[]
        
        for i in range (n):
            TT.clearTimeTagStream()
            while(datetime.utcnow() < exec_time + timedelta(0,i*DELAY)):
                None
            print("timeTags TIME of start reception", datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            
            TT.startTimeTagStream()
            time.sleep(dicty["cal_int_time"])
            TT.stopTimeTagStream()
            temp = TT.getTimeTagStream()
            TEMP.append(temp)
            print("timeTags TIME of end reception", datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            
        i=0
        specification_resultData=jsonData.copy()
        specification_resultData['result'] = specification_resultData['specification']
        del specification_resultData['specification']
        topic = 'topic://'+endpoint+'/results'
        for temp in TEMP:
            print(" Agent will send result for ",i)
            specification_resultData['resultValues'] = [None,None]
            specification_resultData['resultValues'][0]=i
            specification_resultData['resultValues'][1]= [temp.tolist()]
            Container(Send(url,topic, specification_resultData)).run() 
            i+=1
        




def send_capability(url,topic,period,capabilityData):
    while True:
        # Publish Capability in "/capabilities"
        Container(Send(url,topic, capabilityData)).run()
        print('capability sent')
        time.sleep(period)







#publishing the agent capability
capabilityFile = open('conf/capability.json', 'r')
capabilityData = json.load(capabilityFile)
capabilityFile.close()






fn    = 'conf/config.yaml'
yf    = open(fn,'r')
dicty = yaml.load(yf, Loader=yaml.SafeLoader)

print("===Agent===")


# Init local TimeTagger
t6 = time.time()
TT = SwabianClientLib.TimeTag(dicty["TT"]["IP"], fn, 'TT')

basedr      = dicty["directory"]
filebase    = dicty["filename"]

#if not(os.path.exists(basedr)):
 #   os.mkdir(basedr)

TT.initCounts(TT.getActiveChannels())
time.sleep(0.1)

print('TT counts:')
print(TT.getCounts())

TT.initTimeTagStream(max_buf_size=10**7, channels = dicty["TT"]["active_ch"])
time.sleep(0.1)


topic = 'topic://'+'/capabilities'
thread_send_capability = Thread(target=send_capability, args=(url,topic,PERIOD,capabilityData))
thread_send_capability.start()
topic='topic://'+capabilityData['endpoint']+'/specifications'
Container(RecvSpecification(url,topic)).run()








    


    

"""


# Process Specification: Measure TimeTagStream
    # if OK: publish Receipt
    #...
    AliceTT.clearTimeTagStream()
    AliceTT.startTimeTagStream()
    time.sleep(specification.parameters.int_time)           # int_time: agent parameter in Specification
    Atemp = AliceTT.getTimeTagStream()
    # publish Result in topic
    #...


# on exit
AliceTT.close()"""