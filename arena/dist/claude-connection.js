/* Independent connection form remains usable if dashboard initialization fails. */
(()=>{
 const get=id=>document.getElementById(id),dialog=get('claude-dialog');
 const close=()=>{get('claude-key').value='';if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');};
 get('connect-claude').onclick=()=>{get('claude-key').value='';get('claude-connect-status').textContent='';if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');};
 get('close-claude').onclick=close;dialog.addEventListener('cancel',()=>{get('claude-key').value='';});
 async function request(path,body){
  const stateResponse=await fetch('/api/state');if(!stateResponse.ok)throw new Error('Could not reach the local Arena server.');const state=await stateResponse.json();
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Arena-Token':state.token},body:JSON.stringify(body)});const reply=await response.json();if(!response.ok)throw new Error(typeof reply.detail==='string'?reply.detail:'Claude connection failed.');return reply;
 }
 get('claude-connect-form').onsubmit=async event=>{event.preventDefault();get('save-claude').disabled=true;get('claude-connect-status').textContent='Listing models available through your Anthropic API key...';
  try{const reply=await request('/api/connections/anthropic',{api_key:get('claude-key').value});close();if(window.AgentArenaClaudeConnected)await window.AgentArenaClaudeConnected(reply);else window.location.reload();}
  catch(error){get('claude-connect-status').textContent=error.message;}finally{get('save-claude').disabled=false;}
 };
 get('disconnect-claude').onclick=async()=>{try{await request('/api/connections/anthropic/disconnect',{});close();window.location.reload();}catch(error){get('claude-connect-status').textContent=error.message;}};
})();
