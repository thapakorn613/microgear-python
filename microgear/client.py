import logging
from urlparse import urlparse
import json
import oauth2 as oauth
import microgear
import cache
import urllib
import random
import time
import re
import string
import paho.mqtt.client as mqtt


def do_nothing(arg1=None, arg2=None):
    pass

subscribe_list = []
pubilsh_list = []
on_disconnect = do_nothing
on_present = do_nothing
on_absent = do_nothing
on_connect = do_nothing
on_message = do_nothing
on_error = do_nothing
on_reject = do_nothing

def create(gearkey,gearsecret, appid="", args = {}):
    if 'debugmode' in args:
        logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%d/%m/%Y %I:%M:%S %p',
                        )
    else:
        logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%d/%m/%Y %I:%M:%S %p',
                        )

    if 'scope' in args:
        matchScope = re.match( r'^(\w+:[a-zA-Z\/]+,*)+$', args['scope'])
        if matchScope:
            microgear.scope = args["scope"]
        else:
            microgear.scope = ""
            logging.warning("Specify scope is not valid")
        
    microgear.gearkey = gearkey
    microgear.gearsecret = gearsecret
    microgear.appid = appid

def client_on_connect(client, userdata, rc):
    global pubilsh_list
    global subscribe_list
    logging.debug("Connected with result code "+str(rc))
    if rc == 0 :
        on_connect()
        if(microgear.mqtt_client):
            for topic in subscribe_list :
                client.subscribe(topic)
                logging.debug("Auto subscribe "+topic )
            subscribe_list = []
        else:
            on_error("Microgear currently is not available.")
            logging.error("Microgear currently is not available.")
        if(microgear.mqtt_client):
            for topic in pubilsh_list :
                client.publish(topic[0],topic[1])
            pubilsh_list = []
        else:
            on_error("Microgear currently is not available.")
            logging.error("Microgear currently is not available.")
    elif rc == 1 :
        on_reject("Incorrect protocol version.")
        logging.warning("Incorrect protocol version.")
    elif rc == 2 :
        on_reject("Invalid client identifier.")
        logging.warning("Invalid client identifier.")
    elif rc == 3 :
        on_reject("Server unavailable.")
        logging.warning("Server unavailable.")
    elif rc == 4 :
        on_reject("Bad username or password.")
        logging.warning("Bad username or password.")
    elif rc == 5 :
        on_reject("Not authorised.")
        logging.warning("Not authorised.")
    else:
        on_reject("Unknown reason")
        logging.warning("Unknown reason")

        
def client_on_message(client, userdata, msg):
    global pubilsh_list
    global subscribe_list
    topics = msg.topic.split("/")
    if topics[1] == "&present":
        on_present(str(msg.payload))
    elif topics[1] == "&absent":
        on_absent(str(msg.payload))
    else:
        on_message(msg.topic,str(msg.payload))
    if(microgear.mqtt_client):
        for topic in subscribe_list :
            client.subscribe(topic)
            logging.debug("Auto subscribe "+topic )
        subscribe_list = []
    else:
        on_error("Microgear currently is not available.")
        logging.error("Microgear currently is not available.")
        
    if(microgear.mqtt_client):
        for topic in pubilsh_list :
            client.publish(topic[0],topic[1])
        pubilsh_list = []
    else:
        on_error("Microgear currently is not available.")
        logging.error("Microgear currently is not available.")
        

def client_on_subscribe(client, userdata, mid, granted_qos):
    ## TODO: Check subscribe fail
    pass

def client_on_disconnect(client, userdata, rc):
    on_disconnect()
    logging.debug("Diconnected with result code "+str(rc))

def connect():
    global subscribe_list
    times = 1
    while not microgear.accesstoken:
        get_token()
        time.sleep(times)
        times = times+1

    microgear.mqtt_client = mqtt.Client(microgear.accesstoken["token"])
    subscribe_list.append('/&id/'+microgear.accesstoken["token"]+'/#')
    endpoint = microgear.accesstoken["endpoint"].split("//")[1].split(":")
    username = microgear.gearkey+"%"+str(int(time.time()))
    password = hmac(microgear.accesstoken["secret"]+"&"+microgear.gearsecret,microgear.accesstoken["token"]+"%"+username)
    microgear.mqtt_client.username_pw_set(username,password)
    microgear.mqtt_client.connect(endpoint[0], int(endpoint[1]), 60)

    microgear.mqtt_client.on_connect = client_on_connect
    microgear.mqtt_client.on_message = client_on_message
    microgear.mqtt_client.on_subscribe = client_on_subscribe
    microgear.mqtt_client.on_disconnect = client_on_disconnect

    microgear.mqtt_client.loop_forever()

