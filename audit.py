"""Inspect saved configs and trajectories without reading credential files."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'materials/results.json').read_text(encoding='utf-8'))
lines=['MODEL AND CONFIGURATION AUDIT','',
'Boundary: these checks inspect saved local configuration and trajectory metadata. They do not attest to immutable backend weights or an itemized Enterprise invoice.','']
records=[]
for row in rows:
    if row.get('experiment')!='sequential_rehearsal':continue
    raw=json.loads(Path(row['evidence']).read_text(encoding='utf-8'));cfg=raw['config']['agent'];kw=cfg['kwargs'];h=row['harness'];requested=cfg['model_name'].split('/')[-1]
    effort=kw.get('reasoning_effort') if h=='codex' else kw.get('variant') if h=='opencode' else kw.get('thinking')
    metadata_models=[x.split('/')[-1] for x in row.get('reported_models','').split(';') if x]
    compatible=bool(metadata_models) and set(metadata_models)=={requested} and effort=='medium'
    info=raw.get('agent_info') or {}
    item={'harness':h,'task':row['task'],'trial':row['trial'],'requested_model':requested,'trajectory_models':metadata_models,'configured_reasoning':effort,'task_checksum':raw.get('task_checksum'),'cli_version':info.get('version'),'configuration_and_metadata_match':compatible}
    records.append(item)
    lines.append(f"{h} / {row['task']}: model {requested}; configured effort {effort}; CLI {item['cli_version']}; metadata agrees: {compatible}")
checksum_match=all(len({r['task_checksum'] for r in records if r['task']==task})==1 for task in {r['task'] for r in records})
lines.append('Shared task checksums agree across available harness results: '+str(checksum_match))
lines+=['','All task attempts use fresh containers and the same submitted task files. Native system prompts and tools remain part of the harness treatment.',
'OpenCode helper model settings point to the selected model; optional title generation and subagents are disabled. No added skills or MCP servers are configured.',
'Initial authentication smoke tests and the recorded Windows Unicode runner failure are excluded here. See RUNNER-REPAIRS.txt for the reason and preserved trial ID.',
'Token counts are provider/adapter reports. Missing counters are not zero. Repetition and run-order balancing remain necessary before ranking performance.']
(ROOT/'materials/MODEL-AUDIT.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(ROOT/'materials/model-audit.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(f'Audited {len(records)} sequential result configurations; credential files were not read.')
