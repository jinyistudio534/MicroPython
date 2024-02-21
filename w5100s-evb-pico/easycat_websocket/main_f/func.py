import network as net
import uasyncio as a
import json
import ujson
from random import randint
from machine import Pin
import gc
from async_websocket_client import AsyncWebsocketClient
from w5x00 import w5x00_init
from easycat import EasyCAT
from stopwatch import StopWatch

ecout = {'byte0':0,'byte1':0,'byte2':0,'byte3':0,'byte4':0,'byte5':0,'byte6':0,'byte7':0,
         'byte8':0,'byte9':0,'byte10':0,'byte11':0,'byte12':0,'byte13':0,'byte14':0,'byte15':0,
         'byte16':0,'byte17':0,'byte18':0,'byte19':0,'byte20':0,'byte21':0,'byte22':0,'byte23':0,
         'byte24':0,'byte25':0,'byte26':0,'byte27':0,'byte28':0,'byte29':0,'byte30':0,'byte31':0}

ecxq = []
easycat = EasyCAT(1,Cs=8,Sck=10,Mosi=11,Miso=12)

async def MainApp():  
    global ecout,ecxq

    bx  = False
    for i in range(0,32):   
        s1 = 'byte{}'.format(i)
        if ecout[s1] != easycat.BufferOut.Byte[i]:
            print('{}='.format(s1),easycat.BufferOut.Byte[i])
            bx = True
        ecout[s1] = easycat.BufferOut.Byte[i]

    if bx==True:
        ecxq.append(1)       
   
# --------------------------------------------------------------------------------------------
async def ec_loop():
  bt0 = StopWatch()
  if easycat.Init():
    _ope = 0
    _watch = 0 
    while True:      
      st = easycat.MainTask()    
      if _watch != st:
        _watch = st
        if st & 0x80:        
          print("Watchdog")
        else:
          print("Not Watchdog") 

      if _ope != easycat.Operational:
        _ope = easycat.Operational
        if _ope:
          print("Operational")       
        else:
          print("Not Operational")

      if easycat.Operational:
        await MainApp()     
      else:
        if bt0.duration(1000,True):
          print(".",end='')        

      await a.sleep_ms(5)
  else:
    print('init false')

# trying to read config --------------------------------------------------------
# if config file format is wrong, exception is raised and program will stop
print("Trying to load config...")

f = open("../config.json")
text = f.read()
f.close()
config = json.loads(text)
del text
# ------------------------------------------------------------------------------

print("Create WS instance...")
# create instance of websocket
ws = AsyncWebsocketClient(config['socket_delay_ms'])

print("Created.")

# this lock will be used for data interchange between loops --------------------
# better choice is to use uasynio.queue, but it is not documented yet
lock = a.Lock()
# this array stores messages from server
data_from_ws = []
# ------------------------------------------------------------------------------

# SSID - network name
# pwd - password
# attempts - how many time will we try to connect to WiFi in one cycle
# delay_in_msec - delay duration between attempts
async def wifi_connect(SSID: str, pwd: str, attempts: int = 3, delay_in_msec: int = 200) -> network.WLAN:
    wifi = net.WLAN(net.STA_IF)

    wifi.active(1)
    count = 1

    while not wifi.isconnected() and count <= attempts:
        print("WiFi connecting. Attempt {}.".format(count))
        if wifi.status() != net.STAT_CONNECTING:
            wifi.connect(SSID, pwd)
        await a.sleep_ms(delay_in_msec)
        count += 1

    if wifi.isconnected():
        print("ifconfig: {}".format(wifi.ifconfig()))
    else:
        print("Wifi not connected.")

    return wifi

status_led = Pin("LED", Pin.OUT)
async def process_data(data):
    global status_led 
    try:
        if data:
            print("Data > {}".format(data)) # Expected format {"data" : PAYLOAD | 1 | 0}
            json_input = json.loads(data)           
            for key, value in json_input.items():   
                if key.find('byte')>=0:
                    k1 = key.replace('byte','')
                    v1 = int(value)
                    easycat.BufferIn.Byte[int(k1)] = v1
                    print('byte{} = {}'.format(k1,v1))

            
            return
                
    except:
        print('Exception parsing in JSON')
# ------------------------------------------------------
# Main loop function: blink and send data to server.
# This code emulates main control cycle for controller.
def get_data():  
    global ecout
    # Cretae a JSON string
    return ujson.dumps({
        "payload": ecout
    })

async def send_telemetry():
    global lock
    global data_from_ws
    global ws
    global ecout, ecxq   
   
    # Main "work" cycle. It should be awaitable as possible.    
  
    while True:    
        
        if ws is not None:
            # delay to send data. 5 min, 5 * 60 * 1000 ms / 500 ms , 600
            if await ws.open(): 
                s1=''
                if len(ecxq)>0:
                    del(ecxq[0]) 

                    s1 = get_data()
                    await ws.send(s1)                                                          
                    print('   ws :',s1)              
                   
            # lock data archive and process in data
            await lock.acquire()
            if data_from_ws:
                for item in data_from_ws:
                    await process_data(item)
                data_from_ws = []
            lock.release()
            gc.collect()

        await a.sleep_ms(200)

# ------------------------------------------------------
# Task for read loop
async def read_loop():
    global config
    global lock
    global data_from_ws

    # may be, it
    wifi = w5x00_init() 

    while True:
        gc.collect()

        while not wifi.isconnected():
            await a.sleep_ms(1000)
            print(wifi.regs())

        try:
            print("Handshaking...")
            # connect to test socket server with random client number
            if not await ws.handshake(uri = config["server"]):
                raise Exception('Handshake error.')
            print("...handshaked.")

            mes_count = 0
            while await ws.open():
                data = await ws.recv()
                # print("Data: " + str(data) + "; " + str(mes_count))
                # close socket for every 10 messages (even ping/pong)
                if mes_count == 10:
                    await ws.close()
                    print("ws is open: " + str(await ws.open()))
                mes_count += 1

                if data is not None:
                    await lock.acquire()
                    data_from_ws.append(data)
                    lock.release()

                await a.sleep_ms(50)
        except Exception as ex:
            print("Exception: {}".format(ex))
            await a.sleep(1)
# ------------------------------------------------------
