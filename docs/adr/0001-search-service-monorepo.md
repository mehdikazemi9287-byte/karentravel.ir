# ADR-0001: karenseir-search stays in the monorepo (for now)

Status: Accepted
Date: 2026-09-11

## Context

`search-service/` was extracted from the monolith (`backend/app/main.py`) as an
independently deployable service (own Docker image `karenseir-search`, own
process, own port 8080/8090, own Postgres database `karenseir_search`, own
Python dependency set) using the strangler fig pattern. The monolith now
gateways to it via `/search/v3`, `/search/v3/public`, and
`/search/autocomplete/v3/public`, resolving tenant identity from the JWT and
passing only a minimal internal `SearchContext` (tenant slug + public flag) —
never raw claims or user records.

The service is already deployment-independent: it has its own Dockerfile,
requirements.txt, test suite, and can be built/deployed/rolled back without
touching the monolith image. The only thing not yet done is moving
`search-service/` into its own Git repository.

The current Phase 2 master prompt explicitly instructs: **do not split
`search-service/` into a separate Git repository in this phase** — document
the decision and the future trigger conditions instead.

## Decision

Keep `search-service/` inside the `karenseir-current` monorepo, as a sibling
directory to `backend/` and the Next.js `web` app, for now. Do not create a
separate `karenseir-search` Git repository yet.

Reasons:
- The service is young (Phase 1/2 of extraction, days old in production). Its
  contract with the monolith (`/internal/search/offer-pool`, `SearchContext`
  shape, failure taxonomy) is still being hardened and is easiest to change
  atomically when both sides are in one commit/one PR.
- A single engineer/small team currently owns both the monolith and the
  service; a repo split adds process overhead (cross-repo versioning, a
  package registry or git-submodule story, coordinated releases) with no
  present benefit — nobody outside this team consumes `search-service/`
  independently yet.
- Shadow-parity and rollback verification during this extraction relied on
  being able to `git diff`/`git log` both sides together; splitting now would
  lose that continuity for the remaining strangler work (frontend cutover,
  eventual retirement of the old monolith search code path).
- Deployment independence (the property that actually matters operationally)
  is already achieved via separate Docker images/containers/DB — a Git
  repository boundary is a separate, weaker-priority concern than a runtime
  boundary, and the runtime boundary is what was required first.

## Future triggers to re-evaluate (split when ANY of these becomes true)

1. **A second consumer appears.** Any other service, team, or repository
   needs to depend on `search-service/` independently of the monolith's
   release cadence (e.g. a mobile-only search proxy, a partner integration).
2. **Independent release cadence is needed.** The team wants to deploy
   `search-service/` changes more often than monolith changes (or vice
   versa) and the shared repo's CI/branch protection rules start actively
   blocking that (e.g. monolith CI failures blocking a search hotfix merge).
3. **Ownership diverges.** A different team or on-call rotation takes
   ownership of Search from the monolith team, making a shared repo's
   permission model (single set of reviewers/branch rules) a liability.
4. **Repo size/CI time becomes a measurable bottleneck** attributable to
   `search-service/`'s own history/tests/build inflating monorepo CI time
   past an agreed threshold.
5. **The internal contract stabilizes and hardens** to the point that changes
   to `/internal/search/offer-pool` or the `SearchContext` schema become rare
   and versioned (e.g. an explicit `v2` internal contract), reducing the need
   for atomic cross-boundary commits.
6. **Elasticsearch/OpenSearch (or another indexing backend) is adopted.** A
   genuinely separate scaling/ops profile (dedicated infra, dedicated
   on-call, heavier resource footprint) is a natural forcing function for a
   repo split, since it would already require independent infra tooling.

None of these conditions currently hold. Re-visit this ADR when one does.

## Consequences

- `search-service/` continues to be versioned, reviewed, and CI'd inside
  `karenseir-current`; its own `tests/` run as a scoped/targeted pytest job,
  not folded into the monolith's pytest run.
- Docker image builds, tags, and container lifecycles remain fully
  independent (already true today) — this ADR only concerns source control,
  not runtime architecture.
- No code changes result from this ADR; it is a documentation-only decision
  record satisfying the Phase 2 requirement to record the rationale rather
  than act on it.
