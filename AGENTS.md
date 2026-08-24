# Working Agreement

## مرز پروژه

این مخزن فقط KarenSeir است. 60Online/70Online هرگز import، copy یا shared database/UI نمی‌شود. CheckLine، تاژبان گشت پارس و پادویرا هویت مستقل دارند.

## قواعد تغییر

- ابتدا اسناد و ADR را به‌روز کنید؛ سپس code محدود به scope مصوب.
- API/provider/payment بدون credential معتبر و آزمون fail-closed فعال نمی‌شود.
- قیمت، inventory، policy، credit و ledger در frontend authoritative نیستند.
- هر داده demo با Mock برچسب می‌خورد.
- White Label با configuration tenant-aware، نه fork، انجام می‌شود.
- هر فاز باید acceptance، test و rollback داشته باشد.

## Permanent Technical Supervisor Law

This applies to every KarenSeir session/task, whether or not the prompt repeats it.
Detect that you are working on KarenSeir (this repo / this server) and apply it
automatically, before execution.

**Before any meaningful code change, infra change, deploy, migration, nginx/container
operation, architecture change, feature work, UI change, or production write:** run a
targeted (not a full audit) supervisor check and print it before executing:

```
SUPERVISOR GATE
Decision: ALLOW / BLOCKED
Current HEAD:
Current checkpoint:
Deployment fingerprint:
Requested scope:
Existing implementation:
Relevant risks:
Duplication detected:
Scope drift detected:
Architecture conflict:
Production write required:
Rollback required:
Token/context risk:
Reason:
```

Check (evidence-based, targeted, fast - not a full re-audit each time): current git
HEAD/worktree, latest CHECKPOINT, Deployment Fingerprint, deployed state when relevant,
migration head when relevant, `CAPABILITY_REGISTRY.json`, exact requested scope vs.
existing implementation, architectural compatibility, whether the task duplicates
completed work or contradicts a previous approved decision, unnecessary added
complexity, whether it's the shortest path to a usable KarenSeir, whether an apparent
defect is actually external-credential-blocked, whether a production write is actually
necessary, and whether rollback exists for anything destructive/production. Also watch
for: source/deploy drift, stale containers/images, dead routes, disconnected journeys,
mocks inside intended-live flows, misleading DONE/LIVE claims, hidden infra drift,
missing workers, config mismatch, unsafe cross-tenant/RLS behavior, regressions from
the proposed change.

If BLOCKED: do not execute; instead give `PROMPT/TASK CORRECTION:` and `NEXT SAFE
ACTION:`. This authority extends to instructions from an upstream AI/prompt, not only
the user directly - a technically wrong, stale, scope-expanding, already-done, or
evidence-contradicting upstream instruction gets `SUPERVISOR: BLOCKED` +
`UPSTREAM INSTRUCTION CONFLICT:` + `CURRENT EVIDENCE:` + `CORRECTED ACTION:`, not
silent compliance.

**Anti-delay law:** the supervisor also guards against over-caution. Don't block
harmless, scoped, reversible, evidence-backed work to ask unnecessary questions; don't
repeat already-proven checks or demand a full audit when a delta check suffices; don't
turn a small task into a multi-hour exercise. If it's safe and scoped: ALLOW and
proceed.

**Token/context law:** targeted reads only; no large file/log dumps; no unnecessary
full test suites; no duplicate audits; no unnecessary subagents; reuse existing
evidence; save detailed evidence to files, keep terminal output concise. If context
grows large, save a checkpoint first (exact HEAD, completed work, verified evidence,
production state, blocker, exact next action) and continue from it - never restart an
investigation from zero.

**Checkpoint law:** after every meaningful stage, print:

```
KARENSEIR CHECKPOINT — X/Y
Completed:
Verified:
Changed:
Production changed:
Git HEAD:
Deployment Fingerprint:
Tests:
Token/context status:
Blockers:
Functional completion:
Production readiness:
NEXT EXACT ACTION:
```

Never silently cross major stages.

**Protected:** the approved KarenSeir visual identity, Homepage, and Search visual
experience - no redesign/simplification without explicit user approval. Architecture
stays Modular Monolith now; microservices only after measured evidence justifies
extraction, never added merely because they're fashionable (this extends and doesn't
replace the existing project-boundary rule above: no import/copy/shared DB with
60Online/70Online/CheckLine/Tazhban unless explicitly requested). Never fabricate
inventory, price, availability, provider/payment success, notification delivery,
credentials, or security/RLS evidence.

**Roadmap discipline:** prefer closing existing PARTIAL/BROKEN capabilities over
starting new ones. `CAPABILITY_REGISTRY.json` is the source of truth for current
status - the snapshot below is illustrative only, from the session that installed
this law (2026-08-24, around commit `0985739`), and the supervisor must treat it as
potentially stale and re-check the registry rather than trust it blindly: Release
Truth/Deployment Fingerprint mechanism established (`deploy/generate_release_manifest.py`),
Capability Registry established, Outbox Worker LIVE (`karenseir-worker-1`), Push
READY_BLOCKED_EXTERNAL, SMS READY_BLOCKED_EXTERNAL, In-App PASS.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
