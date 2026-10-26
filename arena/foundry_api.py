"""Foundry resource-key discovery. Credentials live only in server memory."""
import json,re,urllib.request,urllib.error,time
from urllib.parse import urlsplit
DEFAULT_ENDPOINT=''
DEFAULT_PROJECT=''
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def normalize_endpoint(value,project=False):
 value=value.strip().rstrip('/');url=urlsplit(value)
 suffix=r'[a-z0-9-]+\.(?:openai\.azure\.com|services\.ai\.azure\.com)'
 if url.scheme!='https' or not re.fullmatch(suffix,url.hostname or '') or url.port not in (None,443) or url.username or url.password or url.query or url.fragment:raise ValueError('Use an HTTPS Foundry resource endpoint without credentials, query parameters or fragments.')
 if project:
  if not re.fullmatch(r'/api/projects/[A-Za-z0-9_.-]+',url.path):raise ValueError('Project endpoint must end with /api/projects/your-project.')
 elif url.path.rstrip('/')!='/openai/v1':raise ValueError('Inference endpoint must end with /openai/v1.')
 return value

def deployment_info(name,raw=None):
 if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name):return None
 raw=raw or {};base=raw.get('model') or name
 if isinstance(base,dict):base=base.get('name') or name
 base=str(base);caps=raw.get('capabilities') or {}
 if not isinstance(caps,dict):caps={}
 if re.search(r'embed|whisper|tts|audio|image|realtime|moderation|transcrib|sora',base,re.I) or caps.get('chat_completion') is False:return None
 responses=bool(caps.get('responses') or re.match(r'^(gpt-(?:4o|4\.1|5|6)|o[134](?:-|$))',base,re.I))
 reasoning=bool(re.match(r'^(gpt-(?:5|6)|o[134](?:-|$))',base,re.I))
 return {'id':name,'model':base,'responses':responses,'reasoning':reasoning}

def discover(endpoint,key,manual=()):
 endpoint=normalize_endpoint(endpoint)
 if not manual:raise ValueError('Enter the actual deployment names from Foundry Models + endpoints. The /models catalog is not a deployment list.')
 if not 20<=len(key)<=500 or any(c.isspace() for c in key):raise ValueError('Enter a valid Foundry resource API key.')
 request=urllib.request.Request(endpoint+'/models',headers={'api-key':key,'Accept':'application/json'})
 warning='';records=[]
 try:
  with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:data=json.loads(response.read(2_000_000))
  records=data.get('data',data.get('value',[]))
  if not isinstance(records,list):raise ValueError()
 except urllib.error.HTTPError as error:
  if error.code in (403,404,405) and manual:warning='Model listing is unavailable; using your supplied deployment names. Inference access still needs a test.'
  else:raise ValueError({401:'Foundry rejected the key. Use the resource API key for this endpoint.',403:'Foundry denied model listing. Check key permissions, or supply deployment names.',404:'This endpoint cannot list models. Check the endpoint or supply deployment names.',429:'Foundry rate-limited discovery. Try again shortly.'}.get(error.code,'Foundry model discovery failed. Check the endpoint and key.')) from None
 except Exception:raise ValueError('Could not read the Foundry model list. Check the endpoint and network access.') from None
 catalog={row.get('id') or row.get('name'):row for row in records if isinstance(row,dict)}
 models={}
 for value in manual:
  pieces=value.split('|',1);name=pieces[0].strip();base=pieces[1].strip() if len(pieces)>1 else None
  info=deployment_info(name,{'model':base} if base else catalog.get(name))
  if not info:raise ValueError('Use text-model deployment names, optionally followed by | underlying-model, one per line.')
  models[info['id']]=info
 return models,warning

def probe_deployment(endpoint,key,info):
 """A bounded, tiny inference check; never return an upstream error body."""
 endpoint=normalize_endpoint(endpoint);api='responses' if info['responses'] else 'chat/completions'
 if api=='responses':body={'model':info['id'],'input':'Reply OK.','max_output_tokens':16,'store':False}
 else:body={'model':info['id'],'messages':[{'role':'user','content':'Reply OK.'}],('max_completion_tokens' if info['reasoning'] else 'max_tokens'):16}
 request=urllib.request.Request(endpoint+'/'+api,data=json.dumps(body).encode(),headers={'api-key':key,'Content-Type':'application/json','Accept':'application/json'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:result=json.loads(response.read(1000000))
  if not isinstance(result,dict) or result.get('error') or not (result.get('id') or result.get('choices')):raise ValueError()
 except urllib.error.HTTPError as error:
  try:detail=json.loads(error.read(64000));code=str((detail.get('error') or {}).get('code',''))
  except Exception:code=''
  if code.lower() in ('deploymentnotfound','modelnotfound','model_not_found') or error.code==404:message='Azure has no accessible deployment named '+info['id']+' at this endpoint. Enter the deployment name from Foundry Models + endpoints.'
  elif error.code==401:message='Azure rejected the resource API key for this endpoint.'
  elif error.code==403:message='Azure denied inference for '+info['id']+'. Check permissions and network rules.'
  elif error.code==429:message='Azure rate-limited the deployment check. Wait or check deployment quota.'
  else:message='Azure rejected the '+api+' check for '+info['id']+'. Check its underlying model and API compatibility.'
  raise ValueError(message) from None
 except Exception:raise ValueError('Could not verify inference for '+info['id']+'. Check endpoint access and try again.') from None
 return {**info,'verified_at':time.time(),'verified_api':api}
