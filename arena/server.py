"""Local Agent Arena; credentials stay outside HTTP responses."""
import io,json,os,re,secrets,shutil,subprocess,sys,threading,time,uuid,zipfile,urllib.request,urllib.error,hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from showdown import ROOT,HARNESS as CORE_HARNESS,auth_env,config,write_json,seconds
from roster import EXTRA,API_HARNESSES,CATALOG
HARNESS={**CORE_HARNESS,**EXTRA}
from aider_output import summary as aider_summary,failure_reason as aider_failure
from fastapi import FastAPI,HTTPException,Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse,HTMLResponse,JSONResponse,PlainTextResponse,Response
from pydantic import BaseModel,Field,SecretStr
import uvicorn
HERE=Path(__file__).resolve().parent
PRIVATE=Path(os.environ.get('ARENA_DATA_DIR',str(ROOT/'.arena'))).expanduser().resolve()
JOBS=PRIVATE/'jobs'
PRIVATE.mkdir(parents=True,exist_ok=True);JOBS.mkdir(parents=True,exist_ok=True)
TOKEN=secrets.token_urlsafe(32);PORT=int(os.environ.get('ARENA_PORT','8090'))
PREVIEW_PORTS={'codex':8095,'opencode':8096,'pi':8097,'aider':8098,'goose':8101,'cline':8102,'mini-swe-agent':8103,'openhands':8104,'qwen':8105}
DOCKER=shutil.which('docker') or r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
HARBOR=Path(sys.executable).with_name('harbor.exe' if os.name=='nt' else 'harbor')
WORKSPACE_LOCK=threading.Lock()
MAX_ACTIVE_AGENTS=max(1,min(64,int(os.environ.get('ARENA_MAX_AGENTS','14'))))
AGENT_SLOTS=threading.BoundedSemaphore(MAX_ACTIVE_AGENTS)
LOCK=threading.RLock();RUNS={};PROCESSES={};READY={};MODELS=[];NATIVE_MODELS={}
AIDER_KEY='';AIDER_MODELS=set()
CLAUDE_KEY='';CLAUDE_MODELS={}
from foundry_api import DEFAULT_ENDPOINT,DEFAULT_PROJECT
FOUNDRY_KEY='';FOUNDRY_ENDPOINT=DEFAULT_ENDPOINT;FOUNDRY_PROJECT=DEFAULT_PROJECT;FOUNDRY_MODELS={}
PREFERRED_MODELS=['gpt-6-sol','gpt-6.1-sol','gpt-6-luna','gpt-5.6-sol','gpt-5.6-terra','gpt-5.6-luna']
from arena_sessions import ArenaStore
ARENAS=ArenaStore(PRIVATE/'arenas.json')
STATE=PRIVATE/'state.json';PRESETS={'build':'01-build','repair':'02-repair','search':'03-search'}
CONTRACT='Work in /app. Complete the user request using the provided local tools. Do not invoke another AI agent, model, or external service. Do not read or modify credentials or runner logs. If building a browser app, make /app/index.html the entry point, prefer self-contained HTML/CSS/JavaScript, and do not require external assets or a running backend. Describe what you finished. Only files under /app are collected.'
if STATE.exists():
 try:
  RUNS=json.loads(STATE.read_text(encoding='utf-8'))
  for r in RUNS.values():
   if r['status'] in ('queued','running','stopping'):
    r['status']='interrupted'
    for i in r['contestants'].values():
     if i['status'] in ('queued','starting','running','verifying'):i['status']='interrupted'
 except (ValueError,OSError):RUNS={}
 for run in RUNS.values():run['created_at']=run['created_at'].removesuffix('ZZ')+'Z' if run['created_at'].endswith('ZZ') else run['created_at']
def persist():
 with LOCK:
  p=STATE.with_suffix('.tmp');p.write_text(json.dumps(RUNS,ensure_ascii=True),encoding='utf-8')
  # Windows readers/antivirus can temporarily hold the destination during rename.
  for attempt in range(8):
   try:p.replace(STATE);break
   except PermissionError:
    if attempt==7:raise
    time.sleep(.05*(attempt+1))
def command(args,env=None,timeout=45):
 return subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=timeout)
def ordered_models(models):
 values=set(models)
 return [m for m in PREFERRED_MODELS if m in values]+sorted(values-set(PREFERRED_MODELS))

def openai_text_models():
 return {m for m in AIDER_MODELS if re.match(r'^(gpt-|o[134](?:-|$))',m) and not re.search(r'audio|realtime|image|search|transcrib|tts|whisper|moderation|embedding|instruct',m,re.I)}

def model_catalogs(provider='default'):
 if provider=='foundry':return {h:ordered_models(m for m,info in FOUNDRY_MODELS.items() if h!='codex' or info['responses']) for h in HARNESS}
 api_models=openai_text_models() if AIDER_KEY else set()
 catalogs={h:ordered_models(set(NATIVE_MODELS.get(h,MODELS) if READY.get(h) else [])|api_models) for h in CORE_HARNESS}
 for h in API_HARNESSES:catalogs[h]=ordered_models(api_models)
 for h in HARNESS:
  if h!='codex':catalogs[h]=ordered_models(set(catalogs[h])|set(CLAUDE_MODELS))
 return catalogs

def personal_ready():
 return {h:bool(READY.get(h) or AIDER_KEY or (h!='codex' and CLAUDE_KEY)) for h in HARNESS}

def personal_route(h,model):
 if model in CLAUDE_MODELS:return 'anthropic'
 if h in API_HARNESSES or not READY.get(h) or model not in NATIVE_MODELS.get(h,MODELS):return 'openai'
 return 'subscription'

def catalog_payload():
 from anthropic_pricing import load as load_anthropic_pricing
 catalogs=model_catalogs()
 return {'anthropic_pricing':load_anthropic_pricing(),'models':ordered_models(m for values in catalogs.values() for m in values),'models_by_harness':catalogs,'provider_catalogs':{'default':catalogs,'foundry':model_catalogs('foundry')},'provider_connections':{'default':personal_ready(),'foundry':{h:bool(FOUNDRY_KEY and models) for h,models in model_catalogs('foundry').items()}},'personal':{'openai':{'connected':bool(AIDER_KEY)},'anthropic':{'connected':bool(CLAUDE_KEY),'models':CLAUDE_MODELS}},'foundry':{'connected':bool(FOUNDRY_KEY),'endpoint':FOUNDRY_ENDPOINT,'project_endpoint':FOUNDRY_PROJECT,'models':FOUNDRY_MODELS}}

