"""Named arena tabs; run state remains in the existing run journal."""
import json,threading,uuid
from pathlib import Path
from datetime import datetime,timezone
class ArenaStore:
 def __init__(self,path):
  self.path=Path(path);self.lock=threading.RLock()
  try:self.arenas=json.loads(self.path.read_text(encoding='utf-8'))
  except (OSError,ValueError):self.arenas={}
  self.arenas.setdefault('main',{'id':'main','name':'Original arena','created_at':datetime.now(timezone.utc).isoformat()})
 def get(self,arena_id):
  with self.lock:return dict(self.arenas[arena_id]) if arena_id in self.arenas else None
 def create(self,name=''):
  with self.lock:
   arena={'id':uuid.uuid4().hex[:12],'name':name.strip() or 'Arena '+str(len(self.arenas)+1),'created_at':datetime.now(timezone.utc).isoformat()}
   self.arenas[arena['id']]=arena;self.save();return dict(arena)
 def rename(self,arena_id,name):
  with self.lock:
   if arena_id not in self.arenas:return None
   self.arenas[arena_id]['name']=name.strip();self.save();return dict(self.arenas[arena_id])
 def save(self):
  import time
  self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.arenas),encoding='utf-8')
  for attempt in range(8):
   try:temp.replace(self.path);break
   except PermissionError:
    if attempt==7:raise
    time.sleep(.05*(attempt+1))
 def listing(self,runs):
  with self.lock:
   entries=[]
   for arena in self.arenas.values():
    active=[r for r in runs.values() if r.get('arena_id','main')==arena['id'] and r['status'] in ('queued','running','stopping')]
    entries.append({**arena,'active_id':active[0]['id'] if active else None,'active_status':active[0]['status'] if active else None})
   return entries
