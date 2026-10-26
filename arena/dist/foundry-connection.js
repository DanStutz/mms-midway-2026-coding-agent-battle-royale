/* Keep the credential form usable independently of dashboard initialization. */
(function(){
 'use strict';
 const get=id=>document.getElementById(id),dialog=get('foundry-dialog');
 if(!dialog)return;
 function close(){get('foundry-key').value='';if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');}
 function open(){get('foundry-key').value='';get('foundry-status').textContent='';try{if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');}catch{dialog.setAttribute('open','');}get('foundry-key').focus();}
 get('connect-foundry').onclick=open;
 get('close-foundry').onclick=close;
 dialog.addEventListener('close',()=>{get('foundry-key').value='';});
 async function post(path,body){
  const stateResponse=await fetch('/api/state',{cache:'no-store'});
  if(!stateResponse.ok)throw new Error('Could not reach the local Arena runner.');
  const state=await stateResponse.json();
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Arena-Token':state.token},body:JSON.stringify(body)});
  let result;try{result=await response.json();}catch{throw new Error('The local runner returned an unreadable reply.');}
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Connection failed. Check the endpoint and key.');
  return result;
 }
 get('foundry-connect-form').onsubmit=async event=>{
  event.preventDefault();get('save-foundry').disabled=true;get('foundry-status').textContent='Checking Foundry model access...';
  try{
   const result=await post('/api/connections/foundry',{api_key:get('foundry-key').value,endpoint:get('foundry-endpoint').value,project_endpoint:get('foundry-project').value,deployments:get('foundry-deployments').value.split(/[,\n]/).map(x=>x.trim()).filter(Boolean)});
   get('foundry-key').value='';
   if(typeof window.AgentArenaFoundryConnected==='function'){
    try{await window.AgentArenaFoundryConnected(result);}catch{window.location.reload();}
   }else window.location.reload();
   close();
  }catch(error){get('foundry-status').textContent=error.message;}
  finally{get('save-foundry').disabled=false;}
 };
 get('disconnect-foundry').onclick=async()=>{
  try{await post('/api/connections/foundry/disconnect',{});get('foundry-key').value='';close();window.location.reload();}
  catch(error){get('foundry-status').textContent=error.message;}
 };
})();
