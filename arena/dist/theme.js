/* Apply the saved theme before CSS paints; independent of Arena/API startup. */
(()=>{
 'use strict';
 const key='agent-arena-theme',root=document.documentElement;
 function apply(value){
  const theme=value==='light'?'light':'dark';root.dataset.theme=theme;
  const button=document.getElementById('theme-toggle');
  if(button){button.textContent=theme==='dark'?'Light mode':'Dark mode';button.setAttribute('aria-label','Switch to '+(theme==='dark'?'light':'dark')+' mode');button.setAttribute('aria-pressed',String(theme==='light'));}
 }
 let saved=null;try{saved=localStorage.getItem(key);}catch{}
 apply(saved);
 function bind(){
  const button=document.getElementById('theme-toggle');if(!button)return;
  apply(root.dataset.theme);
  button.addEventListener('click',()=>{const next=root.dataset.theme==='light'?'dark':'light';apply(next);try{localStorage.setItem(key,next);}catch{}});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind,{once:true});else bind();
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null)apply(event.newValue);});
})();
