'use strict';

const $=id=>document.getElementById(id);

const pricing=window.AgentArenaPricing;

const names={codex:'Codex CLI',opencode:'OpenCode',pi:'Pi',aider:'Aider',goose:'Goose',cline:'Cline CLI','mini-swe-agent':'mini-SWE-agent',openhands:'OpenHands SDK',qwen:'Qwen Code'},colors={codex:'#83bcff',opencode:'#eab886',pi:'#b8a2ef',aider:'#f2d177',goose:'#82d4bc',cline:'#efa3b9','mini-swe-agent':'#93d3e5',openhands:'#f5a56b',qwen:'#a9d878'};

const apiHarnesses=['aider','goose','cline','mini-swe-agent','openhands','qwen'];

let individual=false,nextModels={},extraEntries=[],modelEditRunId=null,drafting=false;

let state={},current=null,poll=null,cards={},customPrompt=$('prompt').value,loading=false;

const active=s=>['queued','running','stopping'].includes(s);

const number=v=>v==null?'--':Number(v).toLocaleString();

const duration=v=>v==null?'--':`${Math.floor(Math.round(v)/60)}:${String(Math.round(v)%60).padStart(2,'0')}`;

function message(text){$('message').textContent=text||'';$('message').hidden=!text;}

async function api(url,body){url=window.AgentArenaTabs?.scope(url)||url;const response=await fetch(url,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Arena-Token':state.token}:{},body:body?JSON.stringify(body):undefined});if(!response.ok){let err;try{err=await response.json();}catch{}throw new Error(typeof err?.detail==='string'?err.detail:`Request failed (${response.status})`);}return response.json();}

function option(value,text){const o=document.createElement('option');o.value=value;o.textContent=text;return o;}

function formHints(){const preset=$('preset').value;const graded=preset!=='custom'&&$('prompt').value.trim()===state.presets?.[preset]?.trim();$('grading-hint').textContent=graded?'Fixed challenge / automatic browser checks enabled':'Custom prompt / compare the outputs; no automatic correctness score';$('grading-hint').classList.toggle('graded',graded);$('char-count').textContent=`${$('prompt').value.length.toLocaleString()} / 20,000`;$('mode-hint').textContent=$('mode').value==='parallel'?'Best for the stage. Contestants run at the same time.':'Runs one at a time to reduce contention. Compare repeated runs.';}

function selectedHarnesses(){return [...document.querySelectorAll('input[name="harness"]:checked')].map(x=>x.value);}

function selectedEntries(){return selectedHarnesses().flatMap(h=>[{id:h,harness:h},...extraEntries.filter(e=>e.harness===h)]);}
function entryHarness(id){return cards[id]?.harness||extraEntries.find(e=>e.id===id)?.harness||current?.contestants[id]?.harness||id;}
function loadCurrentEntries(){
 if(!current||modelEditRunId===current.id)return;
 extraEntries=current.harnesses.filter(id=>id!==(current.contestants[id].harness||id)).map(id=>({id,harness:current.contestants[id].harness||id}));
 const selected=new Set(Object.entries(current.contestants).map(([id,i])=>i.harness||id));
 for(const box of document.querySelectorAll('input[name="harness"]'))box.checked=!box.disabled&&selected.has(box.value);
 nextModels=Object.fromEntries(current.harnesses.map(id=>[id,current.contestants[id].model||current.models?.[id]||current.model]));modelEditRunId=current.id;
}
function enableIndividual(){individual=true;$('individual-models').setAttribute('aria-pressed','true');$('individual-models').textContent='Use shared model';}
function addInstance(id){
 if(active(current?.status))return;
 loadCurrentEntries();const h=entryHarness(id),entries=selectedEntries();
 if(entries.length>=(state.max_contestants||14)){message('A comparison supports up to 14 contestants. Remove an instance or open New arena.');return;}
 for(const e of entries)if(!nextModels[e.id])nextModels[e.id]=$('model').value;
 let n=2;while(entries.some(e=>e.id===h+'-'+n))n++;
 const cid=h+'-'+n,used=entries.filter(e=>e.harness===h).map(e=>nextModels[e.id]),choices=modelChoices(h);
 extraEntries.push({id:cid,harness:h});nextModels[cid]=choices.find(m=>!used.includes(m))||nextModels[id]||choices[0]||'';
 enableIndividual();prepareDraft();saveArenaDraft();cards[cid]?.el.querySelector('.tile-model').focus();
 message('Added another '+names[h]+'. Choose its model on the new tile, then Start comparison.');
}
function removeInstance(id){if(active(current?.status))return;loadCurrentEntries();extraEntries=extraEntries.filter(e=>e.id!==id);delete nextModels[id];prepareDraft();saveArenaDraft();}
function selectedProvider(){return $('provider').value||'default';}

function connected(h){h=entryHarness(h);return state.provider_connections?.[selectedProvider()]?.[h]??(selectedProvider()==='default'?state.connections[h]:false);}

function modelChoices(h){h=entryHarness(h);if(state.provider_catalogs)return state.provider_catalogs[selectedProvider()]?.[h]||[];if(state.models_by_harness)return state.models_by_harness[h]||[];return state.models.filter(m=>!apiHarnesses.includes(h)||(state.api_models||state.aider_models||[]).includes(m));}

function buildChoices(){if($('harness-options').children.length)return;for(const h of Object.keys(names)){const label=document.createElement('label');label.className='chip';label.title=state.harnesses?.[h]?.description||names[h];const input=document.createElement('input');input.type='checkbox';input.name='harness';input.value=h;input.checked=['codex','opencode','pi'].includes(h);const dot=document.createElement('span');dot.className='dot';dot.style.background=colors[h];const name=document.createElement('span');name.textContent=names[h];const auth=document.createElement('span');auth.className='auth';auth.id='auth-'+h;label.append(input,dot,name,auth);$('harness-options').append(label);input.onchange=()=>{if(!input.checked)extraEntries=extraEntries.filter(e=>e.harness!==h);connections(state);if(!active(current?.status)){prepareDraft();saveArenaDraft();}};}}

function fillTileSelectors(){for(const [h,c] of Object.entries(cards)){const select=c.el.querySelector('.tile-model');const models=modelChoices(h);if(!nextModels[h]||!models.includes(nextModels[h]))nextModels[h]=models.includes($('model').value)?$('model').value:models[0]||'';select.replaceChildren(...models.map(m=>option(m,m)));if(!models.length)select.append(option('','No models available; refresh models'));select.value=nextModels[h];select.disabled=active(current?.status)||!connected(h);c.el.querySelector('.choose-model').disabled=active(current?.status)||!connected(h);c.el.querySelector('.tile-model-label').hidden=!individual;c.el.querySelector('.add-instance').disabled=active(current?.status)||!connected(h)||selectedEntries().length>=(state.max_contestants||14);c.el.querySelector('.remove-instance').disabled=active(current?.status);}}

function connections(data){pricing.setAnthropicRates(data.anthropic_pricing);buildChoices();const chosen=$('model').value;let n=0;for(const h of Object.keys(names)){const yes=!!connected(h);n+=Number(yes);const box=document.querySelector(`input[name="harness"][value="${h}"]`);box.disabled=!yes;if(box.disabled)box.checked=false;$('auth-'+h).textContent=yes?'ready':selectedProvider()==='foundry'?(data.foundry?.connected?'no compatible models':'Foundry key needed'):apiHarnesses.includes(h)?'API key needed':'sign in';$('auth-'+h).classList.toggle('ready',yes);}const selected=selectedHarnesses();const models=selected.length?selected.map(modelChoices).reduce((a,b)=>a.filter(m=>b.includes(m))):[];$('model').replaceChildren(...models.map(m=>option(m,m)));if(models.includes(chosen))$('model').value=chosen;else if(models.includes('gpt-6-sol'))$('model').value='gpt-6-sol';if(!models.length)$('model').append(option('',selected.length?'No model shared by selected contestants':'Select contestants first'));const empty=selected.filter(h=>!modelChoices(h).length);$('model-availability').textContent=individual?'Each tile uses its own connection’s model list.':!selected.length?'Select contestants to see available models.':empty.length?'No model catalog for '+empty.map(h=>names[h]).join(', ')+'. Refresh models or deselect that contestant.':!models.length?'These contestants have no shared model. Choose Individual models or change the selection.':(selectedProvider()==='default'&&selected.includes('codex')&&data.personal?.anthropic?.connected?'Codex CLI uses OpenAI only. Deselect Codex for shared Claude models, or choose Individual models.':'Showing models available to the selected contestants.');$('model').disabled=individual;$('connections').textContent=`${n}/${Object.keys(names).length} connected`;$('connections').classList.toggle('ready',n===Object.keys(names).length);$('connect-aider').textContent=(data.personal?.openai?.connected??data.connections.aider)?'OpenAI API connected':'Connect OpenAI API';$('disconnect-aider').hidden=!(data.personal?.openai?.connected??data.connections.aider);$('connect-claude').textContent=data.personal?.anthropic?.connected?'Claude API connected':'Connect Claude API';$('disconnect-claude').hidden=!data.personal?.anthropic?.connected;$('connect-foundry').textContent=state.foundry?.connected?'Foundry connected':'Connect Foundry';$('disconnect-foundry').hidden=!state.foundry?.connected;fillTileSelectors();}

function layoutCards(n){$('contestants').classList.toggle('expanded',n>=4);$('contestants').classList.remove('four-up');$('contestants').style.gridTemplateColumns=n>=4?'':window.innerWidth>800?`repeat(${Math.max(n,1)},minmax(0,1fr))`:'';}

function prepareDraft(){if(active(current?.status)){message('Wait for the current race to finish before changing model mode.');return;}clearInterval(poll);poll=null;current=null;drafting=true;makeCards(selectedEntries().map(e=>e.id));$('results-title').textContent='Configure the next race';$('run-description').textContent=individual?'Choose the next model on each selected harness tile. Use + Add instance to compare the same harness with different models.':'The shared model will be used for every selected harness. Saved results remain in run history.';for(const id of ['export','cost-csv','reuse','cost-summary'])$(id).hidden=true;$('history').value='';$('stop').hidden=true;$('start').disabled=false;}



function history(){const chosen=$('history').value;$('history').replaceChildren(option('','Run history'),...state.history.map(r=>option(r.id,`${new Date(r.created_at.replace(/ZZ$/,'Z')).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})} / ${r.model} / ${r.prompt.slice(0,25)}`)));$('history').value=current?.id||chosen;}

async function reloadState(){state=await api('/api/state');window.AgentArenaTabs?.sync(state);connections(state);history();$('contract').textContent=state.runner_instructions;formHints();}

function makeCards(harnesses,definitions={}){const specs=Object.fromEntries(harnesses.map(id=>[id,{harness:definitions[id]?.harness||entryHarness(id)}]));const seen={};for(const id of harnesses){const base=specs[id].harness;seen[base]=(seen[base]||0)+1;specs[id].label=definitions[id]?.label||names[base]+(harnesses.filter(key=>specs[key].harness===base).length>1?' '+seen[base]:'');}cards={};$('contestants').replaceChildren();for(const h of harnesses){const base=specs[h].harness,label=specs[h].label;const card=document.createElement('article');card.className='contestant';card.style.setProperty('--accent',colors[base]);card.dataset.harness=base;card.dataset.contestant=h;card.innerHTML=`<div class="contestant-head"><h3>${label}<span class="version"></span></h3><span class="status">Ready</span></div><div class="model-bar"><div class="tile-model-heading"><span class="used-model">Next run configuration</span><span class="tile-actions"><button class="add-instance" type="button">+ Add instance</button><button class="remove-instance" type="button">Remove</button><button class="choose-model" type="button">Change model</button></span></div><label class="tile-model-label" hidden>Next run model<select class="tile-model" aria-label="${label} next run model"></select></label></div><div class="metrics"><div class="metric"><span class="label">Wall time</span><span class="value time">--</span></div><div class="metric"><span class="label">Input tokens</span><span class="value input">--</span></div><div class="metric"><span class="label">Output tokens</span><span class="value output">--</span></div></div><div class="cost-row"><div><span class="cost-caption">EST. API TOKEN VALUE / USD</span><strong class="usd">--</strong></div><span class="cost-basis">API equivalent</span></div><div class="detail-strip"><span class="tools">Tools --</span><span class="score">Awaiting challenge</span></div><div class="run-notice" hidden></div><div class="tabs" role="tablist" aria-label="${label} result"><button class="tab active" role="tab" aria-selected="true" data-tab="preview">Preview</button><button class="tab" role="tab" aria-selected="false" data-tab="activity">Activity</button><button class="tab" role="tab" aria-selected="false" data-tab="code">Code</button><button class="tab" role="tab" aria-selected="false" data-tab="output">Output</button></div><div class="panel" data-panel="preview"><div class="empty"><div class="symbol">*</div><p>The next great app starts here.</p><p>A preview appears when index.html is available.</p></div><iframe title="${label} app preview" sandbox="allow-scripts allow-same-origin allow-forms" hidden></iframe></div><div class="panel" data-panel="activity" hidden><ol class="activity-list"></ol></div><div class="panel" data-panel="code" hidden><pre class="output-text code-text">No index.html yet.</pre></div><div class="panel" data-panel="output" hidden><pre class="output-text final-text">The final response will appear here.</pre></div><div class="card-foot"><div><span class="agent-time">Agent time --</span><br><span class="billing"></span></div><div><button class="reset" type="button" hidden>Reset app</button><a class="open" target="_blank" rel="noopener" hidden>Open app &nearr;</a></div></div>`;

 for(const tab of card.querySelectorAll('.tab'))tab.onclick=()=>{for(const t of card.querySelectorAll('.tab')){t.classList.toggle('active',t===tab);t.setAttribute('aria-selected',t===tab?'true':'false');}for(const p of card.querySelectorAll('[data-panel]'))p.hidden=p.dataset.panel!==tab.dataset.tab;if(tab.dataset.tab==='code')loadCode(h);};

 card.querySelector('.reset').onclick=()=>{if(current?.contestants[h]?.preview_url)card.querySelector('iframe').src=current.contestants[h].preview_url+'?reset=1';};

 card.querySelector('.choose-model').onclick=()=>{if(active(current?.status))return;loadCurrentEntries();enableIndividual();connections(state);card.querySelector('.tile-model').focus();message('Choose a next-run model on each tile, then Start comparison. The displayed results keep their original models and costs.');};

 card.querySelector('.add-instance').onclick=()=>addInstance(h);card.querySelector('.add-instance').setAttribute('aria-label','Add another '+names[base]+' instance');card.querySelector('.remove-instance').hidden=h===base;card.querySelector('.remove-instance').onclick=()=>removeInstance(h);card.querySelector('.tile-model').onchange=event=>{nextModels[h]=event.target.value;saveArenaDraft();};cards[h]={el:card,harness:base,label,version:null};$('contestants').append(card);}

 layoutCards(harnesses.length);fillTileSelectors();

}

async function loadCode(h){if(!current)return;const rid=current.id;try{const r=await fetch(window.AgentArenaTabs?.scope(`/api/runs/${rid}/${h}/source`)||`/api/runs/${rid}/${h}/source`);if(!r.ok)throw new Error('Source unavailable');const text=await r.text();if(current?.id===rid)cards[h].el.querySelector('.code-text').textContent=text;}catch(e){message(e.message);}}

function render(run){if(!current||current.id!==run.id)makeCards(run.harnesses,run.contestants);current=run;drafting=false;$('history').value=run.id;const running=active(run.status);$('start').disabled=running;$('stop').hidden=!running;$('stop').disabled=run.status==='stopping';$('individual-models').disabled=running;$('provider').disabled=running;$('results-title').textContent=running?'The race is on':run.status==='complete'?'The results are in':run.status.replaceAll('_',' ');$('run-description').textContent=`${run.model_mode==='individual'?'Individual models':run.model} / ${run.reasoning} / ${run.timeout_minutes} min agent limit / ${run.mode==='parallel'?'live race':'sequential'} / ${run.prompt.slice(0,160)}`;$('cost-csv').hidden=false;$('reuse').hidden=false;$('export').hidden=false;$('export').href=window.AgentArenaTabs?.scope(`/api/runs/${run.id}/export`)||`/api/runs/${run.id}/export`;

 for(const h of run.harnesses){const item=run.contestants[h],c=cards[h],el=c.el,m=item.metrics||{};const actualModel=item.model||run.models?.[h]||run.model;const provider=item.provider||run.provider||'default';el.querySelector('.used-model').textContent=(provider==='foundry'?'Foundry deployment: ':'Used model: ')+actualModel;const cost=pricing.estimate(actualModel,m,provider,run.anthropic_pricing,run.foundry_models);el.querySelector('.cost-caption').textContent=provider==='foundry'?'EST. AZURE TOKEN VALUE / USD':'EST. API TOKEN VALUE / USD';el.querySelector('.usd').textContent=(cost.usd==null?'':'~')+pricing.money(cost.usd);el.querySelector('.cost-row').title=cost.note;el.querySelector('.cost-basis').textContent=provider==='foundry'?'Global Standard estimate':(provider==='anthropic'||provider==='openai'||apiHarnesses.includes(item.harness||h))?'API estimate':'Subscription equivalent';el.querySelector('.version').textContent=item.version||state.versions?.[item.harness||h]||'';const status=el.querySelector('.status');status.className='status '+item.status;const phaseLabels={waiting_for_slot:'Waiting for an agent slot',preparing_workspace:'Preparing workspace',starting:'Starting container',working:'Agent working',collecting:'Collecting output'};status.textContent=running&&['queued','starting','running'].includes(item.status)?phaseLabels[item.phase]||item.status.replaceAll('_',' '):item.status.replaceAll('_',' ');el.querySelector('.time').textContent=duration(item.elapsed_seconds);el.querySelector('.input').textContent=number(m.input_tokens);el.querySelector('.output').textContent=number(m.output_tokens);el.querySelector('.tools').textContent=`Tools ${number(m.tool_calls??item.live_tools)} / cached ${number(m.cache_tokens)}`;el.querySelector('.score').textContent=run.graded?(m.score?`${m.score.passed}/${m.score.total} checks`:'Checks pending'):'Custom / ungraded';el.querySelector('.agent-time').textContent=`Agent time ${duration(m.agent_seconds??item.agent_elapsed_seconds)} / limit ${run.timeout_minutes} min`;el.querySelector('.billing').textContent=[item.billing_route||'ChatGPT subscription',item.reasoning_note].filter(Boolean).join(' / ');const notice=el.querySelector('.run-notice');notice.hidden=!item.error;notice.textContent=item.error||'';el.querySelector('.final-text').textContent=[item.error,item.final_output].filter(Boolean).join('\n\n')||(item.status==='error'?'Runner error. See local Harbor logs for details.':'The final response will appear here.');const list=el.querySelector('.activity-list');list.replaceChildren(...(item.activity?.length?item.activity:[item.phase==='waiting_for_slot'?'Other arenas are using the available agent slots. Your timer starts when a slot is available.':item.phase==='preparing_workspace'?'Preparing the shared starter workspace; models have not started.':item.phase==='starting'?'Starting the container and checking the installed harness; agent timer has not started.':item.phase==='collecting'?'Agent finished; collecting output and token usage.':'Waiting for visible tool activity...']).map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));

 if(!item.has_preview){const empty=el.querySelector('.empty');empty.hidden=false;empty.querySelector('p').textContent=item.error||((item.phase==='preparing_workspace'||item.phase==='starting')?'Preparing the workspace. The agent timer starts after setup.':'Waiting for the first app edit.');}

 if(!item.has_preview&&item.preview_is_starter){const empty=el.querySelector('.empty');empty.hidden=false;empty.querySelector('p').textContent='Waiting for the first app edit.';el.querySelector('iframe').hidden=true;}

 if(item.has_preview){const frame=el.querySelector('iframe');el.querySelector('.empty').hidden=true;frame.hidden=false;el.querySelector('.reset').hidden=false;const open=el.querySelector('.open');open.hidden=false;open.href=item.preview_url;if(c.version!==item.preview_version){frame.src=item.preview_url;c.version=item.preview_version;if(!el.querySelector('[data-panel="code"]').hidden)loadCode(h);}}

 }

 fillTileSelectors();renderCostSummary(run);

 if(!running){clearInterval(poll);poll=null;}

}

async function selectRun(rid){clearInterval(poll);poll=null;if(!rid)return;try{const r=await api('/api/runs/'+rid);render(r);if(active(r.status))poll=setInterval(()=>pollRun(rid),2000);}catch(e){message(e.message);}}

async function pollRun(rid){if(loading)return;loading=true;try{if(current?.id===rid){const run=await api('/api/runs/'+rid);if(current?.id===rid){const wasActive=active(current.status);render(run);if(wasActive&&!active(run.status)){await reloadState();message(run.status==='complete'?'Comparison complete. Inspect the previews and download the results.':'Comparison finished. Review each contestant status.');}}}}catch(e){message(e.message);}finally{loading=false;}}

$('run-form').onsubmit=async event=>{event.preventDefault();saveArenaDraft();message('');const harnesses=selectedHarnesses();if(!harnesses.length){message('Select at least one harness.');return;}if(selectedEntries().length>(state.max_contestants||14)){message('Select at most 14 contestants, including added instances. Remove an instance or deselect a harness.');return;}if(!$('prompt').value.trim()){message('Write a prompt first.');return;}$('start').disabled=true;try{const run=await api('/api/runs',{...(window.AgentArenaTabs?{arena_id:window.AgentArenaTabs.id}:{}),prompt:$('prompt').value,model:individual?(nextModels[harnesses[0]]||$('model').value):$('model').value,provider:selectedProvider(),model_mode:individual?'individual':'shared',models:individual?Object.fromEntries(selectedEntries().map(e=>[e.id,nextModels[e.id]])):{},...(selectedEntries().some(e=>e.id!==e.harness)?{contestants:selectedEntries().map(e=>({...e,model:individual?nextModels[e.id]:$('model').value}))}:{harnesses}),preset:$('preset').value,mode:$('mode').value,reasoning:$('reasoning').value,timeout_minutes:Number($('timeout').value)});await reloadState();await selectRun(run.id);}catch(e){message(e.message);$('start').disabled=false;}};

$('stop').onclick=async()=>{if(!current)return;$('stop').disabled=true;try{await api(`/api/runs/${current.id}/stop`,{});message('Stopping this comparison. Completed results are kept.');await pollRun(current.id);}catch(e){message(e.message);$('stop').disabled=false;}};

$('refresh').onclick=async()=>{$('refresh').disabled=true;message('Checking local sign-ins and model catalogs...');try{const data=await api('/api/refresh',{});Object.assign(state,data);connections(data);message(data.models.length?'Models refreshed.': 'No common models found. Check the local sign-ins.');}catch(e){message(e.message);}finally{$('refresh').disabled=false;}};

$('preset').onchange=()=>{const key=$('preset').value;$('prompt').value=key==='custom'?customPrompt:state.presets[key]||'';formHints();};$('prompt').oninput=()=>{if($('preset').value==='custom')customPrompt=$('prompt').value;formHints();};$('mode').onchange=formHints;$('history').onchange=()=>selectRun($('history').value);$('present').onclick=()=>{document.body.classList.toggle('presentation');$('present').textContent=document.body.classList.contains('presentation')?'Show controls':'Presentation mode';};window.onresize=()=>layoutCards(Object.keys(cards).length);

(async()=>{try{await window.AgentArenaTabs?.ready;await reloadState();restoreArenaDraft();makeCards(selectedEntries().map(e=>e.id));$('start').disabled=false;if(state.active_id||state.history.length)await selectRun(state.active_id||state.history[0].id);}catch(e){message('Could not connect to the local runner: '+e.message);$('start').disabled=true;}})();



$('connect-aider').onclick=()=>{$('aider-key').value='';$('aider-connect-status').textContent=(state.personal?.openai?.connected??state.connections?.aider)?'An API key is connected in server memory. Replace it or disconnect below.':'';$('aider-dialog').showModal();};

$('close-aider').onclick=()=>{$('aider-key').value='';$('aider-dialog').close();};

$('aider-dialog').addEventListener('close',()=>{$('aider-key').value='';});

$('aider-connect-form').onsubmit=async event=>{event.preventDefault();$('save-aider').disabled=true;$('aider-connect-status').textContent='Verifying model access with OpenAI...';try{const data=await api('/api/connections/openai',{api_key:$('aider-key').value});$('aider-key').value='';await reloadState();$('aider-dialog').close();message(data.message+' Select any API-backed harness to include it in the next comparison. API calls are billed separately.');}catch(e){$('aider-connect-status').textContent=e.message;}finally{$('save-aider').disabled=false;}};

$('disconnect-aider').onclick=async()=>{try{await api('/api/connections/openai/disconnect',{});$('aider-key').value='';await reloadState();$('aider-dialog').close();message('OpenAI API disconnected. Existing subscription sign-ins and Claude access remain available. The in-memory key was cleared.');}catch(e){$('aider-connect-status').textContent=e.message;}};



$('reuse').onclick=()=>{if(!current)return;modelEditRunId=null;loadCurrentEntries();$('provider').value=current.provider||'default';individual=current.model_mode==='individual';nextModels={...(current.models||Object.fromEntries(current.harnesses.map(h=>[h,current.contestants[h].model||current.model])))};$('individual-models').setAttribute('aria-pressed',String(individual));$('individual-models').textContent=individual?'Use shared model':'Individual models';document.body.classList.remove('presentation');$('present').textContent='Presentation mode';$('preset').value=current.preset||'custom';$('prompt').value=current.prompt;if($('preset').value==='custom')customPrompt=current.prompt;$('reasoning').value=current.reasoning;$('timeout').value=String(Math.max(current.timeout_minutes||15,15));$('mode').value=current.mode;for(const box of document.querySelectorAll('input[name="harness"]'))box.checked=!box.disabled&&Object.entries(current.contestants).some(([id,i])=>(i.harness||id)===box.value);connections(state);if([...$('model').options].some(o=>o.value===current.model))$('model').value=current.model;formHints();message('Challenge loaded. Review the contestants and the 15-minute-or-longer limit before starting a new attempt. The original result is preserved.');$('prompt').focus();};

$('timeout').onchange=()=>{$('time-hint').textContent=`Each selected contestant gets ${$('timeout').value} minutes of agent time. Setup is separate. Larger apps may need 15 minutes or more.`;};



function renderCostSummary(run){
 const costs=pricing.rows(run),known=costs.filter(c=>typeof c.estimated_usd==='number'),total=known.reduce((n,c)=>n+c.estimated_usd,0),azure=run.provider==='foundry';
 $('cost-summary').hidden=false;$('total-cost').textContent=known.length?'~'+pricing.money(total):'--';
 const coverage=known.length===costs.length?'Across all selected contestants':known.length?`${known.length}/${costs.length} contestants reported priced usage; total is partial`:'Waiting for reported usage or a supported model rate';
 $('total-cost-note').textContent=coverage+(azure?' / Azure Global Standard list-price estimate':'');
 const details=costs.map(c=>{const name=c.model+(c.pricing_model!==c.model?' ('+c.pricing_model+')':'');return Number.isFinite(c.input_usd_per_million)?`${name}: $${c.input_usd_per_million} / 1M uncached input, $${c.cached_usd_per_million} cached input, $${c.output_usd_per_million} output${c.cache_write_usd_per_million!==''?`, $${c.cache_write_usd_per_million} cache writes`:''}.`:name+': '+c.assumptions;});
 $('rate-detail').textContent=[...new Set(details)].join(' ');
 if(azure)$('rate-detail').textContent+=` Microsoft public Global Standard short-context list prices; checked ${pricing.foundryVerified}. Actual agreement, geography, context size and deployment mode may differ. Cache writes use reported counters; missing write counts are valued as ordinary input. Temporary promotional discounts are not applied. Sources: ${[...new Set(costs.map(c=>c.source))].join(', ')}.`;
 if(costs.some(c=>c.provider==='anthropic'))$('rate-detail').textContent+=` Anthropic source: ${run.anthropic_pricing?.source||'https://claude.com/pricing#api'}; verified ${run.anthropic_pricing?.verified||'unknown'}. Cache writes use the published 5-minute TTL rate.`;
}



$('cost-csv').onclick=()=>{if(!current)return;const blob=new Blob(['\uFEFF'+pricing.csv(current)],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`agent-arena-${current.id}-costs.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};



$('individual-models').onclick=()=>{if(active(current?.status))return;individual=!individual;$('individual-models').setAttribute('aria-pressed',String(individual));$('individual-models').textContent=individual?'Use shared model':'Individual models';connections(state);prepareDraft();};

$('model').onchange=()=>{if(!individual)for(const e of selectedEntries())nextModels[e.id]=$('model').value;fillTileSelectors();};



$('provider').onchange=()=>{connections(state);if(!selectedHarnesses().length){for(const h of ['codex','opencode','pi']){const box=document.querySelector(`input[name="harness"][value="${h}"]`);box.checked=!box.disabled;}connections(state);}prepareDraft();};

window.AgentArenaFoundryConnected=async reply=>{

 if(!active(current?.status))$('provider').value='foundry';

 await reloadState();

 if(!selectedHarnesses().length&&!active(current?.status)){

  for(const h of ['opencode','pi','aider']){const box=document.querySelector(`input[name="harness"][value="${h}"]`);box.checked=!box.disabled;}

  connections(state);

 }

 if(!active(current?.status))prepareDraft();

 message(reply.message);

};



window.AgentArenaClaudeConnected=async reply=>{

 if(!active(current?.status)){

  $('provider').value='default';

  if(!individual){const box=document.querySelector('input[name="harness"][value="codex"]');if(box)box.checked=false;}

 }

 await reloadState();

 if(!active(current?.status)){

  if(!selectedHarnesses().length){for(const h of ['opencode','pi','aider']){const box=document.querySelector(`input[name="harness"][value="${h}"]`);box.checked=!box.disabled;}}

  connections(state);

  const claude=[...$('model').options].find(o=>o.value.startsWith('claude-'));

  if(claude&&!individual){$('model').value=claude.value;for(const h of selectedHarnesses())nextModels[h]=claude.value;}

  prepareDraft();

 }

 message(reply.message);

};



$('refresh-claude-pricing').onclick=async()=>{const button=$('refresh-claude-pricing');button.disabled=true;try{const snapshot=await api('/api/pricing/anthropic/refresh',{});pricing.setAnthropicRates(snapshot);message(`Anthropic rates refreshed from ${snapshot.source}, verified ${snapshot.verified}. Saved races keep their original rates.`);}catch(e){message(e.message);}finally{button.disabled=false;}};



function saveArenaDraft(){

 window.AgentArenaTabs?.saveDraft({prompt:$('prompt').value,preset:$('preset').value,provider:$('provider').value,model:$('model').value,reasoning:$('reasoning').value,timeout:$('timeout').value,mode:$('mode').value,individual,nextModels:{...nextModels},extraEntries:extraEntries.map(e=>({...e})),harnesses:selectedHarnesses()});

}

function restoreArenaDraft(){

 const draft=window.AgentArenaTabs?.loadDraft();if(!draft)return;

 for(const field of ['prompt','preset','provider','reasoning','timeout','mode'])if(typeof draft[field]==='string')$(field).value=draft[field];

 individual=!!draft.individual;nextModels={...(draft.nextModels||{})};extraEntries=(draft.extraEntries||[]).filter(e=>typeof e.id==='string'&&/^[a-z][a-z0-9-]{0,47}$/.test(e.id)&&Object.hasOwn(names,e.harness)&&!Object.hasOwn(names,e.id)).slice(0,13).filter((e,i,a)=>a.findIndex(x=>x.id===e.id)===i);customPrompt=$('prompt').value;

 $('individual-models').setAttribute('aria-pressed',String(individual));$('individual-models').textContent=individual?'Use shared model':'Individual models';

 connections(state);

 for(const box of document.querySelectorAll('input[name="harness"]'))box.checked=!box.disabled&&(draft.harnesses||[]).includes(box.value);

 connections(state);if([...$('model').options].some(o=>o.value===draft.model))$('model').value=draft.model;formHints();

}

$('run-form').addEventListener('input',saveArenaDraft);$('run-form').addEventListener('change',saveArenaDraft);

