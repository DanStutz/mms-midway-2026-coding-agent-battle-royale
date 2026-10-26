"""Create a plain-language result sheet from observed, labeled trial exports."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'materials/results.json').read_text(encoding='utf-8'))
formal=[r for r in rows if r.get('experiment')=='sequential_rehearsal']
smoke=[r for r in rows if r.get('experiment')=='authentication_smoke']
def fmt(value):return 'unavailable' if value is None else f'{value:,}'
lines=['ONE BRAIN, THREE TOOLBOXES','Observed rehearsal results','',f'Completed sequential attempts: {len(formal)}/9',f'Initial authentication smoke tests: {len(smoke)} (excluded from this summary)','',
'One attempt per harness per task. No general winner is established.',
'Time is agent execution only; setup and verification are excluded.',
'Input tokens include the adapter-reported cache total. Counters are provider/adapter reports.',
'Actual Enterprise cost per attempt is unavailable, not zero.','']
for h in ['codex','opencode','pi']:
    selected=[r for r in formal if r['harness']==h]
    lines.append(h.upper())
    for r in sorted(selected,key=lambda r:r['task']):
        lines.append(f"  {r['task']}: score {r['score']}; status {r['status']}; {r['agent_seconds']} seconds")
        lines.append(f"    input {fmt(r['input_tokens'])}; cached {fmt(r['cache_tokens'])}; output {fmt(r['output_tokens'])}; tool calls {fmt(r['tool_calls'])}")
        lines.append(f"    requested {r['requested_model']}; trajectory metadata {r['reported_models'] or 'unavailable'}")
        if r.get('overlapping_agent_trials'):lines.append('    OVERLAP: '+r['overlapping_agent_trials'])
    lines.append('')
lines+=['Interpretation: retain individual trials and compare the test matrix before speed or usage. Repeat the sequential schedule three times per task before presenting a performance ranking.',
'Model IDs can be server-side aliases. Session/config metadata does not attest to fixed backend weights.',
'See results.csv for provenance, audit status, trial paths and the separately labeled smoke tests.']
(ROOT/'materials/REHEARSAL-RESULTS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines[:12]))
