#!/usr/bin/env python
import pika, sys, os, json,time

SERVER_NAME = 'localhost'
SELF_NAME = 'controller'


def main():
    
    
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=SERVER_NAME))
    channel = connection.channel()
    channel.exchange_declare(exchange='topic_logs', exchange_type='topic')
    

    capabilityFile = open('coincidence-analyzer.json', 'r')
    capabilityData = json.load(capabilityFile)
    capabilityFile.close()

    endpoint = capabilityData['endpoint']





    print("capability will be received from the analyzer every PERIODE")
    
    input("press enter if you want to analyze coincidence between d1 and d2")
    print("=== I will Pub spec(d1/d2) <capability.endpoint>/specifications ===")
    result = channel.queue_declare('', exclusive=True)
    queue_name = result.method.queue
    binding_keys = {endpoint+'/specifications/receipt',endpoint+'/results'}
    for binding_key in binding_keys:
        channel.queue_bind(
            exchange='topic_logs', queue=queue_name, routing_key=binding_key)
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    print("=======================")

    specificationFile = open('analyzer_specification.json', 'r')
    specificationData = json.load(specificationFile)
    specificationFile.close()
    routing_key = endpoint+'/specifications'
    channel.basic_publish( exchange='topic_logs', routing_key=routing_key, body=json.dumps(specificationData))
    
    channel.start_consuming()



def callback(ch, method, properties, body):
    
    #####

    endpoint=json.loads(body)['endpoint']
    if 'qnet/coincidence' in endpoint:
        print(" [x] %r:%r" % (method.routing_key, json.loads(body)))
        print("=======================")


if __name__ == '__main__':
    try:
        print("===The Controller===")
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)



