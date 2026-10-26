"""Token counters only, normalized to total input including cache reads/writes."""
import json

def read(path):
 if not path.exists() or path.stat().st_size>30000000:return None
 try:return json.loads(path.read_text(encoding='utf-8'))
 except (ValueError,OSError):return None

def lines(path):
 if not path.exists() or path.stat().st_size>30000000:return []
 rows=[]
 for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
  try:row=json.loads(line)
  except ValueError:continue
  if isinstance(row,dict):rows.append(row)
 return rows

def call(total,output,cached=0,write=0,aggregate=False):
 counters=(total,output,cached,write)
 if any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in counters) or cached+write>total:return None
 return {'input_tokens':total,'output_tokens':output,'cache_tokens':cached,'cache_write_tokens':write,'aggregate':aggregate}

def collect(trial,h):
 folder=trial/'agent';calls=[]
 if h in ('openhands','qwen'):
  from new_harness_usage import collect as collect_new
  return collect_new(folder,h)
 if h=='aider':
  for row in lines(folder/'aider-usage.jsonl'):
   calls.append(call(row.get('input_tokens'),row.get('output_tokens'),row.get('cache_tokens') or 0,row.get('cache_write_tokens') or 0))
 elif h in ('pi','opencode'):
  data=read(folder/'trajectory.json') or {}
  for step in data.get('steps',[]):
   m=step.get('metrics') or {}
   if m.get('prompt_tokens') is None:continue
   write=(m.get('extra') or {}).get('cache_write_tokens') or 0
   total=m['prompt_tokens']+(write if h=='opencode' else 0)
   calls.append(call(total,m.get('completion_tokens'),m.get('cached_tokens') or 0,write))
 elif h=='cline':
  for path in (folder/'sessions').glob('*/*.messages.json'):
   data=read(path) or {}
   for msg in data.get('messages',[]):
    m=msg.get('metrics') or {}
    if msg.get('role')=='assistant' and 'inputTokens' in m:calls.append(call(m['inputTokens'],m.get('outputTokens'),m.get('cacheReadTokens') or 0,m.get('cacheWriteTokens') or 0))
 elif h=='goose':
  complete=[row for row in lines(folder/'goose.txt') if row.get('type')=='complete']
  if complete:
   row=complete[-1];calls.append(call(row.get('input_tokens'),row.get('output_tokens'),row.get('cache_read_input_tokens') or 0,row.get('cache_write_input_tokens') or 0,True))
 elif h=='mini-swe-agent':
  data=read(folder/'mini-swe-agent.trajectory.json') or {}
  for msg in data.get('messages',[]):
   usage=(((msg.get('extra') or {}).get('response') or {}).get('usage') or {})
   if not usage:continue
   detail=usage.get('prompt_tokens_details') or {};write=detail.get('cache_creation_tokens') or detail.get('cache_write_tokens') or usage.get('cache_creation_input_tokens') or 0
   calls.append(call(usage.get('prompt_tokens'),usage.get('completion_tokens'),detail.get('cached_tokens') or 0,write))
 valid=[c for c in calls if c is not None]
 if not valid or len(valid)!=len(calls):return {}
 return {'input_tokens':sum(c['input_tokens'] for c in valid),'output_tokens':sum(c['output_tokens'] for c in valid),'cache_tokens':sum(c['cache_tokens'] for c in valid),'cache_write_tokens':sum(c['cache_write_tokens'] for c in valid),'token_usage_calls':valid,'token_usage_source':'native Anthropic harness counters; input includes cache reads and writes'}
