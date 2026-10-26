"""Recognize provider failures without exposing credentials or reasoning text."""
import json,re
MESSAGES={
 'deployment_not_found':'Azure could not find this deployment in the connected resource. Use the deployment name from Foundry, not a catalog model/version ID.',
 'authentication':'Azure rejected the Foundry credential. Reconnect using the resource key for this endpoint.',
 'permission':'Azure denied access to this deployment. Check resource permissions and network access.',
 'rate_limit':'Azure rate-limited this deployment. Reduce concurrent contestants or check deployment quota.',
 'unsupported':'Azure rejected an API operation or parameter for this deployment. Check the selected model and API compatibility.',
 'billing':'Provider billing or credit balance prevented the request. Check your API account billing.',
 'not_found':'Azure returned HTTP 404. Check the resource endpoint and deployment name.'}
def classify(text,provider='foundry'):
 candidates=[];lines=text.splitlines()
 def walk(value):
  if isinstance(value,dict):
   if value.get('type')=='error':candidates.append(json.dumps(value))
   if value.get('errorMessage'):candidates.append(str(value['errorMessage']))
   if isinstance(value.get('error'),(dict,str)):candidates.append(str(value['error']))
   if value.get('type')=='text' and str(value.get('text','')).startswith('Ran into this error:'):candidates.append(str(value['text']))
   for v in value.values():
    if isinstance(v,(dict,list)):walk(v)
  elif isinstance(value,list):
   for v in value:walk(v)
 for index,line in enumerate(lines):
  try:walk(json.loads(line))
  except ValueError:
   if re.search(r'litellm\.|BadRequestError|AuthenticationError|APIConnectionError|PermissionDeniedError|RateLimitError',line):candidates.append(' '.join(lines[index:index+4]))
 joined=' '.join(' '.join(candidates).lower().split())
 if not joined:return None,None
 if any(x in joined for x in ('credit balance is too low','insufficient_quota','insufficient credits')):kind='billing'
 elif 'deploymentnotfound' in joined or 'the api deployment for this resource does not exist' in joined or 'model_not_found' in joined:kind='deployment_not_found'
 elif 'authenticationerror' in joined or 'invalid_api_key' in joined or 'invalidapikey' in joined or re.search(r'\b401\b',joined):kind='authentication'
 elif 'ratelimiterror' in joined or re.search(r'\b429\b',joined):kind='rate_limit'
 elif 'permissiondeniederror' in joined or re.search(r'\b403\b',joined):kind='permission'
 elif any(s in joined for s in ['operationnotsupported','unsupported_parameter','unsupported parameter','not supported with this model','unsupported value','is not supported for this model','invalid_request_error','imagegen deployment must be provided','function tools with reasoning_effort are not supported']):kind='unsupported'
 elif re.search(r'\b404\b',joined):kind='not_found'
 else:return None,None
 message=MESSAGES[kind]
 if provider=='anthropic':
  message=message.replace('Azure','Anthropic').replace('Foundry credential','Anthropic API credential').replace('resource key for this endpoint','Anthropic API key').replace('deployment','model')
  if kind=='deployment_not_found':message='Anthropic could not find or access this model. Refresh the Claude model list.'
 return kind,message