def refresh_connections():
 global MODELS,READY,NATIVE_MODELS
 env=auth_env();work=PRIVATE;ready={};catalogs={h:set() for h in CORE_HARNESS}
 try:
  r=command(['codex','login','status'],env);ready['codex']=r.returncode==0
  d=json.loads((Path.home()/'.codex/models_cache.json').read_text(encoding='utf-8'))
  catalogs['codex']={m['slug'] for m in d.get('models',[]) if m.get('slug','').startswith('gpt-')}
 except Exception:ready['codex']=False
 oe=dict(env);oe.update(XDG_DATA_HOME=str(work/'auth/opencode-data'),XDG_STATE_HOME=str(work/'auth/opencode-state'),XDG_CONFIG_HOME=str(work/'auth/opencode-config'))
 try:
  ob=work/'opencode-tools/node_modules/opencode-windows-x64/bin/opencode.exe'
  r=command([str(ob),'auth','list'],oe);ready['opencode']=r.returncode==0 and 'openai' in r.stdout.lower()
  r=command([str(ob),'models','openai'],oe)
  catalogs['opencode']={x.strip().split('/',1)[1] for x in r.stdout.splitlines() if x.strip().startswith('openai/') and not x.strip().endswith(('-fast','-flex','-ultrafast'))}
 except Exception:ready['opencode']=False
 pe=dict(env);pe['PI_CODING_AGENT_DIR']=str(work/'auth/pi')
 try:
  pb=work/'pi-tools/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js'
  r=command(['node',str(pb),'auth','check','--provider','openai-codex','--no-refresh','--json'],pe)
  ready['pi']=json.loads(r.stdout).get('status')=='ready'
  r=command(['node',str(pb),'--offline','--list-models','openai-codex'],pe)
  catalogs['pi']={x.split()[1] for x in r.stdout.splitlines() if x.startswith('openai-codex')}
 except Exception:ready['pi']=False
 ready.update({h:bool(AIDER_KEY) for h in API_HARNESSES})
 with LOCK:
  NATIVE_MODELS=catalogs;MODELS=ordered_models(m for values in catalogs.values() for m in values);READY=ready
 return {**catalog_payload(),'connections':READY,'aider_models':sorted(AIDER_MODELS),'api_models':sorted(AIDER_MODELS)}

TOOLS_IMAGE='agent-arena-tools:20261026-nine'
STARTUP_LIMIT=120
COLLECTION_LIMIT=90

def docker_preflight():
 try:
  result=command([DOCKER,'info','--format','{{.OSType}}'],timeout=10)
  if result.returncode or result.stdout.strip()!='linux':raise ValueError()
 except Exception:raise HTTPException(503,'Docker Desktop is not ready. Start its Linux engine, wait until it is running, and try again.') from None
 try:
  result=command([DOCKER,'image','inspect','--format','{{.Id}}',TOOLS_IMAGE],timeout=10)
  image=result.stdout.strip()
  if result.returncode or not re.fullmatch(r'sha256:[a-f0-9]{64}',image):raise ValueError()
 except Exception:raise HTTPException(503,'The installed Arena tools image is missing. Run PREPARE-ARENA.ps1 once before starting a comparison.') from None
 pinned='agent-arena-base:'+image.split(':',1)[1]
 result=command([DOCKER,'tag',image,pinned],timeout=10)
 if result.returncode:raise HTTPException(503,'Could not pin the local tools image. Check Docker Desktop and retry.')
 return pinned

def prepare_workspace(run):
 environment=Path(run['task_path'])/'environment'
 digest=hashlib.sha256()
 for path in sorted(environment.rglob('*')):
  if path.is_file():digest.update(str(path.relative_to(environment)).encode());digest.update(path.read_bytes())
 image='agent-arena-workspace:'+digest.hexdigest()[:20]
 exists=command([DOCKER,'image','inspect',image],timeout=10)
 if exists.returncode:
  result=command([DOCKER,'build','--pull=false','-t',image,str(environment)],timeout=90)
  log=PRIVATE/'logs'/(run['id']+'-workspace.txt');log.parent.mkdir(parents=True,exist_ok=True);log.write_text(result.stdout+result.stderr,encoding='utf-8')
  if result.returncode:raise RuntimeError('Workspace preparation failed. Check Docker Desktop and the local workspace build log.')
 metadata=Path(run['task_path'])/'task.toml'
 text=metadata.read_text(encoding='utf-8')
 text=text.replace('[environment]','[environment]\ndocker_image = '+json.dumps(image)+'\nbuild_timeout_sec = '+str(STARTUP_LIMIT),1)
 metadata.write_text(text,encoding='utf-8')
 run['workspace_image']=image

def execution_clock(item):
 for trial in owned_trials(item):
  marker=trial/'agent/arena-execution.json'
  try:
   value=json.loads(marker.read_text(encoding='utf-8'))
   if isinstance(value.get('started_epoch'),(int,float)):return value
  except (OSError,ValueError):pass
 return {}

def owned_trials(item):
 d=Path(item.get('job_root',str(JOBS)))/item['job']
 return [p for p in d.iterdir() if p.is_dir() and (p/'config.json').exists()] if d.exists() else []
def containers(item,all_services=False):
 ids=[]
 for trial in owned_trials(item):
  sessions=[trial.name+'__env']
  if all_services:sessions.append(trial.name+'__verifier__trial')
  for session in sessions:
   project=re.sub(r'[^a-z0-9_-]','-',session.lower())
   args=[DOCKER,'ps','-aq','--filter','label=com.docker.compose.project='+project]
   if not all_services:args+=['--filter','label=com.docker.compose.service=main']
   r=command(args,timeout=10)
   ids += [x for x in r.stdout.splitlines() if re.fullmatch(r'[a-f0-9]{12,64}',x)]
 return list(dict.fromkeys(ids))

def snapshot(item):
 try:
  ids=containers(item)
  if not ids:return
  d=PRIVATE/'snapshots'/item['job'];d.mkdir(parents=True,exist_ok=True);p=d/'index.next.html'
  r=command([DOCKER,'cp',ids[0]+':/app/index.html',str(p)],timeout=8)
  if r.returncode==0 and p.is_file() and p.stat().st_size<=5_000_000:p.replace(d/'index.html')
 except Exception:pass
