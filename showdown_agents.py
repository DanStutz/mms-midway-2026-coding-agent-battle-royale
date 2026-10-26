"""Harbor adapters: native agent loops; preinstalled versions and isolated OAuth files."""
from pathlib import Path
import os, shlex
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.opencode import OpenCode
from harbor.agents.installed.pi import Pi

# Harbor 0.24 has implicit Path.read_text() calls for UTF-8 JSON logs.
# Some Windows Python installations default those calls to cp1252.
# Keep this compatibility shim confined to benchmark runner processes.
if os.name == "nt":
    _original_read_text = Path.read_text
    def _read_utf8_text(self, *args, **kwargs):
        if not args and kwargs.get("encoding") is None:
            kwargs["encoding"] = "utf-8"
        elif args and args[0] is None:
            args = ("utf-8",) + args[1:]
        return _original_read_text(self, *args, **kwargs)
    Path.read_text = _read_utf8_text

class Preinstalled:
    async def run(self,instruction,environment,context):
        import time
        marker=self.logs_dir/'arena-execution.json'
        marker.parent.mkdir(parents=True,exist_ok=True)
        clock={'started_epoch':time.time()}
        def save_clock():
            temporary=marker.with_suffix('.tmp')
            temporary.write_text(json.dumps(clock),encoding='utf-8');temporary.replace(marker)
        save_clock()
        try:return await super().run(instruction,environment,context)
        finally:
            clock['finished_epoch']=time.time();save_clock()

    async def install(self, environment):
        command = {"codex":"codex --version", "opencode":"opencode --version", "pi":"pi --version", "aider":"aider --version", "goose":"goose --version", "mini-swe-agent":"/opt/arena-mini/bin/pip show mini-swe-agent", "cline-cli":"cline --version", "qwen-coder":"qwen --version", "openhands-sdk":"/opt/openhands-sdk-venv/bin/python -c 'import openhands.sdk; print(openhands.sdk.__version__)'"}[self.name()]
        result = await self.exec_as_agent(environment, command)
        if result.return_code or not result.stdout or self._version not in result.stdout:
            raise RuntimeError("Preinstalled harness version mismatch: " + self.name())

async def upload_private(agent, environment, env_name, remote):
    source = Path(os.environ[env_name])
    if not source.is_file(): raise RuntimeError("Complete native login first: " + env_name)
    folder = str(Path(remote).parent).replace("\\", "/")
    await agent.exec_as_agent(environment, "mkdir -p " + shlex.quote(folder))
    await agent._upload_agent_owned_file(environment, source, remote)
    await agent.exec_as_agent(environment, "chmod 600 " + shlex.quote(remote))

class ShowdownCodex(Preinstalled, Codex):
    pass

class ShowdownOpenCode(Preinstalled, OpenCode):
    async def exec_as_agent(self, environment, command, env=None, cwd=None, timeout_sec=None):
        if env and "XDG_DATA_HOME" in env:
            env = dict(env)
            # Native adapter otherwise puts OAuth auth.json inside exported logs.
            env["XDG_DATA_HOME"] = "/tmp/showdown-opencode-data"
        return await super().exec_as_agent(environment, command, env, cwd, timeout_sec)
    async def run(self, instruction, environment, context):
        await upload_private(self, environment, "SHOWDOWN_OPENCODE_AUTH", "/tmp/showdown-opencode-data/opencode/auth.json")
        return await super().run(instruction, environment, context)

class ShowdownPi(Preinstalled, Pi):
    async def exec_as_agent(self, environment, command, env=None, cwd=None, timeout_sec=None):
        env = dict(env or {})
        env["PI_CODING_AGENT_DIR"] = "/tmp/showdown-pi"
        env["PI_TELEMETRY"] = "false"
        return await super().exec_as_agent(environment, command, env, cwd, timeout_sec)
    async def run(self, instruction, environment, context):
        await upload_private(self, environment, "SHOWDOWN_PI_AUTH", "/tmp/showdown-pi/auth.json")
        return await super().run(instruction, environment, context)

