# -*- coding: utf-8 -*-
"""
Created on Mon Mar 28 09:54:48 2022

@author: qlab
"""
import jsonpickle
import time,yaml, numpy as np
from sqlalchemy import false
from proton import Message, Receiver, Url
from proton.handlers import MessagingHandler
from proton.reactor import Container
import json, sys, os
from processCoincidenceData import TTdata, Coincidences
import matplotlib.pyplot as plt
from datetime import timedelta
from datetime import datetime



fn    = 'conf/config.yaml'
yf    = open(fn,'r')
dicty = yaml.load(yf, Loader=yaml.SafeLoader)  


#!/usr/bin/env python


CALIBRATION_RECEIPT={}
MESUREMENT_RECEIPT={}
AGENTS_SPECIFICATION_LIST={}
MEASUREMENT_AGENTS = []

RESULTS={}
CALIBRATION_RESULT={}
bin100 = 0
bin100DONE= False
startTime=""
DELAY = 5


AGENTS_CAPABILITIES ={}
AGENTS_LIST=[]
SPECIFICATION_CONTROLLER={}

cval     = np.array([])
aliceval = np.array([])
bobval   = np.array([])
bobpos   = np.array([])
alicepos = np.array([])
accval   = np.array([])


tim  = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
fig  = plt


from threading import Thread
url = '129.6.250.132:5672'

SELF_NAME = 'coincidence-analyzer'
SELF_ENDPOINT = '/multiverse/qnet/coincidence'

PERIOD = 30

class Send(MessagingHandler):
    def __init__(self, server,topic, messages,self_reply=None):
        super(Send, self).__init__()
        self.server = server
        self.topic = topic
        self.confirmed = 0
        self.data = messages
        self.total = 1
        self.self_reply = self_reply
        
    
    def on_start(self, event):
        conn = event.container.connect(self.server)
        event.container.create_sender(conn, self.topic)
   
    def on_sendable(self, event):
        
        if self.self_reply == None:
            msg = Message(body=json.dumps(self.data))
        else:
            msg = Message(body=json.dumps(self.data),reply_to=self.self_reply)
        event.sender.send(msg)
        event.sender.close()
        
        
    def on_accepted(self, event):
        self.confirmed += 1
        if self.confirmed == self.total:
            print("spexx msg sent to",self.topic)
            
            event.connection.close()


    def on_disconnected(self, event):
        self.sent = self.confirmed

class Receive(MessagingHandler):
    def __init__(self, server):
        super(Receive, self).__init__()
        self.server = server
        
        
    def on_start(self, event):
        conn = event.container.connect(self.server)
        event.container.create_receiver(conn,'topic://'+'/capabilities',handler=RecvCapability())
        event.container.create_receiver(conn,'topic://'+SELF_ENDPOINT+'/specifications',handler=RecvSpecification())

class RecvCapability(MessagingHandler):
    def __init__(self):
        super(RecvCapability, self).__init__()
        
    def on_message(self, event):
        try:
            jsonData = json.loads(event.message.body)
            if ('name' in jsonData and 'endpoint' in jsonData):
                name = jsonData['name']
                endpoint=jsonData['endpoint']
                if (endpoint != SELF_ENDPOINT and 'qnet' in endpoint) or (endpoint == SELF_ENDPOINT and 'specification' in jsonData and 'qnet' in endpoint):
                    print("=======================")
                    print(" [x] Capability received from ", name)
                    AGENTS_CAPABILITIES[name]=jsonData
                    
                    if name not in AGENTS_LIST:
                        AGENTS_LIST.append(name)
        except:
            print("EROR in Received capability from agent")
                       