def read_events(p):
 if not p.exists():return []
 with p.open('rb') as f:
  n=f.seek(0,2);f.seek(max(0,n-2_000_000));raw=f.read()
 result=[]
 for line in raw.decode('utf-8',errors='replace').splitlines():
  try:
   e=json.loads(line)
   if isinstance(e,dict):result.append(e)
  except ValueError:pass
 return result
def progress(h,item):
 paths=owned_trials(item)
 if not paths:return {'activity':[],'final_output':'','live_tools':0}
 p=paths[0]/'agent'/({'codex':'codex.txt','opencode':'opencode.txt','pi':'pi.txt','aider':'aider.txt','goose':'goose.txt','cline':'cline.txt','mini-swe-agent':'mini-swe-agent.txt','openhands':'openhands_sdk.txt','qwen':'qwen-code.txt'}[h]);activity=[];output=[];tools=0
 if h=='openhands':
  events=read_events(paths[0]/'agent/arena-activity.jsonl')
  return {'activity':['Tool: '+str(e.get('name','tool')) for e in events if e.get('type')=='tool'][-14:],'final_output':'\n\n'.join(str(e['text']) for e in events if e.get('type')=='message' and e.get('text'))[-14000:],'live_tools':sum(e.get('type')=='tool' for e in events)}
 if h in ('goose','cline','mini-swe-agent'):
  trajectory=paths[0]/'agent/trajectory.json';activity=[];output=[]
  if trajectory.exists():
   try:
    trace=json.loads(trajectory.read_text(encoding='utf-8'))
    for step in trace.get('steps',[]):
     for call in step.get('tool_calls') or []:activity.append('Tool: '+str(call.get('function_name','tool')))
     if h!='mini-swe-agent' and step.get('source')=='agent' and not step.get('tool_calls') and step.get('message'):output.append(str(step['message']))
   except (ValueError,OSError):pass
  return {'activity':activity[-14:],'final_output':'\n'.join(output)[-14000:] or 'Native agent output is collected with the app and code.','live_tools':len(activity) if activity else None}
 if h=='aider':
  lines=aider_summary(p.read_text(encoding='utf-8',errors='replace')[-100000:]) if p.exists() else []
  return {'activity':lines,'final_output':'\n'.join(lines) or 'Aider visible edit summaries will appear here.','live_tools':None}
 for e in read_events(p):
  kind=e.get('type');entry=None
  if h=='codex' and kind=='item.completed':
   part=e.get('item',{});typ=part.get('type')
   if typ=='command_execution':tools+=1;entry='Command: '+str(part.get('command','')).splitlines()[0][:160]
   elif typ=='file_change':tools+=1;entry='Edited '+', '.join(str(x.get('path','file')) for x in part.get('changes',[]))
   elif typ=='agent_message':output.append(part.get('text',''))
  elif h=='opencode':
   part=e.get('part',{})
   if kind=='tool_use':
    tools+=1;entry='Tool: '+str(part.get('tool','tool'));title=(part.get('state') or {}).get('title')
    if title:entry+=' / '+str(title)[:140]
   elif kind=='text':output.append(part.get('text',''))
  elif h=='qwen':
   if kind=='assistant':
    msg=e.get('message') or {}
    for part in msg.get('content',[]):
     if part.get('type')=='tool_use':tools+=1;activity.append('Tool: '+str(part.get('name','tool')))
     elif part.get('type')=='text' and part.get('text'):output.append(part['text'])
   elif kind=='result' and isinstance(e.get('result'),str):output.append(e['result'])
  elif h=='pi':
   if kind=='tool_execution_start':tools+=1;entry='Tool: '+str(e.get('toolName','tool'))
   elif kind=='message_end':
    msg=e.get('message',{})
    if msg.get('role')=='assistant':output += [x.get('text','') for x in msg.get('content',[]) if x.get('type')=='text']
  if entry:activity.append(entry)
 return {'activity':activity[-14:],'final_output':'\n\n'.join(output)[-14000:],'live_tools':tools}
def result_info(item,provider=None):
 paths=owned_trials(item)
 if not paths:return None
 p=paths[0]/'result.json'
 if not p.exists():return None
 try:
  raw=json.loads(p.read_text(encoding='utf-8'));a=raw.get('agent_result') or {};exception=raw.get('exception_info') or {};trajectory=paths[0]/'agent/trajectory.json';count=None
  if trajectory.exists():
   t=json.loads(trajectory.read_text(encoding='utf-8'));count=sum(len(s.get('tool_calls') or []) for s in t.get('steps',[]))
  reason=None;failure_message=None
  aiderlog=paths[0]/'agent/aider.txt'
  if aiderlog.exists():reason,failure_message=aider_failure(aiderlog.read_text(encoding='utf-8',errors='replace')[-100000:])
  if provider in ('foundry','anthropic'):
   from provider_errors import classify
   for logfile in paths[0].glob('agent/*.txt'):
    detected,message=classify(logfile.read_text(encoding='utf-8',errors='replace')[-300000:],provider)
    if detected:
     reason,failure_message=detected,message;exception={'exception_type':'ProviderRequestError'};break
  p=paths[0]/'verifier/report.json';grade=json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
  metrics={'agent_seconds':seconds(raw.get('agent_execution')),'input_tokens':a.get('n_input_tokens'),'cache_tokens':a.get('n_cache_tokens'),'output_tokens':a.get('n_output_tokens'),'tool_calls':count,'score':{'passed':grade['passed'],'total':grade['total']} if grade else None,'exception_type':exception.get('exception_type'),'actual_cost_usd':None,'reported_api_cost_estimate_usd':a.get('cost_usd') if aiderlog.exists() or provider=='anthropic' else None,'reported_models':(a.get('metadata') or {}).get('reported_models',[]),'failure_reason':reason,'failure_message':failure_message}
  if item['harness'] in ('openhands','qwen'):
   from new_harness_usage import collect as collect_new
   metrics.update(collect_new(paths[0]/'agent',item['harness']))
  if provider=='anthropic':
   from claude_usage import collect
   metrics.update(collect(paths[0],item['harness']))
  return metrics
 except (ValueError,OSError):return None
def output_dir(item):
 for trial in owned_trials(item):
  d=trial/'artifacts/app'
  if d.is_dir():return d
 return None

def app_dir(item):
 for trial in owned_trials(item):
  d=trial/'artifacts/app'
  if (d/'index.html').is_file():return d
 d=PRIVATE/'snapshots'/item['job']
 return d if (d/'index.html').is_file() else None
