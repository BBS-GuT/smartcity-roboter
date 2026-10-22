"""Optional local integration test: pip install -r mqtt/requirements-test.txt. No ROS/hardware."""
import argparse
import asyncio,base64,json,subprocess,sys,threading,time,socket,zlib
from concurrent.futures import CancelledError
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from amqtt.broker import Broker
import paho.mqtt.client as mqtt

options=argparse.ArgumentParser(description='Local synthetic MQTT and camera load test')
options.add_argument('--load-seconds',type=float,default=15.0)
args=options.parse_args()
if not 0 < args.load_seconds <= 300:
 options.error('--load-seconds must be greater than 0 and at most 300')

def port():
 s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
bp,hp=port(),port()
loop=asyncio.new_event_loop()
broker=None
async def start():
 global broker
 broker=Broker({'listeners':{'default':{'type':'tcp','bind':f'127.0.0.1:{bp}'}},'plugins':{'amqtt.plugins.authentication.AnonymousAuthPlugin':{'allow_anonymous':True}}})
 await broker.start()
def serverloop():
 asyncio.set_event_loop(loop);loop.run_until_complete(start());loop.run_forever()
t=threading.Thread(target=serverloop,daemon=True);t.start()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  if self.path=='/api/status':
   payload=b'{"roboter":"RMTEST","fahren":false,"akku":12.1,"ki":null}'
  elif self.path=='/api/grundbetrieb':
   self.send_response(204);self.end_headers();return
  elif self.path=='/api/mqtt/camera':
   Handler.frame += 1
   payload=json.dumps({'kind':'camera','frame_key':str(Handler.frame),'frame_id':'synthetic-camera',
                       'captured_at':'2026-10-21T12:00:00+00:00','observed_at':'2026-10-21T12:00:00+00:00',
                       'encoding':'jpeg','width':640,'height':360,
                       'data_b64':base64.b64encode(Handler.jpeg).decode()}).encode()
  elif self.path=='/api/mqtt/depth':
   payload=json.dumps({'kind':'depth','frame_key':'synthetic-depth','frame_id':'depth-frame',
                       'captured_at':None,'observed_at':'2026-10-21T12:00:00+00:00',
                       'encoding':'16UC1','width':2,'height':2,'step':4,'is_bigendian':False,
                       'compression':'zlib','data_b64':base64.b64encode(zlib.compress(b'\x01\x00\x02\x00\x03\x00\x04\x00')).decode()}).encode()
  elif self.path=='/api/mqtt/scans':
   payload=json.dumps([{'kind':'scan','topic':'/scan0','index':0,'ranges':[0.4,None,2.0],
                        'intensities':[1.0,2.0,3.0]},
                       {'kind':'scan','topic':'/scan1','index':1,'ranges':[1.4,2.2],
                        'intensities':[]}]).encode()
  else:
   self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
Handler.frame=0
Handler.jpeg=(Path(__file__).resolve().parents[1]/'docs/bilder/panel_dashboard.jpg').read_bytes()
http=ThreadingHTTPServer(('127.0.0.1',hp),Handler)
threading.Thread(target=http.serve_forever,daemon=True).start()
received=[]
retained_details=[]
camera_times=[]
reader=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='independent-review-reader')
for _ in range(100):
 try: reader.connect('127.0.0.1',bp);break
 except OSError:time.sleep(.05)
reader.on_connect=lambda c,u,f,r,p:c.subscribe('review/robots/RMTEST/#',qos=1)
def on_message(c,u,m):
 received.append((m.topic,m.payload))
 if '/details/' in m.topic:retained_details.append(m.retain)
 if m.topic.endswith('/details/camera'):camera_times.append(time.monotonic())
