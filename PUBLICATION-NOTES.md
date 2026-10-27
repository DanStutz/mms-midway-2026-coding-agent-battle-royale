# Publication cleanup

This is a source-only export prepared on October 26, 2026.

Included: the local Arena controller/UI, all nine adapters, metering, pricing
snapshots from public pages, isolated preview/session support, fixed challenge
tasks and verifiers, setup/login/build/start scripts and CLI study source.

Excluded: OAuth sign-in caches, API credentials, environment files, runtime state,
job configs, logs, transcripts, generated apps, historical results, validation
reports, presentations, archives, virtual environments, dependency caches and the
local rehearsal-import helper. Generic task fixtures and their synthetic Git author
address are included; they are not a person's contact details.

Sanitized: author-specific Windows paths, resource/project URLs, prefilled deployment
settings, assumptions that a machine is already signed in, and references to the
author's neighboring runtime. Private runtime data now defaults to an ignored
`.arena` folder inside the clone. Each user supplies their own connections.

The live source workspace and its private credentials are unchanged. Existing files
already present in the destination repository are preserved. This export does not
include `.git`, modify remotes, create commits, or push to GitHub.

Checks cover known credential patterns and private identifiers in the copied source,
syntax, provider defaults, clone-local data/auth paths and independent contestant
configuration. Review additional files and existing Git history separately. The
scanner does not validate that model output is safe or correct.

## Refresh verification — October 27, 2026

The latest working Arena UI was compared with this source copy. Light/dark mode,
saved browser theme preference, and Microsoft Foundry public Global Standard
price estimates are included. The UI code matches the working source; HTML keeps
blank resource/deployment fields and generic placeholders for public distribution.

The clone-local data/auth paths, standalone launchers, dependency declarations and
ignore rules from the original cleanup remain intact. No runtime data, sign-in
files, logs or private history were brought over. The reusable source scan found
no configured-pattern findings. This is a pattern-based check, not a guarantee
against every possible secret or a new audit of all Git history.

Existing repository edits and the separately added summary HTML were preserved.
Nothing was staged, committed or pushed by this refresh.