def public_run(run):
 with LOCK:obj=json.loads(json.dumps(run))
 obj.pop('task_path',None)
 for cid,item in obj['contestants'].items():
  h=item['harness'];item.setdefault('id',cid)
  d=app_dir(item);item.update(progress(h,run['contestants'][cid]));info=result_info(item,'anthropic' if run.get('routes',{}).get(cid)=='anthropic' else run.get('provider'))
  if info:item['metrics']=info
  item['elapsed_seconds']=round(max(0,time.time()-item.get('started_epoch',time.time())),1) if item['status'] in ('starting','running','verifying') else item.get('elapsed_seconds',0)
  failure=(info or {}).get('exception_type') or (item.get('metrics') or {}).get('exception_type')
  if failure=='AgentTimeoutError' and item['status'] not in ('cancelled','interrupted'):
   item['status']='timed_out'
   item['error']=f"Reached the {run['timeout_minutes']}-minute agent limit. Codex signed in and ran; use Load challenge and choose a longer limit for a new attempt." if h=='codex' else f"Reached the {run['timeout_minutes']}-minute agent limit. Load the challenge and choose a longer limit for a new attempt."
  elif failure:
   if item['status']=='complete':item['status']='error'
   if (info or {}).get('failure_message') or not item.get('error'):item['error']=(info or {}).get('failure_message') or 'Agent run failed: '+failure+'. Check the model connection and local runner logs.'
  clock=execution_clock(item);item['phase']=item.get('phase',run.get('phase','queued') if item['status']=='queued' else 'starting')
  if clock:
   item['agent_elapsed_seconds']=round(max(0,clock.get('finished_epoch',time.time())-clock['started_epoch']),1)
   if item['status'] in ('starting','running'):item['phase']='collecting' if 'finished_epoch' in clock else 'working'
  item['model']=run.get('models',{}).get(cid,run['model'])
  route=run.get('routes',{}).get(cid)
  item['provider']='anthropic' if route=='anthropic' else 'openai' if route=='openai' else run.get('provider','default')
  if route=='anthropic':item['reasoning_note']='Thinking: '+run['reasoning']+' requested via native harness' if h in ('pi','cline','openhands','qwen') else 'Thinking: native harness default'
  item['billing_route']='Microsoft Foundry / Azure billing' if item['provider']=='foundry' else 'Anthropic API (separately billed)' if route=='anthropic' else 'OpenAI API (separately billed)' if route=='openai' or h in API_HARNESSES else 'ChatGPT subscription'
  starter=ROOT/'tasks'/PRESETS.get(run.get('preset'),'01-build')/'environment/starter/index.html'
  is_starter=bool(d) and starter.exists() and (d/'index.html').read_bytes()==starter.read_bytes()
  item['preview_is_starter']=bool(is_starter)
  item['has_preview']=bool(d) and not is_starter;item['preview_version']=str((d/'index.html').stat().st_mtime_ns) if d else None
  item['preview_url']=f'http://127.0.0.1:{preview_port(run,cid)}/open/{run["id"]}/{cid}' if item['has_preview'] else None
  item.pop('job_root',None)
 return obj
class ContestantInput(BaseModel):
 id:str=Field(pattern=r'^[a-z][a-z0-9-]{0,47}$')
 harness:str=Field(min_length=1,max_length=40)
 model:str|None=Field(default=None,min_length=1,max_length=128)

class RunInput(BaseModel):
 arena_id:str=Field(default='main',pattern=r'^(main|[a-f0-9]{12})$')
 model:str=Field(min_length=1,max_length=128)
 provider:str='default'
 prompt:str=Field(min_length=1,max_length=20000)
 harnesses:list[str]=Field(default_factory=list,max_length=14)
 contestants:list[ContestantInput]|None=Field(default=None,min_length=1,max_length=14)
 model_mode:str="shared"
 models:dict[str,str]=Field(default_factory=dict)
 preset:str='custom'
 mode:str='parallel'
 reasoning:str='medium'
 timeout_minutes:int=Field(default=15,ge=1,le=30)
def contestant_plan(data):
 if data.contestants is not None:
  if data.harnesses:raise HTTPException(400,'Use contestant entries or legacy harnesses, not both.')
  entries=[{'id':c.id,'harness':c.harness,'model':c.model or (data.models.get(c.id) if data.model_mode=='individual' else data.model)} for c in data.contestants]
 else:
  entries=[{'id':h,'harness':h,'model':data.models.get(h) if data.model_mode=='individual' else data.model} for h in data.harnesses]
 if not entries:raise HTTPException(400,'Select at least one contestant.')
 if len({e['id'] for e in entries})!=len(entries):raise HTTPException(400,'Each contestant needs a distinct instance ID.')
 if any(e['harness'] not in HARNESS or (e['id'] in HARNESS and e['id']!=e['harness']) for e in entries):raise HTTPException(400,'Choose valid harnesses and instance IDs.')
 return entries

def worker(rid,h):
 run=RUNS[rid];item=run['contestants'][h]
 if not AGENT_SLOTS.acquire(blocking=False):
  with LOCK:item['phase']='waiting_for_slot';persist()
  while not AGENT_SLOTS.acquire(timeout=.5):
   if run.get('cancelled'):
    with LOCK:item['status']='cancelled';persist()
    return
 try:return run_worker(rid,h)
 except Exception:
  with LOCK:item['status']='error';item['error']='The worker could not finish. Available results are preserved; retry this contestant.';persist()
 finally:AGENT_SLOTS.release()