from harbor.agents.installed.aider import Aider
import json,re

class ShowdownAider(Preinstalled,Aider):
    async def exec_as_agent(self, environment, command, env=None, cwd=None, timeout_sec=None):
        env=dict(env or {})
        if 'aider --yes ' in command:
            model=self.model_name
            command=command.replace('aider --yes ', 'aider --yes --no-stream --file /app/index.html --no-auto-commits --no-check-update --no-analytics --model-settings-file /tmp/arena-aider-models.yml ')
            command=command.replace('--model='+shlex.quote(model.split('/',1)[1]),'--model='+shlex.quote(model))
            command=command.replace('aider --yes ','/opt/arena-aider/bin/python /tmp/arena-aider-run.py --yes ')
            command='set -o pipefail; '+command
            env.update(AIDER_WEAK_MODEL=model,AIDER_EDITOR_MODEL=model,LITELLM_LOG='ERROR')
        result=await super().exec_as_agent(environment,command,env,cwd,timeout_sec)
        if '/tmp/arena-aider-run.py --yes ' in command:
            if result.return_code:raise RuntimeError('Aider exited unsuccessfully; check API model access and billing.')
            if re.search(r'(AuthenticationError|BadRequestError|PermissionDeniedError|RateLimitError)',result.stdout or ''):
                raise RuntimeError('Aider API request failed; check API model access, reasoning support, and billing.')
        return result
    async def run(self,instruction,environment,context):
        model=self.model_name
        settings=[{'name':model,'edit_format':'diff','use_repo_map':True,'weak_model_name':model,'editor_model_name':model,'use_temperature':False,'extra_params':({'reasoning_effort':self.options.reasoning_effort or 'medium'} if self.options.reasoning_effort or not os.environ.get('ARENA_FOUNDRY') else {}),'accepts_settings':(['reasoning_effort'] if self.options.reasoning_effort or not os.environ.get('ARENA_FOUNDRY') else [])}]
        if model.startswith('anthropic/'):
            settings[0]['extra_params']={};settings[0]['accepts_settings']=[]
        await self._upload_agent_owned_file(environment,Path(__file__).parent/'arena/aider_meter.py','/tmp/arena-aider-run.py')
        payload=json.dumps(settings)
        await self.exec_as_agent(environment,'printf %s '+shlex.quote(payload)+' > /tmp/arena-aider-models.yml')
        return await super().run(instruction,environment,context)


    def populate_context_post_run(self,context):
        path=self.logs_dir/'aider-usage.jsonl'
        if not path.exists():return
        records=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            try:records.append(json.loads(line))
            except ValueError:pass
        if not records:return
        for target,key in [('n_input_tokens','input_tokens'),('n_cache_tokens','cache_tokens'),('n_output_tokens','output_tokens')]:
            values=[record.get(key) for record in records]
            setattr(context,target,sum(values) if all(isinstance(value,int) for value in values) else None)
        estimates=[r.get('estimated_cost_usd') for r in records]
        context.cost_usd=sum(estimates) if all(isinstance(v,(int,float)) for v in estimates) else None
        context.metadata={'usage_source':'litellm_completion_response_usage','reported_models':sorted({str(r['reported_model']) for r in records if r.get('reported_model')}),'cost_is_estimate_not_invoice':True}

from harbor.agents.installed.goose import Goose
from harbor.agents.installed.mini_swe_agent import MiniSweAgent
from harbor.agents.installed.cline.cline import ClineCli