def resettoken():
    cache.delete_item("microgear.cache")

def subscribe(topic):
    global subscribe_list
    topic = "/"+microgear.appid+topic
    subscribe_list.append(topic)

def publish(topic,message):
    global pubilsh_list
    pubilsh_list.append(["/"+microgear.appid+topic,message])

def setname(topic):
    microgear.gearname = topic
    subscribe("/gearname/"+topic)

def chat(topic,message):
    publish("/gearname/"+topic,message)

def readstream(stream, filter):
    publish('/@readstream/'+stream,'{"filter":"'+filter+'"}')

def writestream(stream,data):
    publish('/@writestream/'+stream,'{"data":'+data+'}')

def get_token():
    logging.debug("Check stored token.")
    cached = cache.get_item("microgear.cache")
    if not cached:
        cached = cache.set_item("microgear.cache", {})
    else:
        microgear.accesstoken = cached["accesstoken"]
        for x,y in microgear.accesstoken.items():
            microgear.accesstoken[x] = str(y)

    if microgear.accesstoken:
        endpoint = microgear.accesstoken.get("endpoint").split("//")[1].split(":")
        microgear.gearexaddress = endpoint[0]
        microgear.gearexport = endpoint[1]
    else:
        if cached.get("requesttoken"):
            get_accesstoken(cached)
        else:
            get_requesttoken(cached)


def get_requesttoken(cached):
    logging.debug("Requesting a request token.")
    consumer = oauth.Consumer(key=microgear.gearkey, secret=microgear.gearsecret)
    client = oauth.Client(consumer)
    verifier = ''.join(random.sample(string.lowercase+string.digits,8))
    params = {'oauth_callback': "scope=%s&appid=%s&verifier=%s" % (microgear.scope, microgear.appid, verifier)}
    resp, content = client.request(microgear.gearauthrequesttokenendpoint, "POST", body=urllib.urlencode(params))
    matchContent = re.match( r'oauth_token=(.*?)&oauth_token_secret=(.*?).*', content)
    if matchContent:
        contents = content.split("&")
        cached["requesttoken"] = {
        "token": contents[0].split("=")[1],
        "secret": contents[1].split("=")[1],
        "verifier": verifier
        }
        cache.set_item("microgear.cache", cached)
        microgear.requesttoken = cached["requesttoken"]
        get_accesstoken(cached)
    else:
        #logging.warning("Request token is not issued, please check your appkey and appsecret.")
        on_error("Request token is not issued, please check your appkey and appsecret.")
        logging.error("Request token is not issued, please check your appkey and appsecret.")

def get_accesstoken(cached):
    microgear.requesttoken = cached.get("requesttoken")
    #send requesttoken to obtain accesstoken
    logging.debug("Already has request token.")
    #logging.debug(json.dumps(microgear.requesttoken))
    logging.debug("Requesting an access token.")
    token = oauth.Token(key=microgear.requesttoken.get("token"), secret=microgear.requesttoken.get("secret"))
    consumer = oauth.Consumer(key=microgear.gearkey, secret=microgear.gearsecret)
    client = oauth.Client(consumer, token)
    params = { "oauth_verifier": microgear.requesttoken["verifier"]}
    resp, content = client.request(microgear.gearauthaccesstokenendpoint, "POST", body=urllib.urlencode(params))
    matchContent = re.match( r'endpoint=(.*?)&oauth_token=(.*?)&oauth_token_secret=(.*?).*', content)
    if matchContent:
        contents = content.split("&")
        cached["accesstoken"] = {
        "token": contents[1].split("=")[1],
        "secret": contents[2].split("=")[1],
        "endpoint": urllib.unquote(contents[0].split("=")[1]).decode('utf8')
        }
        cache.set_item("microgear.cache", cached)
        microgear.accesstoken = cached["accesstoken"]
    else:
        #logging.warning("Access token is not issued, please check your consumerkey and consumersecret.")
        on_error("Access token is not issued, please check your consumerkey and consumersecret.")
        logging.error("Access token is not issued, please check your consumerkey and consumersecret.")

def hmac(key, message):
    import base64
    import hmac
    import hashlib
    import urllib

    hash = hmac.new(key, message, hashlib.sha1).digest()
    password = base64.encodestring(hash)
    password = password.strip()

    return password