def run_worker(rid,cid):
 run=RUNS[rid];item=run['contestants'][cid];h=item['harness']
 with LOCK:
  if run.get('cancelled'):item['status']='cancelled';persist();return
  item['status']='starting';item['phase']='starting';item['started_epoch']=time.time();persist()
 model=run.get('models',{}).get(cid,run['model'])
 c=config(h if h in CORE_HARNESS else 'codex',model,'01-build',item['job'])
 if h in API_HARNESSES:
  cls,provider,version=HARNESS[h];kw={'version':version,'reasoning_effort':run['reasoning']}
  if h=='aider':kw['stream']=False
  if h=='openhands':kw['load_skills']=False
  if h=='cline':kw.update(cline_version=version,cline_timeout_sec=run['timeout_minutes']*60)
  c['agents']=[{'import_path':'showdown_agents:'+cls,'model_name':provider+(':' if h=='cline' else '/')+model,'kwargs':kw,'exclude_logs':['**/auth.json','**/*credentials*']}]
 c['jobs_dir']=str(JOBS);c['tasks']=[{'path':run['task_path']}]
 c['agents'][0]['override_setup_timeout_sec']=STARTUP_LIMIT
 c['agents'][0]['override_timeout_sec']=run['timeout_minutes']*60;kw=c['agents'][0]['kwargs'];effort=run['reasoning']
 if h=='codex':kw['reasoning_effort']=effort
 elif h=='pi':kw['thinking']=effort
 elif h in API_HARNESSES:kw['reasoning_effort']=effort
 else:kw['variant']=effort;kw['opencode_config']['provider']['openai']['models'][model]['options']['reasoningEffort']=effort
 if run.get('provider')=='foundry':
  from foundry_runtime import configure
  c=configure(c,h,model,run['foundry_models'][model],run['endpoint'])
 route=run.get('routes',{}).get(cid)
 if route=='anthropic':
  from claude_runtime import configure as configure_claude
  c=configure_claude(c,h,model,run.get('claude_models',{}).get(model,{}),effort)
 elif route=='openai' and h in CORE_HARNESS:
  from foundry_runtime import configure as configure_api
  c=configure_api(c,h,model,{'responses':True,'reasoning':bool(re.match(r'^(gpt-(?:5|6)|o[134])',model))},'https://api.openai.com/v1')
 c['verifier']={'disable':not run['graded']};c['artifacts']=[{'source':'/app','exclude':['.git','node_modules','.venv','__pycache__','auth.json','.env*','*.pem','.aider*']}]
 try:
  from harbor.models.job.config import JobConfig
  JobConfig.model_validate(c);cfg=PRIVATE/'configs'/(item['job']+'.json');write_json(cfg,c)
  log=PRIVATE/'logs'/(item['job']+'.txt');log.parent.mkdir(parents=True,exist_ok=True)
  with log.open('w',encoding='utf-8') as output:
   flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
   agent_env=auth_env()
   if run.get('provider')=='foundry':
    from foundry_runtime import environment
    agent_env=environment(agent_env,FOUNDRY_KEY,run['endpoint'])
   elif route=='anthropic':
    from claude_runtime import environment as claude_environment
    agent_env=claude_environment(agent_env,CLAUDE_KEY)
   elif route=='openai':
    from foundry_runtime import environment as api_environment
    agent_env=api_environment(agent_env,AIDER_KEY,'https://api.openai.com/v1');agent_env.pop('ARENA_FOUNDRY',None)
   elif h in API_HARNESSES:agent_env['OPENAI_API_KEY']=AIDER_KEY
   if h=='openhands':
    agent_env['LLM_API_KEY']=agent_env.get('ANTHROPIC_API_KEY') if route=='anthropic' else agent_env.get('OPENAI_API_KEY','')
    agent_env['LLM_BASE_URL']=agent_env.get('ANTHROPIC_BASE_URL','https://api.anthropic.com') if route=='anthropic' else agent_env.get('OPENAI_BASE_URL','https://api.openai.com/v1')
    agent_env['OPENHANDS_SUPPRESS_BANNER']='1'
   proc=subprocess.Popen([str(HARBOR),'run','--config',str(cfg)],cwd=ROOT,env=agent_env,stdout=output,stderr=subprocess.STDOUT,creationflags=flags)
   with LOCK:PROCESSES[(rid,cid)]=proc;item['status']='running';persist()
   last=0;watchdog=None
   while proc.poll() is None:
    if run.get('cancelled'):stop_contestant(rid,cid);break
    clock=execution_clock(item);now=time.time()
    item['phase']='collecting' if clock.get('finished_epoch') else 'working' if clock else 'starting'
    if not clock and now-item['started_epoch']>STARTUP_LIMIT:watchdog='setup';break
    if clock and now-clock.get('finished_epoch',clock['started_epoch'])>(COLLECTION_LIMIT if clock.get('finished_epoch') else run['timeout_minutes']*60+30):watchdog='collection' if clock.get('finished_epoch') else 'agent';break
    if clock and now-last>10:snapshot(item);last=now
    time.sleep(1)
   if watchdog:
    stop_contestant(rid,cid)
    item['error']={'setup':'Container or agent setup exceeded 2 minutes; the model never started. Check Docker Desktop and retry.','agent':'The agent exceeded its time limit and was stopped.','collection':'The agent finished, but output collection exceeded 90 seconds. Available previews are preserved.'}[watchdog]
   proc.wait(timeout=30)
  info=result_info(item,'anthropic' if run.get('routes',{}).get(cid)=='anthropic' else run.get('provider'))
  with LOCK:
   item['status']='cancelled' if run.get('cancelled') else ('error' if watchdog in ('setup','collection') else 'timed_out' if watchdog else ('timed_out' if info and info.get('exception_type')=='AgentTimeoutError' else ('error' if proc.returncode or (info and info.get('exception_type')) else 'complete')))
   if item['status']=='error' and not item.get('error') and not (info or {}).get('exception_type'):item['error']='The local runner exited before producing a result. Check Docker Desktop and retry; no generated output was collected.'
   item['elapsed_seconds']=round(time.time()-item['started_epoch'],1)
   if info:item['metrics']=info
   persist()
 except Exception as exc:
  with LOCK:item['status']='error';item['error']=type(exc).__name__+': '+str(exc)[:160];persist()
 finally:
  with LOCK:PROCESSES.pop((rid,cid),None)
def stop_contestant(rid,h):
 item=RUNS[rid]['contestants'][h]
 try:
  ids=containers(item)
  if ids:command([DOCKER,'stop','--time','2',*ids],timeout=20)
 except Exception:pass
 proc=PROCESSES.get((rid,h))
 if proc and proc.poll() is None:
  try:
   if os.name=='nt':command(['taskkill','/PID',str(proc.pid),'/T','/F'],timeout=15)
   else:proc.terminate()
  except OSError:pass
 try:
  ids=containers(item,all_services=True)
  if ids:command([DOCKER,'rm','-f',*ids],timeout=20)
 except Exception:pass