class RecvSpecification(MessagingHandler):
    def __init__(self):
        super(RecvSpecification, self).__init__()
        
    def on_message(self, event):
        
        global AGENTS_SPECIFICATION_LIST,startTime,MEASUREMENT_AGENTS
        startTime =datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-2]
        jsonData = json.loads(event.message.body)
        endpoint=jsonData['endpoint']
        samples_size = jsonData['parameters']['samples_size']
        if (endpoint != SELF_ENDPOINT and 'qnet' in endpoint) or (endpoint == SELF_ENDPOINT and 'specification' in jsonData and 'qnet' in endpoint):
            print(" [x] Specification received from the controller\n ")
            #agent will publish a receipt

            global SPECIFICATION_CONTROLLER,AGENTS_M
            SPECIFICATION_CONTROLLER = {}
            SPECIFICATION_CONTROLLER = jsonData.copy()

            ####AGENTS VERIFICATION
            AGENTS_VERIFICATION = True
            for parameter in jsonData['parameters']:
                if 'detector' in parameter:
                    agent = jsonData['parameters'][parameter]
                    if agent not in AGENTS_CAPABILITIES:
                        print(agent, 'agent is not running')
                        AGENTS_VERIFICATION = False

            if AGENTS_VERIFICATION:
                print(" Analyzer will send receipt to the controller")
                specification_receiptData=jsonData.copy()
                specification_receiptData['receipt'] = specification_receiptData['specification']
                del specification_receiptData['specification']

                topic = event.message.reply_to
                
                Container(Send(url,topic, specification_receiptData)).run()


                AGENTS_SPECIFICATION_LIST={}
                for parameter in jsonData['parameters']:
                    if 'detector' in parameter:

                        agent_name = jsonData['parameters'][parameter]
                        specificationData = AGENTS_CAPABILITIES[agent_name].copy()
                        

                        #send specification for calibration
                        specificationData['parameters']['type']='calibration'
                        specificationData['parameters']['interval_time_s']=dicty['cal_int_time']
                        specificationData['parameters']['samples_size'] = 1
                        specificationData['specification'] = specificationData['capability']
                        del specificationData['capability']


                        #topic to send calibration specification to the agent
                        topic = 'topic://'+specificationData['endpoint']+'/specifications'
                        #add to the list of agents specifications
                        AGENTS_SPECIFICATION_LIST[topic]=specificationData

                #print(AGENTS_SPECIFICATION_LIST)

                global cval,aliceval,bobval,bobval,bobpos,alicepos,accval


                for i in range (int(samples_size)):
                    RESULTS[i]={}

                cval     = np.empty([int(samples_size)])
                aliceval = np.empty([int(samples_size)])
                bobval   = np.empty([int(samples_size)])
                bobpos   = np.empty([int(samples_size)])
                alicepos = np.empty([int(samples_size)])
                accval   = np.empty([int(samples_size)])


                connection = event.connection
                MEASUREMENT_AGENTS= []
                for topic in AGENTS_SPECIFICATION_LIST:### needs to be in parallel
                    topic_reply_to=AGENTS_SPECIFICATION_LIST[topic]['endpoint']+'/receipt/'+SELF_NAME
                    event.container.create_receiver(connection,topic_reply_to,handler=RecvReceipt())
                    MEASUREMENT_AGENTS.append(AGENTS_SPECIFICATION_LIST[topic]['name'])
                #the exec time when the agents will exec the measurement after current Time + delay
                exec_time = datetime.utcnow()+timedelta(0,DELAY)
                for topic in AGENTS_SPECIFICATION_LIST:### needs to be in parallel
                    topic_reply_to=AGENTS_SPECIFICATION_LIST[topic]['endpoint']+'/receipt/'+SELF_NAME
                    AGENTS_SPECIFICATION_LIST[topic]['when']=str(exec_time)
                    Container(Send(url,topic, AGENTS_SPECIFICATION_LIST[topic],self_reply = topic_reply_to)).run()              

class RecvReceipt(MessagingHandler):
    def __init__(self):
        print("receiver forreceipt created")
        super(RecvReceipt, self).__init__()
        self.calibration= False
        
    def on_message(self, event):
        global CALIBRATION_RECEIPT,AGENTS_SPECIFICATION_LIST
        jsonData = json.loads(event.message.body)
        endpoint = jsonData['endpoint']
        name = jsonData['name']
        receipt_type = jsonData['parameters']['type']
        if receipt_type == "calibration" and self.calibration==False:
            self.calibration = True
            
            topic='topic://'+endpoint+'/results'
            connection = event.connection
            event.container.create_receiver(connection,topic,handler=RecvResult())
            
            print(" [x] Calibration Receipt received from\n %r" % name)
            CALIBRATION_RECEIPT[name] = True
            
            print(" [x] Analyzer will send specification for measurement to %r" % name)

            measurement_specification = AGENTS_CAPABILITIES[name].copy()
            

            #send specification for calibration
            measurement_specification['parameters']['type']='measurement'
            measurement_specification['parameters']['interval_time_s']=dicty['cal_int_time']
            measurement_specification['parameters']['samples_size'] = SPECIFICATION_CONTROLLER['parameters']['samples_size']
            measurement_specification['specification'] = measurement_specification['capability']
            del measurement_specification['capability']

            topic = 'topic://'+measurement_specification['endpoint']+'/specifications'
            AGENTS_SPECIFICATION_LIST[topic]=measurement_specification
            
                
            
            



        elif receipt_type == "measurement" and self.calibration==True:
            print(" [x] Mesurment Receipt received from\n %r" % name)
            MESUREMENT_RECEIPT[name]=''
            
            event.receiver.close()                 
            return
        else:
            None

