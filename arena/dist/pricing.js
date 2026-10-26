/* Official OpenAI Standard short-context text rates, USD per 1M tokens. */

(function(global){

const verified='2026-10-20';

const rates={

 'gpt-6-sol':{input:2,cached:.2,output:10},

 'gpt-6.1-sol':{input:2,cached:.1,output:10},

 'gpt-6-luna':{input:.1,cached:.01,output:.5},

 'gpt-5.6-sol':{input:4,cached:.4,output:20},

 'gpt-5.6-terra':{input:2,cached:.2,output:12},

 'gpt-5.6-luna':{input:.2,cached:.02,output:1.2}

};

const assumptions='Standard short-context API rates; cache-write premiums, long-context uplifts, regional charges, taxes, and tool fees excluded. Subscription values are API equivalents, not invoices. Cached tokens are included in input and counted once. Output includes any reported reasoning tokens.';

let anthropic={rates:{},verified:'',source:'https://claude.com/pricing#api'};

function setAnthropicRates(snapshot){if(snapshot?.rates){anthropic=snapshot;Object.assign(rates,snapshot.rates);}}

function claudeRate(model,snapshot){const key=model.replace(/-\d{8}$/,'');return (snapshot||anthropic).rates[key];}

function estimateClaude(model,metrics,snapshot){

 const data=snapshot||anthropic,rate=claudeRate(model,data),m=metrics||{};

 const base={rate,verified:data.verified,source:data.source,note:data.assumptions};

 if(!rate)return {...base,usd:null,note:'No published Anthropic rate found for this exact model.'};

 const calls=m.token_usage_calls;

 if(!Array.isArray(calls)||!calls.length)return {...base,usd:null,note:'Awaiting reconciled Claude input, output and cache usage.'};

 let usd=0;const parts={uncached_input:0,cached_input:0,cache_write:0,output:0};

 for(const c of calls){

  const {input_tokens:input,output_tokens:output,cache_tokens:cached,cache_write_tokens:write}=c;

  if([input,output,cached,write].some(v=>!Number.isFinite(v)||v<0)||cached+write>input)return {...base,usd:null,note:'Claude token counters cannot be reconciled.'};

  if(rate.threshold&&c.aggregate&&input>rate.threshold)return {...base,usd:null,note:'Per-request usage is required to apply this Claude model’s context pricing tiers.'};

  const r=rate.threshold&&input>rate.threshold?rate.above:rate;

  parts.uncached_input+=(input-cached-write)*r.input/1e6;parts.cached_input+=cached*r.cached/1e6;parts.cache_write+=write*r.write/1e6;parts.output+=output*r.output/1e6;

 }

 usd=Object.values(parts).reduce((a,b)=>a+b,0);return {...base,usd,parts,cache_known:true};

}

function estimate(model,metrics,provider){

 if(provider==='foundry')return {usd:null,note:'Microsoft Foundry deployment rates are not configured. Region, deployment type and Azure pricing may differ; token usage is still recorded.',verified:''};

 if(provider==='anthropic')return estimateClaude(model,metrics,arguments[3]);

 const rate=rates[model];if(!rate)return {usd:null,note:'No verified rate for this model.',verified};

 const m=metrics||{},input=m.input_tokens,output=m.output_tokens,knownCache=m.cache_tokens!=null,cached=knownCache?m.cache_tokens:0;

 if(!Number.isFinite(input)||!Number.isFinite(output))return {usd:null,note:'Awaiting reported token usage.',verified,rate};

 if(input<0||output<0||!Number.isFinite(cached)||cached<0||cached>input)return {usd:null,note:'Token counters cannot be reconciled.',verified,rate};

 const parts={uncached_input:(input-cached)*rate.input/1e6,cached_input:cached*rate.cached/1e6,output:output*rate.output/1e6};

 return {usd:parts.uncached_input+parts.cached_input+parts.output,parts,rate,verified,cache_known:knownCache,note:(knownCache?'':'Cache count unavailable; input valued as uncached. ')+assumptions};

}

function money(value){if(value==null||!Number.isFinite(value))return '--';return '$'+value.toFixed(value>0&&value<.01?6:4);}

function rows(run){return run.harnesses.map(h=>{const item=run.contestants[h],m=item.metrics||{},model=item.model||run.models?.[h]||run.model,provider=item.provider||run.provider||'default',cost=estimate(model,m,provider,run.anthropic_pricing);return {run_id:run.id,contestant_id:h,contestant_label:item.label||item.harness||h,harness:item.harness||h,provider,endpoint:run.endpoint||'',model,status:item.status,input_tokens:m.input_tokens??'',cached_input_tokens:m.cache_tokens??'',output_tokens:m.output_tokens??'',estimated_usd:cost.usd??'',cost_basis:provider==='foundry'?'Azure deployment rate not configured':(provider==='anthropic'||provider==='openai'||['aider','goose','cline','mini-swe-agent','openhands','qwen'].includes(item.harness||h))?'API token estimate':'API-equivalent token value',actual_invoice_usd:'',rates_verified:cost.verified??verified,input_usd_per_million:cost.rate?.input??'',cached_usd_per_million:cost.rate?.cached??'',output_usd_per_million:cost.rate?.output??'',cache_write_tokens:m.cache_write_tokens??'',cache_write_usd_per_million:cost.rate?.write??'',source:provider==='anthropic'?(run.anthropic_pricing?.source||anthropic.source):provider==='foundry'?'https://azure.microsoft.com/pricing/details/ai-foundry-models/':'https://developers.openai.com/api/docs/models/'+model,assumptions:cost.note};});}

function csv(run){const data=rows(run),keys=Object.keys(data[0]||{});const quote=v=>'"'+String(v).replaceAll('"','""')+'"';return [keys.map(quote).join(','),...data.map(row=>keys.map(k=>quote(row[k])).join(','))].join('\r\n');}

global.AgentArenaPricing={rates,verified,assumptions,estimate,money,rows,csv,setAnthropicRates,claudeRate};

})(typeof window==='undefined'?globalThis:window);