def execute(rid):
 run=RUNS[rid]
 with LOCK:run['status']='running';run['phase']='preparing_workspace';persist()
 try:
  with WORKSPACE_LOCK:prepare_workspace(run)
 except Exception:
  with LOCK:
   run['status']='cancelled' if run.get('cancelled') else 'finished_with_errors';run['finished_at']=datetime.now(timezone.utc).isoformat()
   for item in run['contestants'].values():item.update(status='cancelled' if run.get('cancelled') else 'error',phase='preparing_workspace',error='Workspace preparation failed or exceeded 90 seconds. No models were started. Check Docker Desktop and retry.')
   persist()
  return
 with LOCK:run['phase']='starting';persist()
 if run['mode']=='parallel':
  with ThreadPoolExecutor(max_workers=len(run['harnesses'])) as pool:list(pool.map(lambda h:worker(rid,h),run['harnesses']))
 else:
  for h in run['harnesses']:worker(rid,h)
 with LOCK:
  run['status']='cancelled' if run.get('cancelled') else ('complete' if all(x['status']=='complete' for x in run['contestants'].values()) else 'finished_with_errors')
  run['finished_at']=datetime.now(timezone.utc).isoformat();persist()
app=FastAPI(title='Agent Arena',docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=HERE/'dist'),name='static')
@app.middleware('http')
async def local_only(request:Request,call_next):
 if request.headers.get('host','').split(':')[0] not in ('127.0.0.1','localhost'):return JSONResponse({'detail':'Local access only'},status_code=403)
 if request.method not in ('GET','HEAD'):
  origin=request.headers.get('origin')
  if origin and origin not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):return JSONResponse({'detail':'Origin rejected'},status_code=403)
  if not secrets.compare_digest(request.headers.get('x-arena-token',''),TOKEN):return JSONResponse({'detail':'Refresh the page before running'},status_code=403)
 response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff'
 if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
 return response
@app.get('/')
def index():return FileResponse(HERE/'dist/index.html',headers={'Cache-Control':'no-store'})
@app.get('/api/state')
def state(arena_id:str='main'):
 arena=ARENAS.get(arena_id)
 if not arena:raise HTTPException(404,'Arena not found. Open a new arena tab.')
 with LOCK:
  history=[{'id':r['id'],'created_at':r['created_at'],'model':'Mixed models' if r.get('model_mode')=='individual' else r['model'],'prompt':r['prompt'][:80],'status':r['status']} for r in reversed(list(RUNS.values())) if r.get('arena_id','main')==arena_id]
  active=next((r['id'] for r in RUNS.values() if r.get('arena_id','main')==arena_id and r['status'] in ('queued','running','stopping')),None)
  arenas=ARENAS.listing(RUNS)
 return {'arena':arena,'arenas':arenas,'max_active_agents':MAX_ACTIVE_AGENTS,'max_contestants':14,'other_active_arenas':sum(bool(a['active_id']) for a in arenas if a['id']!=arena_id),'token':TOKEN,**catalog_payload(),'connections':READY,'history':history,'active_id':active,'versions':{h:v[2] for h,v in HARNESS.items()},'presets':{k:(ROOT/'tasks'/v/'instruction.md').read_text(encoding='utf-8') for k,v in PRESETS.items()},'runner_instructions':CONTRACT,'aider_models':sorted(AIDER_MODELS),'api_models':sorted(AIDER_MODELS),'harnesses':CATALOG,'api_harnesses':sorted(API_HARNESSES)}
class ArenaInput(BaseModel):
 name:str=Field(default='',max_length=60)
@app.post('/api/arenas')
def create_arena(data:ArenaInput):return ARENAS.create(data.name)
@app.post('/api/arenas/{arena_id}/rename')
def rename_arena(arena_id:str,data:ArenaInput):
 if not data.name.strip():raise HTTPException(400,'Give this arena a name.')
 result=ARENAS.rename(arena_id,data.name)
 if result is None:raise HTTPException(404)
 return result

@app.post('/api/refresh')
def refresh():return refresh_connections()
@app.post('/api/runs')
def start(data:RunInput):
 with LOCK:
  if not ARENAS.get(data.arena_id):raise HTTPException(404,'Arena not found.')
  if any(r.get('arena_id','main')==data.arena_id and r['status'] in ('queued','running','stopping') for r in RUNS.values()):raise HTTPException(409,'This arena already has a running comparison. Open New arena for another prompt.')
  if data.provider not in ('default','foundry'):raise HTTPException(400,'Choose an available model source.')
  if data.model_mode not in ('shared','individual'):raise HTTPException(400,'Invalid model mode.')
  entries=contestant_plan(data);selected_models={e['id']:e['model'] for e in entries}
  catalogs=model_catalogs(data.provider)
  if any(e['model'] not in catalogs.get(e['harness'],[]) for e in entries):raise HTTPException(400,'Choose a model listed for each selected contestant. Refresh models if access has changed.')
  if any(not (bool(FOUNDRY_KEY) if data.provider=='foundry' else personal_ready().get(e['harness'])) for e in entries):raise HTTPException(400,'Connect the missing sign-in or API key before running.')
  if data.provider=='default' and any(personal_route(e['harness'],e['model'])=='openai' and (not AIDER_KEY or e['model'] not in AIDER_MODELS) for e in entries):raise HTTPException(400,'This API key does not list one of the selected models. Choose a model permitted for each contestant.')
  if data.mode not in ('parallel','sequential') or data.reasoning not in ('low','medium','high'):raise HTTPException(400,'Invalid comparison settings.')
  if not data.prompt.strip():raise HTTPException(400,'Write a prompt first.')
  if data.provider=='foundry':
   from foundry_api import probe_deployment
   for deployment in set(selected_models.values()):
    info=FOUNDRY_MODELS[deployment]
    if time.time()-info.get('verified_at',0)>300:
     try:FOUNDRY_MODELS[deployment]=probe_deployment(FOUNDRY_ENDPOINT,FOUNDRY_KEY,info)
     except ValueError as error:raise HTTPException(400,str(error)) from None
  tools_image=docker_preflight()
  rid=uuid.uuid4().hex[:12];task=PRIVATE/'tasks'/('demo-'+rid);base=ROOT/'tasks'/PRESETS.get(data.preset,'01-build');shutil.copytree(base,task)
  meta=task/'task.toml';meta.write_text(re.sub(r'^artifacts\s*=.*$','',meta.read_text(encoding='utf-8'),flags=re.M),encoding='utf-8')
  dockerfile=task/'environment/Dockerfile';old_docker=dockerfile.read_text(encoding='utf-8');workspace_layer=old_docker[old_docker.index('WORKDIR /app'):]
  dockerfile.write_text('FROM '+tools_image+'\n'+workspace_layer,encoding='utf-8')
  original=(base/'instruction.md').read_text(encoding='utf-8');graded=data.preset in PRESETS and data.prompt.strip()==original.strip();prompt=data.prompt.strip()
  (task/'instruction.md').write_text(prompt if graded else prompt+'\n\n'+CONTRACT,encoding='utf-8')
  totals={h:sum(e['harness']==h for e in entries) for h in HARNESS};ordinals={}
  contestants={}
  for e in entries:
   cid=e['id'];h=e['harness'];ordinals[h]=ordinals.get(h,0)+1
   label=CATALOG[h]['name']+((' '+str(ordinals[h])) if totals[h]>1 else '')
   contestants[cid]={'id':cid,'harness':h,'label':label,'model':e['model'],'version':HARNESS[h][2],'status':'queued','job':'a'+rid+'-'+cid,'metrics':None}
  run={'id':rid,'arena_id':data.arena_id,'created_at':datetime.now(timezone.utc).isoformat(),'status':'queued','provider':data.provider,'model':entries[0]['model'],'model_mode':'individual' if len(set(selected_models.values()))>1 else data.model_mode,'models':selected_models,'prompt':prompt,'harnesses':[e['id'] for e in entries],'mode':data.mode,'reasoning':data.reasoning,'timeout_minutes':data.timeout_minutes,'preset':data.preset,'graded':graded,'task_path':str(task),'contestants':contestants}
  if data.provider=='foundry':run.update(endpoint=FOUNDRY_ENDPOINT,project_endpoint=FOUNDRY_PROJECT,foundry_models={m:FOUNDRY_MODELS[m] for m in set(selected_models.values())})
  if data.provider=='default':run['routes']={e['id']:personal_route(e['harness'],e['model']) for e in entries};run['claude_models']={m:CLAUDE_MODELS[m] for m in set(selected_models.values()) if m in CLAUDE_MODELS}
  if any(route=='anthropic' for route in run.get('routes',{}).values()):
   from anthropic_pricing import load as load_anthropic_pricing
   run['anthropic_pricing']=load_anthropic_pricing()
  RUNS[rid]=run;persist()
 threading.Thread(target=execute,args=(rid,),daemon=True).start();return {'id':rid}
