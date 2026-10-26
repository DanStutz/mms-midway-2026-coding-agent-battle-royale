"""Native Anthropic routes for the eight compatible harnesses."""
CLASSES={'opencode':'ShowdownApiOpenCode','pi':'ShowdownApiPi','aider':'ShowdownAider','goose':'ShowdownGoose','cline':'ShowdownCline','mini-swe-agent':'ShowdownMiniSwe','openhands':'ShowdownOpenHands','qwen':'ShowdownQwen'}
def configure(config,h,model,info,effort):
 if h not in CLASSES:raise ValueError('Codex CLI does not support Anthropic models.')
 agent=config['agents'][0];kw=agent['kwargs'];agent['import_path']='showdown_agents:'+CLASSES[h]
 agent['model_name']='anthropic'+(':' if h=='cline' else '/')+model
 # Aider and mini-SWE use their native model defaults. Forwarding OpenAI
 # reasoning_effort to older Anthropic clients can create invalid requests.
 kw.pop('reasoning_effort',None)
 if h=='opencode':
  kw.pop('variant',None)
  kw['opencode_config']={'small_model':'anthropic/'+model,'share':'disabled','autoupdate':False,
   'agent':{'title':{'disable':True},'summary':{'model':'anthropic/'+model},'compaction':{'model':'anthropic/'+model},'explore':{'disable':True},'general':{'disable':True}},
   'permission':{'task':'deny','webfetch':'deny','websearch':'deny'},
   'provider':{'anthropic':{'options':{'apiKey':'{env:ANTHROPIC_API_KEY}'},'models':{model:{'name':info.get('display_name',model),'limit':{'context':info.get('max_input_tokens') or 200000,'output':info.get('max_tokens') or 16384}}}}}}
 if h=='pi':kw['model_api']='anthropic-messages';kw['thinking']=effort;kw['anthropic_model_info']=info
 if h=='cline':kw['thinking']=effort
 if h in ('openhands','qwen'):kw['reasoning_effort']=effort;kw['model_info']=info
 return config

def environment(base,key):
 env=dict(base)
 for name in list(env):
  if name.startswith(('OPENAI_','ANTHROPIC_','AZURE_')) or name.endswith('_API_KEY') or name in ('API_KEY','CODEX_HOME','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON','SHOWDOWN_OPENCODE_AUTH','SHOWDOWN_PI_AUTH','ARENA_FOUNDRY'):env.pop(name,None)
 env.update(ANTHROPIC_API_KEY=key,ANTHROPIC_BASE_URL='https://api.anthropic.com',ARENA_ANTHROPIC='1',PI_TELEMETRY='false')
 return env
