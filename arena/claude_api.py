"""Anthropic model discovery; credentials remain in the server process only."""
import json,re,urllib.request,urllib.error
from urllib.parse import urlencode
VERSION='2023-06-01'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def list_models(key):
 if not 20<=len(key)<=500 or any(c.isspace() for c in key):raise ValueError('Enter a valid Anthropic API key.')
 models={};after=None
 for page in range(20):
  query={'limit':100}
  if after:query['after_id']=after
  request=urllib.request.Request('https://api.anthropic.com/v1/models?'+urlencode(query),headers={'x-api-key':key,'anthropic-version':VERSION,'Accept':'application/json'})
  try:
   with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:data=json.loads(response.read(2000000))
   if not isinstance(data.get('data'),list):raise ValueError()
  except urllib.error.HTTPError as error:
   raise ValueError({401:'Anthropic rejected the API key.',403:'Anthropic denied model listing. Check API key permissions.',429:'Anthropic rate-limited the connection check. Try again shortly.'}.get(error.code,'Anthropic could not validate this key.')) from None
  except Exception:raise ValueError('Could not reach Anthropic to list models. Check the connection and try again.') from None
  for row in data['data']:
   name=row.get('id') if isinstance(row,dict) else None
   if not isinstance(name,str) or not re.fullmatch(r'claude-[A-Za-z0-9_.-]+',name) or row.get('lifecycle')=='retired':continue
   models[name]={k:row[k] for k in ('id','display_name','max_input_tokens','max_tokens','capabilities') if k in row}
  if not data.get('has_more'):break
  cursor=data.get('last_id')
  if not isinstance(cursor,str) or cursor==after:raise ValueError('Anthropic returned an invalid model-list page. Try reconnecting.')
  after=cursor
 else:raise ValueError('Anthropic model listing exceeded its page limit. Try reconnecting.')
 if not models:raise ValueError('This key did not return any available Claude models.')
 return models