class ShowdownGoose(Preinstalled,Goose):
    async def install(self,environment):
        await super().install(environment)
        settings={'GOOSE_PROVIDER':self.model_name.split('/',1)[0],'GOOSE_MODEL':self.model_name.split('/',1)[1],'extensions':{'developer':{'name':'developer','type':'builtin','enabled':True},'todo':{'name':'todo','type':'platform','enabled':True}}}
        await self.exec_as_agent(environment,'mkdir -p ~/.config/goose && printf %s '+shlex.quote(json.dumps(settings))+' > ~/.config/goose/config.yaml')
    async def exec_as_agent(self,environment,command,env=None,cwd=None,timeout_sec=None):
        env=dict(env or {});env.update(GOOSE_DISABLE_KEYRING='true',GOOSE_MODE='auto',GOOSE_TELEMETRY_ENABLED='false')
        if 'goose run ' in command:command='set -o pipefail; '+command
        result=await super().exec_as_agent(environment,command,env,cwd,timeout_sec)
        if 'goose run ' in command and result.return_code:raise RuntimeError('Goose failed. Check API access and model support.')
        return result

class ShowdownMiniSwe(Preinstalled,MiniSweAgent):
    async def exec_as_agent(self,environment,command,env=None,cwd=None,timeout_sec=None):
        if 'mini-swe-agent --yolo' in command:command='set -o pipefail; '+command
        result=await super().exec_as_agent(environment,command,env,cwd,timeout_sec)
        if 'mini-swe-agent --yolo' in command and result.return_code:raise RuntimeError('mini-SWE-agent failed. Check API access and model support.')
        return result

class ShowdownCline(Preinstalled,ClineCli):
    PROVIDER_API_KEY_ENVS={**ClineCli.PROVIDER_API_KEY_ENVS,"openai-native":"OPENAI_API_KEY"}



class ShowdownFoundryOpenCode(Preinstalled,OpenCode):
    """API-key route: no ChatGPT OAuth credential is uploaded."""
    pass

class ShowdownFoundryPi(Preinstalled,Pi):
    """Native Pi custom provider, with no subscription auth upload."""
    pass

# Cline's supported custom-provider settings preserve Responses/reasoning while
# avoiding the public OpenAI provider's automatic image-generation capability.
CLINE_FOUNDRY_SETUP = """import os,json,pathlib,datetime
p=pathlib.Path.home()/'.cline/data/settings/providers.json'
p.parent.mkdir(parents=True,exist_ok=True)
settings={'provider':'arena-foundry','model':os.environ['MODELID'],
 'apiKey':os.environ['API_KEY'],'baseUrl':os.environ['ARENA_FOUNDRY_BASE'],
 'protocol':'openai-responses','client':'openai',
 'capabilities':['reasoning','streaming','tools'],
 'modelCatalog':{'loadLatestOnInit':False,'includeClineCloudModels':False,'loadPrivateOnAuth':False}}
data={'version':1,'lastUsedProvider':'arena-foundry','modes':{},
 'providers':{'arena-foundry':{'settings':settings,'updatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}}}
p.write_text(json.dumps(data));p.chmod(0o600)
registry={'version':1,'providers':{'arena-foundry':{'provider':{
 'name':'Microsoft Foundry','baseUrl':settings['baseUrl'],'defaultModelId':settings['model'],
 'protocol':'openai-responses','client':'openai','capabilities':settings['capabilities']},
 'models':{settings['model']:{'id':settings['model'],'capabilities':['reasoning','tools'],
 'supportsReasoning':True,'apiFormat':'openai-responses'}}}}}
(p.parent/'models.json').write_text(json.dumps(registry))
"""