@app.get('/api/runs/{rid}')
def get_run(rid:str,arena_id:str='main'):
 if rid not in RUNS or RUNS[rid].get('arena_id','main')!=arena_id:raise HTTPException(404)
 return public_run(RUNS[rid])
@app.post('/api/runs/{rid}/stop')
def stop(rid:str,arena_id:str='main'):
 run=RUNS.get(rid)
 if not run or run.get('arena_id','main')!=arena_id:raise HTTPException(404)
 with LOCK:
  if run['status'] not in ('queued','running','stopping'):return {'status':run['status']}
  run['cancelled']=True;run['status']='stopping'
  for item in run['contestants'].values():
   if item['status']=='queued':item['status']='cancelled'
  if all(item['status'] not in ('queued','starting','running','verifying') for item in run['contestants'].values()):run['status']='cancelled'
  persist()
 for h in run['harnesses']:threading.Thread(target=stop_contestant,args=(rid,h),daemon=True).start()
 return {'status':'stopping'}
@app.get('/api/runs/{rid}/{h}/source')
def source(rid:str,h:str,arena_id:str='main'):
 if RUNS.get(rid,{}).get('arena_id','main')!=arena_id:raise HTTPException(404)
 item=RUNS.get(rid,{}).get('contestants',{}).get(h)
 if not item:raise HTTPException(404)
 d=app_dir(item);return PlainTextResponse((d/'index.html').read_text(encoding='utf-8') if d else 'No index.html has been written yet.')
@app.get('/api/runs/{rid}/export')
def export(rid:str,arena_id:str='main'):
 run=RUNS.get(rid)
 if not run or run.get('arena_id','main')!=arena_id:raise HTTPException(404)
 buffer=io.BytesIO()
 with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('results.json',json.dumps(public_run(run),indent=2));z.writestr('prompt.txt',run['prompt'])
  z.writestr('READ-ME.txt','Actual subscription cost was not measured. Custom prompts have no correctness score. Parallel mode is a live race, not an isolated speed benchmark. Credentials and native logs are excluded.\n')
  for h,item in run['contestants'].items():
   d=output_dir(item) or app_dir(item)
   if d:
    total=0
    for p in d.rglob('*'):
     if p.is_file() and not p.is_symlink() and p.stat().st_size<=5_000_000:
      total+=p.stat().st_size
      if total>20_000_000:break
      if p.name=='auth.json' or p.name.startswith('.env') or p.suffix.lower()=='.pem' or any(x in ('.git','node_modules','.venv','__pycache__') for x in p.relative_to(d).parts):continue
      z.write(p,'apps/'+h+'/'+str(p.relative_to(d)).replace('\\','/'))
 return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="arena-{rid}.zip"'})

class AiderConnection(BaseModel):
 api_key:SecretStr

def aider_active():
 return any(r['status'] in ('queued','running','stopping') and r.get('provider','default')=='default' and ('openai' in r.get('routes',{}).values() or (not r.get('routes') and any(i.get('harness') in API_HARNESSES for i in r['contestants'].values()))) for r in RUNS.values())

@app.post('/api/connections/openai')
@app.post('/api/connections/aider')
def connect_aider(data:AiderConnection):
 global AIDER_KEY,AIDER_MODELS
 from aider_api import list_models
 with LOCK:
  if aider_active():raise HTTPException(409,'Wait for the active API-backed run to finish before changing its key.')
 key=data.api_key.get_secret_value().strip()
 try:models=list_models(key)
 except ValueError as error:raise HTTPException(400,str(error)) from None
 with LOCK:
  if aider_active():raise HTTPException(409,'Wait for the active API-backed run to finish before changing its key.')
  AIDER_KEY=key;AIDER_MODELS=models;READY.update({h:True for h in API_HARNESSES})
 return {'connected':True,'aider_models':sorted(AIDER_MODELS),'message':'OpenAI API connected for compatible harnesses under Personal connections. The key is held in server memory only.'}

