# Agent Arena

Compare coding-agent harnesses and models through a local web dashboard. Give every
contestant the same prompt and inspect its app preview, activity, source, elapsed
time, token usage and estimated USD value.

- Nine harnesses: Codex CLI, OpenCode, Pi, Aider, Goose, Cline CLI, mini-SWE-agent,
  OpenHands SDK and Qwen Code.
- Shared-model comparisons or a separate model on each tile.
- Repeat any harness with multiple models, such as three Aider instances side by side.
- Up to 14 contestants per comparison, with independent workspaces and previews.
- Multiple arena tabs for independent prompts, with shared local connections.
- OpenAI and Anthropic API connections; separate Microsoft Foundry configuration.
- Run history, downloadable results, cost CSV and presentation mode.
- Light/dark mode toggle with a saved browser preference shared across arena tabs.

## Quick start on Windows

Install Python 3.12 or newer and Docker Desktop. Start Docker Desktop using Linux
containers. Open PowerShell in this repository folder, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP.ps1
powershell -ExecutionPolicy Bypass -File .\PREPARE-ARENA.ps1
powershell -ExecutionPolicy Bypass -File .\START-ARENA.ps1
```

Open [Agent Arena](http://127.0.0.1:8090). The tools-image build can take several
minutes and download several GB; do it before a live presentation. Later starts
only need Docker Desktop and `START-ARENA.ps1`. The supplied launchers target Windows;
other host platforms have not been validated by this cleaned export.

Click **Connect OpenAI API** or **Connect Claude API** and enter your own key in the
local form. API usage requires the provider's credits and is billed separately from
ChatGPT or Claude subscriptions. Keys stay in server memory and clear on restart.
No API key, saved sign-in, or private endpoint is included in this copy.

For Foundry, click **Connect Foundry** and enter your own resource inference URL,
optional project URL, resource key and actual deployment names. Generic placeholders
are shown; a model catalog entry alone does not prove a deployment exists. Azure
USD uses Microsoft public Global Standard short-context list-price estimates for
supported GPT-5.6/GPT-6 models. Custom aliases use the underlying model entered with
the deployment name. Estimates include reported cache reads/writes; missing cache-write
counts are valued as ordinary input. Agreement discounts, temporary promotions,
regional/Data Zone premiums, long-context uplifts and other deployment modes are
excluded. Unknown models or missing usage remain unpriced. Check Rates and calculation
and Cost CSV for model, source, verification date and assumptions.

Select contestants, choose a model, enter a prompt, and **Start comparison**.

## Compare three models with Aider

1. Select **Aider** and deselect other harnesses.
2. Click **+ Add instance** twice on its tile.
3. Choose a different model on Aider 1, Aider 2 and Aider 3.
4. Select **Live race / together** and start the comparison.

Each entry has separate output, preview, token counts and estimated USD. Added
copies can be removed from the next comparison. The same model can also be repeated.
Claude is available to eight harnesses; Codex CLI uses OpenAI models. Available
models depend on your connections and each harness's compatibility. Providers may
reject a listed model because of credits, quota or unsupported features.

Use **New arena** for another prompt. A bare `/` URL creates a new arena; its named
`?arena=...` URL reopens it. Closing a tab does not stop a comparison. Shared capacity
is 14 active agents across all tabs; other workers wait without using their timer.

## Optional native ChatGPT sign-ins

OpenAI/Claude API connections are the simplest setup for API-backed harnesses.
Codex, OpenCode and Pi also support their native ChatGPT sign-ins. For these,
install Node.js 22 or newer. For Codex install the pinned CLI first:

```powershell
npm install -g @openai/codex@0.163.0
.\LOGIN.ps1 -Harness codex
.\LOGIN.ps1 -Harness opencode
.\LOGIN.ps1 -Harness pi
```

Use your own authorized account/workspace. OpenCode and Pi install pinned local
host tools under the ignored `.arena` directory. Codex uses its normal local auth
cache. Each tool has its own login; signing into this dashboard does not sign it in.

## Data and configuration

Private runtime data defaults to `.arena/` in this clone: state, arena metadata,
auth caches, logs, snapshots, job configs, jobs and model-generated artifacts. The
folder is ignored by Git. Optional environment variables:

- `ARENA_DATA_DIR`: another private data directory. Native login and server must
  use the same value. Keep external data directories outside public Git tracking.
- `ARENA_PORT`: controller port; `START-ARENA.ps1 -Port 8090` sets it for you.
- `ARENA_MAX_AGENTS`: shared active-agent capacity, from 1 through 64.
- `SHOWDOWN_JOBS_DIR`: job location for the optional historical CLI study only.

The three fixed tasks can run browser correctness checks. Custom prompts are
ungraded. OpenHands uses the Software Agent SDK rather than its separate web app.
Versions are pinned in `arena/Dockerfile.tools` for reproducible installation.

USD values are estimates, not invoices. Missing counters and unknown rates remain
unknown. Claude rates can be refreshed from its public pricing page; each race
keeps its rate snapshot. Parallel runs share CPU, memory and API quotas. Use repeated
sequential trials before making performance claims about models or harnesses.

## Before publishing changes

Run the dependency-free scanner from this folder:

```powershell
python tools/check-public.py
```

It reports file names and line numbers, never matched secret values. It checks known
credential patterns, private keys, user-specific absolute paths and filled Azure
resource URLs in source. Automated scanning is not proof that no secret exists.
Review your Git diff and newly added files before every push. Keep sign-in caches,
`.env` files, logs, generated apps/results, archives and runtime environments private.
If a real credential was previously published, deleting it from a new copy does not
invalidate it; rotate it through the provider and assess the existing Git history.
See [GitHub's removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

This controller runs local coding tools and generated apps. It binds to loopback;
do not expose it as a public service. The source cleanup does not certify arbitrary
model-generated files or pre-existing repository history as safe to publish.

The original three-harness CLI study is also included in `run.ps1` and `showdown.py`.
Historical results, slide decks, local validation evidence and rehearsal imports
are excluded from this public source copy. See `PUBLICATION-NOTES.md` for scope.