class RecvResult(MessagingHandler):
    def __init__(self):
        super(RecvResult, self).__init__()
        self.received = 0
        self.H_hough = 0        
        
    def on_message(self, event):
        global AGENTS_SPECIFICATION_LIST
        jsonData = json.loads(event.message.body)
        
        name = jsonData['name']
        result_type = jsonData['parameters']['type']
        samples_size = int(jsonData['parameters']['samples_size'])

        print("type RECEIVED IS ", result_type)
        global bin100DONE,bin100,RESULTS,CALIBRATION_RESULT
        global cval,aliceval,bobval,accval
        if result_type == "calibration":
            print("calibration result Received for and  from ", name)
            CALIBRATION_RESULT[name]= np.array(jsonData['resultValues'][1][0])
            if len(CALIBRATION_RESULT)==2:
                #the exec time when the agents will exec the measurement after current Time + delay
                exec_time = str(datetime.utcnow()+timedelta(0,DELAY))
                print(exec_time)
                for topic in AGENTS_SPECIFICATION_LIST:### needs to be in parallel
                    topic_reply_to=AGENTS_SPECIFICATION_LIST[topic]['endpoint']+'/receipt/'+SELF_NAME
                    AGENTS_SPECIFICATION_LIST[topic]['when']=exec_time
                    Container(Send(url,topic, AGENTS_SPECIFICATION_LIST[topic],self_reply = topic_reply_to)).run()
                AGENTS_SPECIFICATION_LIST={}
                Adata = TTdata(fn, CALIBRATION_RESULT[MEASUREMENT_AGENTS[0]], dicty[MEASUREMENT_AGENTS[0]]["chan"], dicty[MEASUREMENT_AGENTS[0]]["sync"], dicty[MEASUREMENT_AGENTS[0]]["pps"], Calibrate = True)

                Bdata = TTdata(fn, CALIBRATION_RESULT[MEASUREMENT_AGENTS[1]], dicty[MEASUREMENT_AGENTS[1]]["chan"], dicty[MEASUREMENT_AGENTS[1]]["sync"], dicty[MEASUREMENT_AGENTS[1]]["pps"], Calibrate = True)
                
                ##############
                coinc  = Coincidences(fn, Adata, Bdata)
                
                print('finding coincidence peak')
                coinc.findPeak()
                coinc.bin100 = -1
                bin100 = coinc.bin100
                bin100DONE = True
                print('coincidence bin: %d'%bin100)
                self.H_hough = coinc.H_rough
                fig = plt
                fig.plot(coinc.H_rough)
                fig.pause(0.05)
                CALIBRATION_RESULT={}
                
        elif result_type =="measurement":        
            self.received+=1    
            index = jsonData['resultValues'][0]
            print("result Received for and  from self.received", index, name,self.received)

            RESULTS[index][name]= np.array(jsonData['resultValues'][1][0])

            if (len(RESULTS[index])==2):

                Adata = TTdata(fn, RESULTS[index][MEASUREMENT_AGENTS[0]], dicty[MEASUREMENT_AGENTS[0]]["chan"], dicty[MEASUREMENT_AGENTS[0]]["sync"], dicty[MEASUREMENT_AGENTS[0]]["pps"], Calibrate = True)

                Bdata = TTdata(fn, RESULTS[index][MEASUREMENT_AGENTS[1]], dicty[MEASUREMENT_AGENTS[1]]["chan"], dicty[MEASUREMENT_AGENTS[1]]["sync"], dicty[MEASUREMENT_AGENTS[1]]["pps"], Calibrate = True)

                
                while bin100DONE== False:
                    None
                


                print("len of cval in index %d is %d" % (index, len(cval)))
                coinc = Coincidences(fn,    Adata, Bdata)        
                coinc.CoincidenceAndRates(bin100)
                acc = coinc.totalAccidentals
                cps = coinc.totalCoincidences
            
                alice = coinc.totalSinglesAlice
                bob   = coinc.totalSinglesBob


                print("CVAL ",cval)
                print("CPS ",cps)
                cval[index]=cps
                accval[index] = acc
                aliceval[index] = alice
                bobval[index] = bob
                print("CVAL ",cval)



                ##### Plot #####
                print("coinc.edge[1:]/1000:",coinc.edge[1:]/1000)
                print("coinc.H",coinc.H)
                print("len de coinc.H",len(coinc.H))
                print("len de coinc.edge",len(coinc.edge[1:]))
                print("max(coinc.H)*1.1]:",[0, max(coinc.H)*1.1])
                print("[coinc.coin_windw_min, coinc.coin_windw_min]:",[coinc.coin_windw_min, coinc.coin_windw_min])
                print("[coinc.coin_windw_max, coinc.coin_windw_max]:",[coinc.coin_windw_max, coinc.coin_windw_max])
                print("[coinc.acc_windw_min, coinc.acc_windw_min]:",[coinc.acc_windw_min, coinc.acc_windw_min])
                print("[coinc.acc_windw_max, coinc.acc_windw_max]:",[coinc.acc_windw_max, coinc.acc_windw_max])

                
                fig = plt
                fig.subplot(2,1,1)
                fig.plot(coinc.edge[1:]/1000,coinc.H, color = 'black')
                fig.plot([coinc.coin_windw_min, coinc.coin_windw_min],[0, max(coinc.H)*1.1], color = 'green')
                fig.plot([coinc.coin_windw_max, coinc.coin_windw_max],[0, max(coinc.H)*1.1], color = 'green')
                fig.plot([coinc.acc_windw_min, coinc.acc_windw_min],[0, max(coinc.H)*1.1], color = 'red')
                fig.plot([coinc.acc_windw_max, coinc.acc_windw_max],[0, max(coinc.H)*1.1], color = 'red')
                
                fig.subplot(2,1,2)
                fig.plot(cval, color = 'green')
                fig.plot(accval, color = 'red')
                fig.pause(0.05)
                
                print('coincidences: %d; s1: %d; s2: %d; accidentals: %d'%(cps,alice,bob,acc))
                
                
                
                ##############
                del RESULTS[index]

                print('coincidences: %d; s1: %d; s2: %d; accidentals: %d'%(cps,alice,bob,acc))
                
                Result_msg = SPECIFICATION_CONTROLLER.copy()
                del Result_msg['specification']
                topic = 'topic:///multiverse/qnet/coincidence/results'


                #########################RESULTS
                print(len(Result_msg['results']))
                Result_msg['timestamp'] = startTime
                Result_msg['resultValues']=[[]]*len(Result_msg['results'])
                Result_msg['resultValues'][0]=(coinc.edge[1:]/1000).tolist()
                Result_msg['resultValues'][1]=coinc.H.tolist()
                Result_msg['resultValues'][2]=[coinc.coin_windw_min, coinc.coin_windw_min]
                Result_msg['resultValues'][3]=[coinc.coin_windw_max, coinc.coin_windw_max]
                Result_msg['resultValues'][4]=[coinc.acc_windw_min, coinc.acc_windw_min]
                Result_msg['resultValues'][5]=[coinc.acc_windw_max, coinc.acc_windw_max]
                Result_msg['resultValues'][6]=self.H_hough.tolist()
                #Result_msg['resultValues'][7]=cval.tolist()
                #Result_msg['resultValues'][8]=accval.tolist()
                    


                Result_msg['result'] = SPECIFICATION_CONTROLLER['specification']
                

                
                print("analyzer will send result to the controller" ,Result_msg)
                
                Container(Send(url,topic, Result_msg)).run()
            
            if len(RESULTS)==0:
                
                


                cval     = np.array([])
                aliceval = np.array([])
                bobval   = np.array([])
                bobpos   = np.array([])
                alicepos = np.array([])
                accval   = np.array([])
                
                print("=============================================")
                print("==================THE END====================")
                print("=============================================")
                
                print(RESULTS)
            


            if self.received==samples_size:
                print("will close receiver for ", name,self.received)
                self.received=0
                event.receiver.close()
                return

def send_capability(url,topic,period):
    while True:
        # Publish Capability in "/capabilities"
        capabilityFile = open('conf/capability.json', 'r')
        capabilityData = json.load(capabilityFile)
        capabilityFile.close()
        Container(Send(url,topic, capabilityData)).run()
        time.sleep(period)


def main():
    #publishing the analyzer capability
    topic = 'topic://'+'/capabilities'
    thread_send_capability = Thread(target=send_capability, args=(url,topic,PERIOD))
    thread_send_capability.start()
    Container(Receive(url)).run()


if __name__ == '__main__':
    try:
        print("===CoincidenceAnalyzer===")
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

