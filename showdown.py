"""Repeatable Harbor schedule and honest evidence export. No credentials in configs."""
import argparse, csv, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('ARENA_DATA_DIR',str(ROOT/'.arena'))).expanduser().resolve()
JOBS=Path(os.environ.get('SHOWDOWN_JOBS_DIR',str(DATA/'jobs')))
HARNESS={"codex":("ShowdownCodex","openai","0.163.0"),"opencode":("ShowdownOpenCode","openai","1.19.3"),"pi":("ShowdownPi","openai-codex","1.3.0")}
TASKS=['01-build','02-repair','03-search']
def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def auth_env():
    env=os.environ.copy()
    defaults={"CODEX_AUTH_JSON_PATH":Path.home()/'.codex/auth.json',"SHOWDOWN_OPENCODE_AUTH":DATA/'auth/opencode-data/opencode/auth.json',"SHOWDOWN_PI_AUTH":DATA/'auth/pi/auth.json'}
    for k,v in defaults.items(): env.setdefault(k,str(v))
    for key in ('OPENAI_API_KEY','OPENAI_BASE_URL','CODEX_API_KEY','PI_API_KEY'):
        env.pop(key,None)
    env['PYTHONUTF8']='1'
    env['PYTHONPATH']=str(ROOT)+os.pathsep+env.get('PYTHONPATH','')
    return env

def config(harness,model,task,job,install_only=False):
    cls,provider,version=HARNESS[harness]
    kwargs={'version':version}
    if harness=='codex': kwargs.update(reasoning_effort='medium',web_search='disabled',config={'features':{'multi_agent':False}})
    if harness=='opencode': kwargs.update(variant='medium',disable_web_search=True,opencode_config={
        'small_model':f'openai/{model}', 'share':'disabled', 'autoupdate':False,
        'agent':{'title':{'disable':True},'summary':{'model':f'openai/{model}'},'compaction':{'model':f'openai/{model}'},'explore':{'disable':True},'general':{'disable':True}},
        'permission':{'task':'deny','webfetch':'deny','websearch':'deny'},
        'provider':{'openai':{'models':{model:{'options':{'reasoningEffort':'medium'}}}}}})
    if harness=='pi': kwargs.update(thinking='medium')
    return {'job_name':job,'jobs_dir':str(JOBS),'n_attempts':1,'n_concurrent_trials':1,'retry':{'max_retries':0},'install_only':install_only,
        'agents':[{'import_path':'showdown_agents:'+cls,'model_name':f'{provider}/{model}','kwargs':kwargs,'exclude_logs':['**/auth.json','**/*credentials*']}],
        'tasks':[{'path':str(ROOT/'tasks'/task)}],'environment':{'type':'docker','delete':True}}

def plan(args):
    out=ROOT/'runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True,exist_ok=False)
    selected=TASKS if args.suite=='conference' else TASKS[:1]
    entries=[]
    for rep in range(args.attempts):
        for ti,task in enumerate(selected):
            names=list(HARNESS); shift=(rep+ti)%3; names=names[shift:]+names[:shift]
            for h in names:
                if args.harness and h!=args.harness: continue
                job=f'{out.name}-{task}-{h}-r{rep+1}'
                c=config(h,args.model,task,job,args.install_only)
                # Validate with the installed Harbor schema before any Docker/model call.
                from harbor.models.job.config import JobConfig
                JobConfig.model_validate(c)
                dest=out/(job+'.json'); write_json(dest,c)
                entries.append({'harness':h,'task':task,'replicate':rep+1,'model':args.model,'config':str(dest),'job':job,'install_only':args.install_only})
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tasks').rglob('*') if p.is_file()}
    write_json(out/'manifest.json',manifest); write_json(out/'schedule.json',entries)
    print(f'Validated {len(entries)} configs. Schedule: {out / "schedule.json"}',flush=True)
    return out,entries

