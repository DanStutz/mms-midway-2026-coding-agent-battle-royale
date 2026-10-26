"""Agent choices and setup metadata for the local Arena."""
EXTRA={
 'aider':('ShowdownAider','openai','0.86.2'),
 'goose':('ShowdownGoose','openai','1.52.0'),
 'cline':('ShowdownCline','openai-native','3.0.73'),
 'mini-swe-agent':('ShowdownMiniSwe','openai','2.4.6'),
 'openhands':('ShowdownOpenHands','openai','1.58.2'),
 'qwen':('ShowdownQwen','openai','0.26.1')
}
API_HARNESSES=set(EXTRA)
CATALOG={
 'codex':{'name':'Codex CLI','description':'OpenAI coding agent','auth':'subscription','color':'#83bcff'},
 'opencode':{'name':'OpenCode','description':'Configurable coding tools and context','auth':'subscription','color':'#eab886'},
 'pi':{'name':'Pi','description':'Small core toolbox','auth':'subscription','color':'#b8a2ef'},
 'aider':{'name':'Aider','description':'Git-aware file editing','auth':'api','color':'#f2d177'},
 'goose':{'name':'Goose','description':'Developer tools and task automation','auth':'api','color':'#82d4bc'},
 'cline':{'name':'Cline CLI','description':'Plan/act coding workflow','auth':'api','color':'#efa3b9'},
 'openhands':{'name':'OpenHands SDK','description':'Software agent with terminal, file editor and task tracking','auth':'api','color':'#f5a56b'},
 'qwen':{'name':'Qwen Code','description':'Provider-configurable terminal coding agent','auth':'api','color':'#a9d878'},
 'mini-swe-agent':{'name':'mini-SWE-agent','description':'Minimal shell-based coding agent','auth':'api','color':'#93d3e5'}
}
