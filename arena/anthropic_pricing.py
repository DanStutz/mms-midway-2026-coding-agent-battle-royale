"""Fetch a credential-free snapshot from Anthropic's public API pricing page."""
import json,re,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone
from pathlib import Path
SOURCE='https://claude.com/pricing#api'
SNAPSHOT=Path(__file__).parent/'dist/claude-rates.json'
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style'):self.skip+=1
  if tag=='h3':self.parts.append('\nMODEL:')
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.skip=max(0,self.skip-1)
 def handle_data(self,data):
  if not self.skip:self.parts.append(data+' ')

def parse(html):
 parser=Text();parser.feed(html);text=''.join(parser.parts);rates={}
 for section in text.split('MODEL:')[1:]:
  name=re.match(r'\s*(Fable|Opus|Sonnet|Haiku|Mythos)\s+(\d+(?:\.\d+)?)\b',section)
  if not name:continue
  # Stop at the next heading/feature; only accept the standard four token rates.
  prices=[float(n.replace(',','')) for n in re.findall(r'\$\s*([\d,]+(?:\.\d+)?)\s*/\s*M[Tt]ok',section)]
  if len(prices)<4:continue
  model='claude-'+name[1].lower()+'-'+name[2].replace('.','-')
  if model=='claude-haiku-5-5':
   if len(prices)<8:continue
   rates[model]={'cached':prices[0],'write':prices[1],'input':prices[4],'output':prices[6],
    'threshold':100000,'above':{'cached':prices[2],'write':prices[3],'input':prices[5],'output':prices[7]}}
  else:rates[model]={'cached':prices[0],'write':prices[1],'input':prices[2],'output':prices[3]}
 if len(rates)<4 or any(not 0<r['input']<=100 or not 0<r['output']<=500 or not 0<r['cached']<=r['input'] or not r['input']<=r['write']<=r['input']*3 for r in rates.values()):raise ValueError('Anthropic pricing page format changed; the last verified snapshot was kept.')
 return {'source':SOURCE,'verified':datetime.now(timezone.utc).date().isoformat(),'rates':rates,'assumptions':'Standard global API token rates; 5-minute cache writes. Unknown cache TTL is valued at 5 minutes. Taxes, tool fees, fast mode and US-only premiums excluded. Estimates are not invoices.'}

def load():
 try:return json.loads(SNAPSHOT.read_text(encoding='utf-8'))
 except (ValueError,OSError):return {'source':SOURCE,'verified':'','rates':{}}

def refresh():
 try:
  request=urllib.request.Request(SOURCE.split('#')[0],headers={'User-Agent':'Agent-Arena/1.0','Accept':'text/html'})
  with urllib.request.urlopen(request,timeout=20) as response:html=response.read(5000000).decode('utf-8')
  snapshot=parse(html)
 except ValueError:raise
 except Exception:raise ValueError('Could not refresh Anthropic pricing; the last verified snapshot was kept.') from None
 temp=SNAPSHOT.with_suffix('.tmp');temp.write_text(json.dumps(snapshot,indent=2),encoding='utf-8');temp.replace(SNAPSHOT)
 return snapshot
if __name__=='__main__':
 result=refresh();print('Verified',len(result['rates']),'Claude model rates from',result['source'],'on',result['verified']);print(json.dumps(result['rates']))
