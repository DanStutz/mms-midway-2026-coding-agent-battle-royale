"""Normalize counter-only observations from the two native harnesses."""
import json

def collect(folder,h):
 calls=[]
 try:
  if h=='openhands':
   path=folder/'arena-usage.json'
   if path.exists():calls=json.loads(path.read_text(encoding='utf-8')).get('calls',[])
  elif h=='qwen':
   path=folder/'arena-qwen-usage.jsonl';seen=set()
   if path.exists():
    for line in path.read_text(encoding='utf-8').splitlines():
     try:row=json.loads(line)
     except ValueError:continue
     identity=row.get('request_id')
     if identity in seen:continue
     seen.add(identity);calls.append({k:row.get(k) for k in ('input_tokens','output_tokens','cache_tokens','cache_write_tokens','aggregate')})
 except (OSError,ValueError):return {}
 fields=('input_tokens','output_tokens','cache_tokens','cache_write_tokens')
 if not calls or any(any(not isinstance(c.get(f),int) or isinstance(c.get(f),bool) or c[f]<0 for f in fields) or c['cache_tokens']+c['cache_write_tokens']>c['input_tokens'] for c in calls):return {}
 return {**{f:sum(c[f] for c in calls) for f in fields},'token_usage_calls':calls,'token_usage_source':'native provider response counters; input includes cache reads and writes'}
