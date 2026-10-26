"""A dedicated loopback origin for each run/harness preview."""
import socket,threading
import uvicorn
class PreviewOrigins:
 def __init__(self,factory):self.factory=factory;self.lock=threading.RLock();self.servers={}
 def port(self,rid,harness):
  key=(rid,harness)
  with self.lock:
   if key in self.servers:return self.servers[key][0]
   sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
   if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   try:
    server=uvicorn.Server(uvicorn.Config(self.factory(harness,rid),host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
    self.servers[key]=(port,server,thread,sock);thread.start()
   except Exception:
    self.servers.pop(key,None);sock.close();raise
   return port
 def close(self):
  with self.lock:
   for port,server,thread,sock in self.servers.values():server.should_exit=True
