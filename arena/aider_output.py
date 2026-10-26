"""Parse only Aider's visible edit and usage summaries."""
import re

def summary(text):
 text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
 text=re.sub(r'<think>.*?</think>','',text,flags=re.S|re.I)
 visible=[line.strip()[:240] for line in text.splitlines() if re.match(r'^(Applied edit|Wrote |Added |Tokens:|Cost:|Commit |Aider v|Main model:|Weak model:)',line.strip())]
 return visible[-18:]

def failure_reason(text):
 lower=' '.join(text.lower().split())
 if any(marker in lower for marker in ['no credits remaining','insufficient_quota','exceeded your current quota','billing_hard_limit_reached']):return 'api_no_credits','OpenAI reports no API credits remaining. Add credits to this API project, then start a new Aider attempt. ChatGPT subscription usage is separate.'
 if 'ratelimiterror' in lower:return 'api_rate_limited','OpenAI rate-limited the Aider request. Check API limits and try a new attempt later.'
 if 'authenticationerror' in lower or 'invalid_api_key' in lower:return 'api_authentication','OpenAI rejected the Aider API credential. Reconnect Aider with a valid key.'
 if 'badrequesterror' in lower or 'model_not_found' in lower:return 'api_model_rejected','OpenAI rejected Aider’s model request. Check the selected model and API project access.'
 if 'permissiondeniederror' in lower:return 'api_permission','The API project does not permit this Aider request. Check model permissions.'
 return None,None