def run(args):
    out,entries=plan(args)
    if args.dry_run:return
    env=auth_env()
    if not args.install_only:
        for e in entries:
            key={'codex':'CODEX_AUTH_JSON_PATH','opencode':'SHOWDOWN_OPENCODE_AUTH','pi':'SHOWDOWN_PI_AUTH'}[e['harness']]
            if not Path(env[key]).is_file(): raise SystemExit(f'Missing native login for {e["harness"]}. See LOGIN.ps1. Configs are ready at {out}.')
        # Presence alone does not imply a usable Codex login.
        if any(e['harness']=='codex' for e in entries):
            check=subprocess.run(['codex','login','status'],capture_output=True,text=True)
            if check.returncode:raise SystemExit('Codex CLI is not signed in. Complete LOGIN.ps1 -Harness codex first.')
    status=[]
    for e in entries:
        print(f'\nRUN {e["harness"]} / {e["task"]} / repetition {e["replicate"]}',flush=True)
        proc=subprocess.run([str(Path(sys.executable).with_name('harbor.exe' if os.name=='nt' else 'harbor')),'run','--config',e['config']],cwd=ROOT,env=env)
        status.append({**e,'exit_code':proc.returncode}); write_json(out/'execution.json',status)
    report()
    if any(item['exit_code'] for item in status): raise SystemExit(1)

def blind(args):
    if not args.model: raise SystemExit('Supply --model for the audited pilot model.')
    import random, shutil
    chosen={}
    for p in sorted(set((ROOT/'jobs').glob('*/*/result.json')) | set(JOBS.glob('*/*/result.json'))):
        d=json.loads(p.read_text(encoding='utf-8'))
        h=(d.get('agent_info') or {}).get('name')
        if h not in HARNESS or d.get('exception_info') or d.get('task_name')!='01-build':continue
        requested=(d['config']['agent'].get('model_name') or '').split('/')[-1]
        app=p.parent/'artifacts/app/index.html'
        if requested==args.model and d.get('verifier_result') and app.is_file():chosen[h]=(app,d['trial_name'])
    if set(chosen)!=set(HARNESS):raise SystemExit('Blind export requires a completed graded build submission from each harness on the same requested model.')
    pairs=list(chosen.items());random.SystemRandom().shuffle(pairs)
    mapping={}
    for label,(h,(app,trial)) in zip('ABC',pairs):
        dest=ROOT/'materials/blind'/label;dest.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(app,dest/'index.html');mapping[label]={'harness':h,'trial':trial}
    private=DATA/'showdown-blind-key.json';write_json(private,mapping)
    print('Exported A/B/C apps. Organizer key is outside the public materials: '+str(private))
    print('Review model IDs and outputs before presenting. Run DEMO.ps1 to serve each app on a separate origin.')

def seconds(obj):
    if not obj or not obj.get('started_at') or not obj.get('finished_at'):return None
    return round((datetime.fromisoformat(obj['finished_at'])-datetime.fromisoformat(obj['started_at'])).total_seconds(),3)

