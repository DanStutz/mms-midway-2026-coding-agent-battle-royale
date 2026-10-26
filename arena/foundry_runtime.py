"""Create native harness configs for a Foundry OpenAI v1 connection."""
import os
from copy import deepcopy
CLASSES={'codex':'ShowdownCodex','opencode':'ShowdownFoundryOpenCode','pi':'ShowdownFoundryPi','aider':'ShowdownAider','goose':'ShowdownGoose','cline':'ShowdownFoundryCline','mini-swe-agent':'ShowdownMiniSwe','openhands':'ShowdownOpenHands','qwen':'ShowdownQwen'}
def configure(config,h,model,info,endpoint):
 agent=config['agents'][0];kw=agent['kwargs'];kw.pop('opencode_config',None) if h!='opencode' else None
 agent['import_path']='showdown_agents:'+CLASSES[h]
 agent['model_name']=(('arena-foundry:' if info['responses'] else 'openai:') if h=='cline' else 'openai/')+model
 if not info['reasoning']:
  for key in ('reasoning_effort','thinking','variant'):kw.pop(key,None)
  if h=='pi':kw['thinking']='off'
 if h=='codex':
  kw['config']={'features':{'multi_agent':False},'model_provider':'arena_foundry','model_providers':{'arena_foundry':{'name':'Microsoft Foundry','base_url':endpoint,'env_key':'OPENAI_API_KEY','wire_api':'responses','requires_openai_auth':False}}}
 if h=='opencode':
  provider=kw['opencode_config']['provider']['openai'];provider['options']={'baseURL':endpoint,'apiKey':'{env:OPENAI_API_KEY}'}
  if not info['reasoning']:provider['models'][model].pop('options',None)
 if h in ('openhands','qwen'):kw['model_info']=info
 if h=='pi':kw['model_api']='openai-responses' if info['responses'] else 'openai-completions'
 return config

def environment(base,key,endpoint):
 env=dict(base)
 for name in list(env):
  if name.startswith('OPENAI_') or name.endswith('_API_KEY') or name in ('API_KEY','CODEX_HOME','ANTHROPIC_AUTH_TOKEN','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON','CODEX_API_KEY','SHOWDOWN_OPENCODE_AUTH','SHOWDOWN_PI_AUTH','AZURE_API_KEY','AZURE_API_BASE','AZURE_OPENAI_API_KEY','AZURE_OPENAI_ENDPOINT','AZURE_API_VERSION'):env.pop(name,None)
 env.update(OPENAI_API_KEY=key,OPENAI_BASE_URL=endpoint,OPENAI_API_BASE=endpoint,ARENA_FOUNDRY='1',PI_TELEMETRY='false')
 return env