class ShowdownFoundryCline(ShowdownCline):
    PROVIDER_API_KEY_ENVS={**ShowdownCline.PROVIDER_API_KEY_ENVS,'arena-foundry':'OPENAI_API_KEY'}
    def create_run_agent_commands(self,instruction):
        original=self.model_name
        provider=original.split(':',1)[0]
        # Also accept already generated jobs from the previous Arena version.
        responses=provider in ('arena-foundry','openai-native')
        self.model_name=('arena-foundry:' if responses else 'openai:')+original.split(':',1)[1]
        try:commands=super().create_run_agent_commands(instruction)
        finally:self.model_name=original
        endpoint=os.environ.get('OPENAI_BASE_URL','')
        if not endpoint:raise ValueError('Foundry endpoint is required for Cline.')
        commands[0].env['ARENA_FOUNDRY_BASE']=endpoint
        if responses:commands[0].command+=' && python3 -c '+shlex.quote(CLINE_FOUNDRY_SETUP)
        else:commands[0].command+=' && cline auth --provider "$PROVIDER" --apikey "$API_KEY" --modelid "$MODELID" --baseurl "$ARENA_FOUNDRY_BASE" >/dev/null'
        return commands
    async def exec_as_agent(self,environment,command,env=None,cwd=None,timeout_sec=None):
        running='cline -P ' in command
        if running:command='set -o pipefail; '+command
        result=await super().exec_as_agent(environment,command,env,cwd,timeout_sec)
        failed=False
        if running:
            for line in (result.stdout or '').splitlines():
                try:
                    event=json.loads(line)
                    if isinstance(event,dict) and event.get('type')=='error':failed=True
                except ValueError:pass
        if (running or 'cline auth ' in command) and (result.return_code or failed):raise RuntimeError('Cline Foundry request failed. Check the deployment name, API support and Azure permissions.')
        return result

# Native API routes intentionally do not upload subscription credential files.
class ShowdownApiOpenCode(Preinstalled,OpenCode):
    pass

class AnthropicPiOptions(Pi.options_model):
    anthropic_model_info:dict={}

class ShowdownApiPi(Preinstalled,Pi):
    options_model=AnthropicPiOptions
    def __init__(self,*args,anthropic_model_info=None,**kwargs):
        self._anthropic_model_info=anthropic_model_info or {}
        super().__init__(*args,**kwargs)
    def _build_custom_models_json(self,access,model_id):
        result=super()._build_custom_models_json(access,model_id)
        if result and self.model_name.startswith('anthropic/'):
            model=result['providers']['harbor-endpoint']['models'][0]
            info=self._anthropic_model_info
            types=((info.get('capabilities') or {}).get('thinking') or {}).get('types') or {}
            # Preserve API capability metadata in Pi's native custom-model registry.
            adaptive=(types.get('adaptive') or {}).get('supported')
            if adaptive is None:adaptive=bool(re.match(r'^claude-(?:opus|sonnet)-(?:4-[6-9]|[5-9])|^claude-(?:haiku|fable|mythos)-[5-9]',model_id))
            model['compat']={'forceAdaptiveThinking':adaptive}
            model['contextWindow']=info.get('max_input_tokens') or 200000
            model['maxTokens']=info.get('max_tokens') or 16384
        return result

from harbor.agents.installed.openhands_sdk import OpenHandsSDK
from harbor.agents.installed.qwen_code import QwenCode
from harbor.agents.model_connection import ModelConnectionSpec

class ArenaOpenHandsOptions(OpenHandsSDK.options_model):
    model_info:dict={}

class ShowdownOpenHands(Preinstalled,OpenHandsSDK):
    options_model=ArenaOpenHandsOptions
    def __init__(self,*args,model_info=None,**kwargs):
        self._arena_model_info=model_info or {}
        super().__init__(*args,**kwargs)
    async def install(self,environment):
        await Preinstalled.install(self,environment)
        await self._upload_agent_owned_file(environment,Path(__file__).parent/'arena/openhands_runner.py','/installed-agent/run_agent.py')
    async def exec_as_agent(self,environment,command,env=None,cwd=None,timeout_sec=None):
        env=dict(env or {})
        if '/installed-agent/run_agent.py' in command:
            command='set -o pipefail; '+command
            env.update(PYTHONUNBUFFERED='1',ARENA_API_MODE='responses' if self.model_name.startswith('openai/') and self._arena_model_info.get('responses',True) else 'chat',ARENA_MODEL_INFO=json.dumps(self._arena_model_info),ARENA_REASONING='1' if self.options.reasoning_effort else '0')
        result=await super().exec_as_agent(environment,command,env,cwd,timeout_sec)
        if '/installed-agent/run_agent.py' in command and result.return_code:raise RuntimeError('OpenHands SDK failed. Check provider access, model support and local runner logs.')
        return result

class ArenaQwenOptions(QwenCode.options_model):
    reasoning_effort:str|None=None
    model_info:dict={}

