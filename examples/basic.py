import microgear.client as microgear
import time
import logging

appid = "I9Z4JIFFt9bx3tE:QgEpVOtmWPaN7n5pTIwMl8D6b"
gearkey = "I9Z4JIFFt9bx3tE"
gearsecret =  "QgEpVOtmWPaN7n5pTIwMl8D6b"

microgear.create(gearkey,gearsecret,appid,{'debugmode': True})

def connection():
    logging.info("Now I am connected with netpie")

def subscription(topic,message):
    logging.info(topic+" "+message)

def disconnect():
    logging.debug("disconnect is work")

microgear.setalias("doraemon")
microgear.on_connect = connection
microgear.on_message = subscription
microgear.on_disconnect = disconnect
microgear.subscribe("/mails")
microgear.connect(False)

while True:
	if(microgear.connected):
		microgear.chat("doraemon","Hello world."+str(int(time.time())))
	time.sleep(3)
