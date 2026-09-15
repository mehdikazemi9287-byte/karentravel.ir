# Bootstrap another project's agent configuration

`MASTER_RULES.md` is the common source of truth. `AGENTS.template.md` holds only the seven
project fields and the common-rules insertion point. Karen Travel's root AGENTS.md references
the master; rendered configurations embed a snapshot so other projects have no runtime or
filesystem dependency on Karen Travel. Future updates require a reviewed regeneration/merge,
not automatic synchronization across projects.

Supported: Karen Travel, 60Online, Estehkam, ShadShahr, Padvira, CheckLine.
Only bootstrap a different project after explicit user authorization for that project.
Definitions describe Codex roles; they do not start persistent agents or install global settings.

## Seven inputs

Create a UTF-8 JSON file with exactly these keys, each a non-empty string:

- PROJECT_NAME: one supported project name.
- PROJECT_ROOT: verified absolute project path.
- SERVER: verified server identity, or UNKNOWN if not established.
- PRODUCTION_PATH: verified deployment path, or UNKNOWN; never guess.
- SERVICES: confirmed service inventory as text, or UNKNOWN.
- PROTECTED_AREAS: project-confirmed protected areas, or UNKNOWN.
- PROJECT_SPECIFIC_RULES: confirmed project rules, or UNKNOWN.

Multiline strings are supported. Do not place secrets in these inputs. UNKNOWN does not pass
an operational gate; verify relevant values before application/runtime/infrastructure work.
No project paths, services or detailed protected rules are prefilled or invented.

## Render and review

From the framework's parent directory, supply your actual non-secret variables file:

```sh
python3 agent-framework/bootstrap.py /path/to/project-variables.json
```

The tool only writes the generated document to stdout. It does not connect to SERVER, inspect
PROJECT_ROOT, install files, touch a repository, modify services or deploy. To save a candidate,
use a fresh staging directory (never redirect directly over an existing AGENTS.md):

```sh
agent_stage_dir=$(mktemp -d /tmp/agent-framework.XXXXXX)
python3 agent-framework/bootstrap.py /path/to/project-variables.json > "$agent_stage_dir/AGENTS.md"
```

Check the command's exit status; discard an empty candidate from a failed render. QA must review
the seven values, local protected rules and common rules. In the explicitly authorized target
project, check Git status/branch/HEAD first. If AGENTS.md exists, read it and prepare an additive,
reviewed merge preserving valid content and existing work; never replace it wholesale. If absent,
install the reviewed candidate with an exclusive-create operation that fails if the file exists.
Then inspect the actual diff/new file, run git diff --check, check git status, and pass QA before
completion. Commit only under that project's user authorization. Never auto-push or auto-deploy.