def report():
    rows=[]
    for path in sorted(set((ROOT/'jobs').glob('*/*/result.json')) | set(JOBS.glob('*/*/result.json'))):
        d=json.loads(path.read_text(encoding='utf-8')); a=d.get('agent_result') or {}; cfg=d['config']['agent']; name=(d.get('agent_info') or {}).get('name') or cfg.get('name') or cfg.get('import_path','unknown').split(':')[-1]
        if name not in HARNESS or d.get('config',{}).get('install_only'):continue
        error=d.get('exception_info'); error_type=(error or {}).get('exception_type',''); rewards=(d.get('verifier_result') or {}).get('rewards') or {}; score=rewards.get('reward')
        trajpath=path.parent/'agent/trajectory.json'; model_ids=[]; tools=None
        if trajpath.is_file():
            traj=json.loads(trajpath.read_text(encoding='utf-8')); steps=traj.get('steps',[])
            model_ids=sorted({s['model_name'] for s in steps if s.get('model_name')}); tools=sum(len(s.get('tool_calls') or []) for s in steps)
        usage_source='harbor_adapter'
        tool_source='atif' if tools is not None else ''
        raw=path.parent/'agent/codex.txt'
        if name=='codex' and raw.is_file() and a.get('n_input_tokens') is None:
            events=[]
            for line in raw.read_text(encoding='utf-8').splitlines():
                try: events.append(json.loads(line))
                except ValueError: pass
            usage=[e['usage'] for e in events if e.get('type')=='turn.completed' and isinstance(e.get('usage'),dict)]
            if usage:
                for target,key in [('n_input_tokens','input_tokens'),('n_cache_tokens','cached_input_tokens'),('n_output_tokens','output_tokens')]:
                    a[target]=sum(u[key] for u in usage) if all(key in u for u in usage) else None
                usage_source='codex_cli_turn_completed_fallback'
            items=[e.get('item',{}) for e in events if e.get('type')=='item.completed']
            tools=sum(1 for i in items if i.get('type') in ('command_execution','file_change','mcp_tool_call','web_search'))
            tool_source='codex_cli_completed_action_items'
        review='CONFIG_AND_TRAJECTORY_METADATA_MATCH' if model_ids and all(x.split('/')[-1]==(cfg.get('model_name') or '').split('/')[-1] for x in model_ids) else 'NEEDS_REVIEW'
        status=('agent_timeout' if 'AgentTimeout' in error_type else ('agent_error' if 'Agent' in error_type or 'NonZero' in error_type else 'runner_error')) if error else ('graded' if score is not None else 'ungraded')
        row={'harness':name,'experiment':('authentication_smoke' if path.parents[1].name in ['20261020T045705Z-01-build-codex-r1','20261020T050108Z-01-build-opencode-r1','20261020T050252Z-01-build-pi-r1'] else ('sequential_rehearsal_runner_error' if error_type=='UnicodeDecodeError' else 'sequential_rehearsal')),'task':d['task_name'],'requested_model':cfg.get('model_name'),'reported_models':';'.join(model_ids),'same_model_review':review,'status':status,'exception_type':error_type,'score':score,'agent_seconds':seconds(d.get('agent_execution')),'agent_started':(d.get('agent_execution') or {}).get('started_at'),'agent_finished':(d.get('agent_execution') or {}).get('finished_at'),'setup_seconds':seconds(d.get('environment_setup')),'input_tokens':a.get('n_input_tokens'),'cache_tokens':a.get('n_cache_tokens'),'output_tokens':a.get('n_output_tokens'),'tool_calls':tools,'usage_source':usage_source,'tool_count_source':tool_source,'reported_api_cost_not_invoice':a.get('cost_usd'),'actual_subscription_cost_usd':None,'trial':d['trial_name'],'evidence':str(path)}
        rows.append(row)
    for row in rows:
        start=row.get('agent_started');end=row.get('agent_finished')
        row['overlapping_agent_trials']=';'.join(other['trial'] for other in rows if other is not row and start and end and other.get('agent_started') and other.get('agent_finished') and max(start,other['agent_started']) < min(end,other['agent_finished']))
    dest=ROOT/'materials/results.csv'; dest.parent.mkdir(exist_ok=True)
    fields=list(rows[0]) if rows else ['harness','experiment','task','requested_model','reported_models','same_model_review','status','exception_type','score','agent_seconds','agent_started','agent_finished','setup_seconds','input_tokens','cache_tokens','output_tokens','tool_calls','usage_source','tool_count_source','reported_api_cost_not_invoice','actual_subscription_cost_usd','trial','evidence','overlapping_agent_trials']
    with dest.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    write_json(ROOT/'materials/results.json',rows)
    print(f'Exported {len(rows)} agent results to {dest}. Unreported usage and cost remain blank.')
    subprocess.run([sys.executable,str(ROOT/'summarize.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'audit.py')],check=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['run','plan','report','validate','baseline','blind']); ap.add_argument('--model'); ap.add_argument('--suite',choices=['pilot','conference'],default='pilot'); ap.add_argument('--attempts',type=int,default=1); ap.add_argument('--harness',choices=list(HARNESS)); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--install-only',action='store_true'); args=ap.parse_args()
    if args.action=='report':report()
    elif args.action=='blind':blind(args)
    elif args.action in ('validate','baseline'):
        mode='oracle' if args.action=='validate' else 'nop'
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        dest=ROOT/'runs'/f'{mode}-{stamp}.json'
        c={'job_name':f'{mode}-{stamp}','jobs_dir':str(JOBS),'n_attempts':1,'n_concurrent_trials':1,'retry':{'max_retries':0},'agents':[{'name':mode}],'tasks':[{'path':str(ROOT/'tasks'/x)} for x in TASKS]}
        write_json(dest,c)
        from harbor.models.job.config import JobConfig
        JobConfig.model_validate(c)
        if not args.dry_run:
            raise SystemExit(subprocess.run([str(Path(sys.executable).with_name('harbor.exe' if os.name=='nt' else 'harbor')),'run','--config',str(dest)],cwd=ROOT,env=auth_env()).returncode)
    else:
        if not args.model or not args.model.replace('-','').replace('.','').isalnum():ap.error('Supply an exact common model ID with --model; provider prefixes are added automatically.')
        if not 1<=args.attempts<=20:ap.error('--attempts must be between 1 and 20')
        if args.action=='plan':args.dry_run=True
        run(args)