class ShowdownQwen(Preinstalled,QwenCode):
    MODEL_CONNECTION=ModelConnectionSpec(passthrough=True)
    options_model=ArenaQwenOptions
    def __init__(self,*args,reasoning_effort=None,model_info=None,**kwargs):
        self._arena_effort=reasoning_effort;self._arena_model_info=model_info or {}
        super().__init__(*args,**kwargs)
    def arena_settings(self):
        provider,model=self.model_name.split('/',1);info=self._arena_model_info
        row={'id':model,'envKey':'ANTHROPIC_API_KEY' if provider=='anthropic' else 'OPENAI_API_KEY',
             'baseUrl':os.environ.get('ANTHROPIC_BASE_URL','https://api.anthropic.com') if provider=='anthropic' else os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1')}
        if provider=='openai':row['wireApi']='responses' if info.get('responses',True) else 'chat-completions'
        if self._arena_effort:
            row['generationConfig']={'reasoning':{'effort':self._arena_effort}}
            adaptive=((info.get('capabilities') or {}).get('thinking') or {}).get('types',{}).get('adaptive',{}).get('supported')
            if adaptive is None:adaptive=bool(re.match(r'^claude-(?:opus|sonnet)-(?:4-[6-9]|[5-9])|^claude-(?:haiku|fable|mythos)-[5-9]',model))
            row['capabilities']={'reasoning':{'profile':('anthropic-adaptive' if adaptive else 'anthropic-manual') if provider=='anthropic' else 'openai-reasoning','efforts':['low','medium','high'],'defaultEffort':self._arena_effort}}
        return {'$version':4,'security':{'auth':{'selectedType':provider}},'model':{'name':model},'modelProviders':{provider:[row]},'tools':{'exclude':['task','web_fetch','web_search']},'telemetry':{'enabled':False},'memory':{'enableManagedAutoMemory':False,'enableManagedAutoDream':False,'enableAutoSkill':False,'enableTeamMemory':False}}
    async def install(self,environment):
        await Preinstalled.install(self,environment)
        await self._upload_agent_owned_file(environment,Path(__file__).parent/'arena/qwen_meter.mjs','/tmp/arena-qwen-meter.mjs')
        settings=json.dumps(self.arena_settings())
        await self.exec_as_agent(environment,'mkdir -p ~/.qwen && printf %s '+shlex.quote(settings)+' > ~/.qwen/settings.json && chmod 600 ~/.qwen/settings.json')
    async def exec_as_agent(self,environment,command,env=None,cwd=None,timeout_sec=None):
        running='qwen --yolo --auth-type openai' in command
        if running:
            env=dict(env or {});env['NODE_OPTIONS']='--import /tmp/arena-qwen-meter.mjs'
            provider,model=self.model_name.split('/',1)
            old='qwen --yolo --auth-type openai --openai-api-key "$OPENAI_API_KEY" --openai-base-url "${OPENAI_BASE_URL:-https://api.openai.com/v1}" '
            command=command.replace(old,'qwen --yolo --advisor off --output-format stream-json --auth-type '+provider+' --model '+shlex.quote(model)+' ')
            command='set -o pipefail; '+command
        result=await super().exec_as_agent(environment,command,env,cwd,timeout_sec)
        failed=False
        if running:
            for line in (result.stdout or '').splitlines():
                try:
                    event=json.loads(line)
                    if isinstance(event,dict) and (event.get('is_error') or event.get('type')=='error'):failed=True
                except ValueError:pass
            if result.return_code or failed:raise RuntimeError('Qwen Code failed. Check provider access, model support and local runner logs.')
        return result

    def populate_context_post_run(self,context):
        super().populate_context_post_run(context)
        from arena.new_harness_usage import collect
        counters=collect(self.logs_dir,'qwen')
        for target,source in [('n_input_tokens','input_tokens'),('n_output_tokens','output_tokens'),('n_cache_tokens','cache_tokens')]:
            if source in counters:setattr(context,target,counters[source])
