"""Usage-only instrumentation around the native Aider CLI. No response text or secrets are saved."""
import json,sys
from pathlib import Path
import litellm
_original=litellm.completion

def completion(*args,**kwargs):
 result=_original(*args,**kwargs)
 data=result.model_dump() if hasattr(result,'model_dump') else result
 if isinstance(data,dict):
  usage=data.get('usage') or {}
  if usage:
   detail=usage.get('prompt_tokens_details') or {}
   record={'requested_model':kwargs.get('model'),'reported_model':data.get('model'),'input_tokens':usage.get('prompt_tokens'),'cache_tokens':detail.get('cached_tokens'),'output_tokens':usage.get('completion_tokens'),'cache_write_tokens':detail.get('cache_creation_tokens') or detail.get('cache_write_tokens') or usage.get('cache_creation_input_tokens') or 0}
   try:record['estimated_cost_usd']=litellm.completion_cost(completion_response=result)
   except Exception:record['estimated_cost_usd']=None
   destination=Path('/logs/agent/aider-usage.jsonl');destination.parent.mkdir(parents=True,exist_ok=True)
   with destination.open('a',encoding='utf-8') as stream:stream.write(json.dumps(record)+'\n')
 return result
litellm.completion=completion
from aider.main import main
sys.exit(main())
