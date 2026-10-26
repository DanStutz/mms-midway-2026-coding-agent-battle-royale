/* Each bare URL opens a fresh arena; named URLs can reopen a running arena. */
(()=>{
 const $=id=>document.getElementById(id);let id=null,token='';
 async function request(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Arena-Token':token}:{},body:body?JSON.stringify(body):undefined});let data;try{data=await response.json();}catch{throw new Error('Could not read the Arena server response.');}if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Could not open this arena.');return data;}
 const tabs={
  get id(){return id;},
  scope(path){return id&&(/^\/api\/state(?:\?|$)/.test(path)||/^\/api\/runs(?:\/|\?|$)/.test(path))?path+(path.includes('?')?'&':'?')+'arena_id='+encodeURIComponent(id):path;},
  sync(state){
   token=state.token||token;const arena=state.arena;if(!arena)return;
   if(document.activeElement!==$('arena-name'))$('arena-name').value=arena.name;
   document.title=arena.name+' · Agent Arena';
   const select=$('arena-switch');select.replaceChildren();
   for(const item of state.arenas||[]){const option=document.createElement('option');option.value=item.id;option.textContent=item.name+(item.active_id?' / running':'');select.append(option);}select.value=id;
   const n=state.other_active_arenas||0;$('arena-concurrency').textContent=n?`${n} other arena${n===1?'':'s'} running · shared machine and API limits`:'Ready for another prompt in a new arena';
  },
  saveDraft(draft){if(id)try{sessionStorage.setItem('agent-arena-draft:'+id,JSON.stringify(draft));}catch{}},
  loadDraft(){if(id)try{return JSON.parse(sessionStorage.getItem('agent-arena-draft:'+id)||'null');}catch{}return null;}
 };
 window.AgentArenaTabs=tabs;$('start').disabled=true;
 tabs.ready=(async()=>{
  const url=new URL(window.location.href),requested=url.searchParams.get('arena');
  if(requested&&!/^(main|[a-f0-9]{12})$/.test(requested))throw new Error('Invalid arena URL. Use New arena to create another tab.');
  const initial=await request('/api/state'+(requested?'?arena_id='+requested:''));token=initial.token;
  if(requested)id=requested;
  else{const arena=await request('/api/arenas',{});id=arena.id;url.searchParams.set('arena',id);window.history.replaceState(null,'',url.pathname+url.search+url.hash);}
  return id;
 })();
 $('arena-switch').onchange=()=>{window.location.href='/?arena='+encodeURIComponent($('arena-switch').value);};
 $('arena-name').onchange=async()=>{try{const reply=await request('/api/arenas/'+id+'/rename',{name:$('arena-name').value});document.title=reply.name+' · Agent Arena';}catch(error){$('message').hidden=false;$('message').textContent=error.message;}};
 tabs.ready.then(()=>setInterval(async()=>{try{tabs.sync(await request(tabs.scope('/api/state')));}catch{}},10000)).catch(()=>{});
})();