reader.on_message=on_message
reader.loop_start()
proc=subprocess.Popen([sys.executable,'mqtt/panel_bridge.py','--host','127.0.0.1','--port',str(bp),'--robot','RMTEST','--base-topic','review/robots','--panel',f'http://127.0.0.1:{hp}','--interval','.2'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
def wait(pred):
 for _ in range(150):
  if pred():return
  time.sleep(.1)
 raise AssertionError(received)
try:
 wait(lambda:any(t.endswith('/availability') and p==b'online' for t,p in received))
 states=[json.loads(p) for t,p in received if t.endswith('/panel/state')]
 assert states and states[0]['payload']['akku']==12.1 and states[0]['payload']['ki'] is None
 wait(lambda:any(t.endswith('/panel/state') and json.loads(p)['last_broker_ack_seq'] is not None for t,p in received))
 print('PASS independent receiver: panel state, null, identity, online, broker ACK sequence')
 wait(lambda:len(camera_times)>=20)
 assert camera_times[19]-camera_times[0]<1.5, 'Local camera stream is below expected 20 fps ceiling'
 wait(lambda:all(any(t.endswith('/details/'+name) for t,p in received)
                     for name in ('depth','scan0','scan1')))
 details={name:[json.loads(p) for t,p in received if t.endswith('/details/'+name)]
          for name in ('camera','depth','scan0','scan1')}
 cameras=details['camera']
 assert len({item['payload']['frame_key'] for item in cameras})>=3
 assert all(base64.b64decode(item['payload']['data_b64'])==Handler.jpeg for item in cameras)
 assert all(item['payload']['encoding']=='jpeg' and item['state_ack_seq'] is not None for item in cameras)
 assert zlib.decompress(base64.b64decode(details['depth'][0]['payload']['data_b64']))==b'\x01\x00\x02\x00\x03\x00\x04\x00'
 assert details['scan0'][0]['payload']['ranges']==[0.4,None,2.0]
 assert details['scan1'][0]['payload']['topic']=='/scan1'
 assert all(item['transport_schema']=='panel-detail/1' and item['robot_id']=='RMTEST'
            for group in details.values() for item in group)
 assert retained_details and not any(retained_details)
 print('PASS live camera JPEG frames, native depth bytes and both scans at independent receiver')
 load_start=time.monotonic()
 start_count=len(camera_times)
 start_generated=Handler.frame
 time.sleep(args.load_seconds)
 elapsed=time.monotonic()-load_start
 frame_count=len(camera_times)-start_count
 generated=Handler.frame-start_generated
 assert frame_count>0, 'No camera frames received during load test'
 camera_payloads=[p for t,p in received if t.endswith('/details/camera')][-frame_count:]
 assert len(camera_payloads)==frame_count
 assert all(base64.b64decode(json.loads(p)['payload']['data_b64'])==Handler.jpeg
            for p in camera_payloads), 'Camera image changed during transfer'
 assert frame_count>=generated-1, 'Camera frames were lost between HTTP source and MQTT receiver'
 print(f'PASS synthetic camera load: {frame_count} received/{generated} generated in '
       f'{elapsed:.1f}s = {frame_count/elapsed:.1f} fps, '
       f'{sum(map(len,camera_payloads))/elapsed/1_000_000:.2f} MB/s payload')
 http.shutdown();http.server_close()
 wait(lambda:any(t.endswith('/availability') and p==b'offline' for t,p in received))
 print('PASS source loss: offline rather than stale online')
 # restore HTTP endpoint and ensure recovery with new boot
 http=ThreadingHTTPServer(('127.0.0.1',hp),Handler)
 threading.Thread(target=http.serve_forever,daemon=True).start()
 wait(lambda:len({json.loads(p)['boot_id'] for t,p in received if t.endswith('/panel/state')})>=2)
 print('PASS source recovery: fresh state under a new boot identity')
 boots_before={json.loads(p)['boot_id'] for t,p in received if t.endswith('/panel/state')}
 try:
  asyncio.run_coroutine_threadsafe(broker.shutdown(),loop).result(5)
 except CancelledError:
  # amqtt can cancel its shutdown future after closing the listener.
  pass
 time.sleep(1)
 asyncio.run_coroutine_threadsafe(start(),loop).result(5)
 wait(lambda:bool({json.loads(p)['boot_id'] for t,p in received if t.endswith('/panel/state')} - boots_before))
 print('PASS broker restart: independent receiver gets fresh state')
 proc.terminate();proc.wait(8)
 # Windows terminate() forcibly ends the process; it does not exercise SIGTERM cleanup.
 if sys.platform == 'win32':
  print('PASS test process cleanup (Windows forced termination; graceful shutdown not tested)')
 else:
  assert proc.returncode == 0, proc.returncode
  print('PASS clean shutdown',proc.returncode)
finally:
 if proc.poll() is None:proc.kill();proc.wait()
 print(proc.stdout.read()[-1500:])
 reader.disconnect();reader.loop_stop();http.shutdown();http.server_close()

 async def finish():
  # Final fixture teardown: amqtt 0.11.3 shutdown() can propagate cancellation
  # from broadcast tasks after forced Windows process termination. The actual
  # broker restart above still exercises shutdown(); here close every listener
  # and await every remaining task explicitly before closing the event loop.
  for server in broker._servers.values():
   await server.close_instance()
  if not broker._broadcast_shutdown_waiter.done():
   broker._broadcast_shutdown_waiter.set_result(True)
  await asyncio.gather(broker._broadcast_task,return_exceptions=True)
  tasks=[task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
  for task in tasks:task.cancel()
  await asyncio.gather(*tasks,return_exceptions=True)
 try:
  asyncio.run_coroutine_threadsafe(finish(),loop).result(5)
 finally:
  loop.call_soon_threadsafe(loop.stop)
  t.join(5)
  if t.is_alive():raise RuntimeError('Broker test thread did not stop')
  loop.close()
