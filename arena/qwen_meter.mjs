/* Counter-only observation of pinned Qwen provider methods; native outputs unchanged. */
import {appendFileSync,readdirSync,readFileSync} from 'node:fs';
import {join,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
const root='/usr/local/lib/node_modules/@qwen-code/qwen-code/chunks';
let sequence=0;
function save(requestId,response,provenance){
 const u=response?.usageMetadata;if(!u)return;
 const p=provenance(u)||{};
 const entry={request_id:requestId,input_tokens:u.promptTokenCount,output_tokens:u.candidatesTokenCount,
  cache_tokens:u.cachedContentTokenCount||0,cache_write_tokens:p.cacheCreationInputTokens||0,aggregate:false};
 if([entry.input_tokens,entry.output_tokens,entry.cache_tokens,entry.cache_write_tokens].some(v=>!Number.isFinite(v)||v<0))return;
 try{appendFileSync('/logs/agent/arena-qwen-usage.jsonl',JSON.stringify(entry)+'\n');}catch{}
}
for(const [prefix,exportName]of [['anthropicContentGenerator-','AnthropicContentGenerator'],['openaiResponsesContentGenerator-','OpenAIResponsesContentGenerator']]){
 const filename=readdirSync(root).find(n=>n.startsWith(prefix)&&n.endsWith('.js'));
 if(!filename)throw new Error('Pinned Qwen provider module is missing. Rebuild Arena tools.');
 const path=join(root,filename),source=readFileSync(path,'utf8');
 const usageImport=source.match(/import\{[^}]*setGenAiUsageProvenance[^}]*\}from"([^"]+)"/);
 if(!usageImport)throw new Error('Pinned Qwen usage metadata module is missing.');
 const {getGenAiUsageProvenance}=await import(pathToFileURL(join(dirname(path),usageImport[1])));
 const provider=(await import(pathToFileURL(path)))[exportName];
 for(const method of ['generateContent','generateContentStream']){
  const native=provider.prototype[method];
  provider.prototype[method]=async function(...args){
   const requestId=String(process.pid)+':'+String(++sequence),result=await native.apply(this,args);
   if(method==='generateContent'){save(requestId,result,getGenAiUsageProvenance);return result;}
   return(async function*(){let last;try{for await(const event of result){if(event?.usageMetadata)last=event;yield event;}}finally{if(last)save(requestId,last,getGenAiUsageProvenance);}})();
  };
 }
}

// Keep tool-launched Node programs free of the runner's metering preload.
if(process.env.NODE_OPTIONS==='--import /tmp/arena-qwen-meter.mjs')delete process.env.NODE_OPTIONS;