@app.post('/api/connections/openai/disconnect')
@app.post('/api/connections/aider/disconnect')
def disconnect_aider():
 global AIDER_KEY,AIDER_MODELS
 with LOCK:
  if aider_active():raise HTTPException(409,'Wait for the active API-backed run to finish before disconnecting.')
  AIDER_KEY='';AIDER_MODELS=set();READY.update({h:False for h in API_HARNESSES})
 return {'connected':False}

class ClaudeConnection(BaseModel):
 api_key:SecretStr

def claude_active():
 return any(r['status'] in ('queued','running','stopping') and 'anthropic' in r.get('routes',{}).values() for r in RUNS.values())

@app.post('/api/pricing/anthropic/refresh')
def refresh_claude_pricing():
 from anthropic_pricing import refresh
 try:return refresh()
 except ValueError as error:raise HTTPException(503,str(error)) from None

@app.post('/api/connections/anthropic')
def connect_claude(data:ClaudeConnection):
 global CLAUDE_KEY,CLAUDE_MODELS
 from claude_api import list_models
 with LOCK:
  if claude_active():raise HTTPException(409,'Wait for the active Claude comparison before changing its key.')
 key=data.api_key.get_secret_value().strip()
 try:models=list_models(key)
 except ValueError as error:raise HTTPException(400,str(error)) from None
 with LOCK:
  if claude_active():raise HTTPException(409,'Wait for the active Claude comparison before changing its key.')
  CLAUDE_KEY=key;CLAUDE_MODELS=models
 return {'connected':True,'message':'Claude API connected under Personal connections. Claude models are available to eight compatible harnesses; Codex CLI uses OpenAI models. The key is held in server memory only.',**catalog_payload()}

@app.post('/api/connections/anthropic/disconnect')
def disconnect_claude():
 global CLAUDE_KEY,CLAUDE_MODELS
 with LOCK:
  if claude_active():raise HTTPException(409,'Wait for the active Claude comparison before disconnecting.')
  CLAUDE_KEY='';CLAUDE_MODELS={}
 return {'connected':False}

class FoundryConnection(BaseModel):
 api_key:SecretStr
 endpoint:str=DEFAULT_ENDPOINT
 project_endpoint:str=DEFAULT_PROJECT
 deployments:list[str]=Field(default_factory=list,max_length=100)

def foundry_active():
 return any(r['status'] in ('queued','running','stopping') and r.get('provider')=='foundry' for r in RUNS.values())

@app.post('/api/connections/foundry')
def connect_foundry(data:FoundryConnection):
 global FOUNDRY_KEY,FOUNDRY_ENDPOINT,FOUNDRY_PROJECT,FOUNDRY_MODELS
 from foundry_api import normalize_endpoint,discover,probe_deployment
 with LOCK:
  if foundry_active():raise HTTPException(409,'Wait for the active Foundry comparison before changing its connection.')
 try:
  endpoint=normalize_endpoint(data.endpoint);project=normalize_endpoint(data.project_endpoint,project=True) if data.project_endpoint.strip() else ''
  key=data.api_key.get_secret_value().strip();models,warning=discover(endpoint,key,data.deployments)
  first=next(iter(models));models[first]=probe_deployment(endpoint,key,models[first])
 except ValueError as error:raise HTTPException(400,str(error)) from None
 with LOCK:
  if foundry_active():raise HTTPException(409,'Wait for the active Foundry comparison before changing its connection.')
  FOUNDRY_KEY=key;FOUNDRY_ENDPOINT=endpoint;FOUNDRY_PROJECT=project;FOUNDRY_MODELS=models
 return {'connected':True,'message':warning or 'Foundry connected using your deployment list. The first deployment passed an inference check; other selected deployments are checked before a race starts.',**catalog_payload()}

@app.post('/api/connections/foundry/disconnect')
def disconnect_foundry():
 global FOUNDRY_KEY,FOUNDRY_MODELS
 with LOCK:
  if foundry_active():raise HTTPException(409,'Wait for the active Foundry comparison before disconnecting.')
  FOUNDRY_KEY='';FOUNDRY_MODELS={}
 return {'connected':False}

def preview_app(h,allowed_run=None):
 preview=FastAPI(docs_url=None,redoc_url=None)
 @preview.get('/open/{rid}/{name}')
 def open_app(rid:str,name:str,reset:int=0):
  if (allowed_run is not None and rid!=allowed_run) or name!=h or rid not in RUNS or h not in RUNS[rid]['contestants']:raise HTTPException(404)
  dest=f'/app/{rid}/{h}/index.html'
  script=f"const k='__arena_run';if(localStorage.getItem(k)!=={json.dumps(rid)}||{bool(reset).__str__().lower()}){{localStorage.clear();sessionStorage.clear();localStorage.setItem(k,{json.dumps(rid)});}}location.replace({json.dumps(dest)});"
  return HTMLResponse('<!doctype html><meta charset="utf-8"><script>'+script+'</script>')
 @preview.get('/app/{rid}/{name}/{file_path:path}')
 def file(rid:str,name:str,file_path:str):
  item=RUNS.get(rid,{}).get('contestants',{}).get(name)
  if (allowed_run is not None and rid!=allowed_run) or name!=h or not item:raise HTTPException(404)
  d=app_dir(item)
  if not d:raise HTTPException(404)
  p=(d/file_path).resolve()
  if not p.is_relative_to(d.resolve()) or not p.is_file() or p.is_symlink():raise HTTPException(404)
  return FileResponse(p,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
 return preview
from preview_origins import PreviewOrigins
PREVIEWS=PreviewOrigins(preview_app)
def preview_port(run,h):
 # Keep old saved previews usable; new arenas receive a separate storage origin.
 return PREVIEW_PORTS[h] if 'arena_id' not in run and h in PREVIEW_PORTS else PREVIEWS.port(run['id'],h)

@app.on_event('shutdown')
def shutdown():
 PREVIEWS.close()
 for rid,run in list(RUNS.items()):
  if run['status'] in ('queued','running','stopping'):
   run['cancelled']=True
   for h in run['harnesses']:stop_contestant(rid,h)
 persist()

if __name__=='__main__':
 refresh_connections()
 for h,port in PREVIEW_PORTS.items():threading.Thread(target=lambda name=h,p=port:uvicorn.run(preview_app(name),host='127.0.0.1',port=p,log_level='warning'),daemon=True).start()
 print(f'Agent Arena: http://127.0.0.1:{PORT}',flush=True)
 uvicorn.run(app,host='127.0.0.1',port=PORT,log_level='warning')

