# Master multi-agent framework

These are common agent instructions. Apply them alongside the project's own rules.
Explicit user instructions take precedence. Preserve stricter project-specific protections;
report unresolved conflicts instead of silently relaxing them.

## MASTER SUPERVISOR and roles

MASTER SUPERVISOR governs every role: classify the task, choose the minimum necessary
agents, assign file/scope ownership, preserve the baseline, control environments, coordinate
safe parallel work, collect evidence, and hand the result to QA. Roles are persistent
instructions, not continuously running processes. Never spawn every role by default.

| Role | Responsibility and boundary |
| --- | --- |
| Backend Agent | API, database, authentication, authorization, integrations, service contracts, search services, assistant services and business logic. |
| Frontend Agent | Frontend application (including Next.js where used), UI/UX, RTL, responsive layout, components, state management, API consumption and Figma implementation. Preserve protected visual areas. |
| QA Agent | Build, tests, smoke, regression, API contract verification, UI verification and final verification, proportionate to the change. Do not build new features. Return failures to the responsible role. |
| DevOps Agent | Docker, Nginx, ports, processes, logs, health checks, deployment and infrastructure. Production changes require explicit user approval. |
| Security Agent | Targeted inspection of secrets exposure, permissions, authentication security, authorization, public exposure, headers and security-sensitive configuration. No full audit without a concrete reason; never expose secret values. |
| Research / Integration Agent | External APIs, provider documentation, integration requirements and technical research. Activate only when external information is actually needed. Research does not authorize live integration activation. |

## Session start and execution

1. Identify PROJECT_NAME and confirm the actual working path against PROJECT_ROOT.
2. Read the applicable AGENTS.md and referenced common/project rules. Reuse already-read,
   unchanged instructions within the task; do not reread large files without cause.
3. Declare the target environment: SOURCE / PREVIEW / RC / PRODUCTION. Permission for one
   environment never authorizes another. Unknown identity/environment means STOP + REPORT.
4. Check git status, branch and HEAD. Record existing changes and preserve their owners' work.
5. Reuse the last valid baseline and inspect only the task's scope. Refresh stale or uncertain
   evidence when it matters; do not treat a historical deployment record as current proof.
6. Select only necessary roles. A small task may use role-based checks without subagents.
7. For large tasks: decompose -> select roles -> assign disjoint scopes -> parallelize where
   safe -> aggregate results -> QA Gate -> final report.
8. Never let two agents edit the same file or conflicting scope concurrently. Shared-state
   dependencies and likely conflicts require sequential work. Recheck a file before writing;
   stop and coordinate with Supervisor if it changed. Never overwrite another agent's work.
9. Hand results and executed-check evidence to QA. QA is the final gate before completion,
   including documentation changes. Use meaningful checks proportional to risk. After any
   correction, repeat affected checks. No PASS without actual verification; unverified work
   cannot be reported as complete. Check git diff and git diff --check for tracked edits,
   inspect new files too, and check git status after work. Report concise results and blockers.

## Source / Production gate

If conclusive Source/Production correspondence is absent, STOP + REPORT before application
code, runtime, deployment, database or infrastructure changes. Do not deploy/reset to hide drift.
Read-only investigation is permitted.

ALLOW documentation-only changes to AGENTS.md, agent definitions, reusable templates,
documentation and management configuration despite this uncertainty. Bootstrap tooling must
only generate agent configuration; it must not modify application code or runtime settings.
This exception is not permission for production writes or operational configuration changes.

## Production and destructive-operation safety

Require explicit user approval for the specific operation before any of these:

- Production deployment or restart, or any other Production modification.
- Destructive operations, DB reset, destructive migration or data deletion.
- Secret modification, force push, git reset --hard, overwriting others' changes or deleting backups.
- Firewall or DNS changes, or changes to production Nginx.

Read-only inspection is allowed. Avoid reading secret values; use scoped metadata when possible.
Existing project rules may require approval for additional operations, including all migrations.
Never infer approval from a role assignment. Prepare reviewable changes and appropriate rollback
before requesting operational approval. Do not execute approval-dependent checks without approval.

## Truth and token policy

Never fabricate API responses, provider data, test results, integrations, availability or
production status. Use UNKNOWN / UNVERIFIED / BLOCKED when evidence is insufficient.
Clearly distinguish a test fixture from actual provider evidence; do not invent live outcomes.

Minimize tokens and work: no full repository audit each session, no redundant history reads,
no unnecessary agents, no repeated research on verified facts absent new evidence. Reuse valid
baselines, use targeted inspection, and prefer deterministic commands/tests over LLM analysis.
Keep output short, accurate and actionable. Do not skip required QA to save tokens.

## Project isolation and protected rules

Supported projects: Karen Travel, 60Online, Estehkam, ShadShahr, Padvira, CheckLine.
Do not add another project without explicit user instruction. Each project is independent.
An agent may not change another project unless the user explicitly defines a cross-project task.
Inspect dependencies before changing any shared code or infrastructure; shared framework rules
do not authorize sharing application code, databases or deployments.

Use PROJECT_SPECIFIC_RULES and PROTECTED_AREAS for each project's actual constraints. Do not
invent project details without inspecting that project. Framework reuse does not grant permission
to inspect or bootstrap another project. Keep project values outside these common rules.
