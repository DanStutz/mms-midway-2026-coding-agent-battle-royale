"""Validate an in-memory API credential; never persist or return the credential."""
import json,urllib.request,urllib.error

def list_models(key):
 if not 20<=len(key)<=500 or any(c.isspace() for c in key):raise ValueError('Enter a valid OpenAI API key.')
 request=urllib.request.Request('https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+key,'Accept':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=20) as response:
   data=json.loads(response.read(2_000_000))
 except urllib.error.HTTPError as error:
  raise ValueError({401:'OpenAI rejected the API key.',403:'This key cannot list models. Check its project permissions.',429:'OpenAI rate-limited the connection check. Try again shortly.'}.get(error.code,'OpenAI could not validate this key.')) from None
 except Exception:raise ValueError('Could not reach OpenAI to validate the key. Check the connection and try again.') from None
 return {item['id'] for item in data.get('data',[]) if isinstance(item,dict) and isinstance(item.get('id'),str)}
