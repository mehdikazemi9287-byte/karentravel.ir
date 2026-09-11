"""Provider registry: the single place providers are wired up.

The orchestrator/fan-out never branches on provider identity (no
if/elif-per-provider). It asks the registry which providers are eligible for
a vertical (registered, enabled, and declaring that vertical) and iterates
them in a deterministic priority order. Adding a real external carrier later
is a one-line `REGISTRY.register(...)` call -- no fan-out code changes.

Kept deliberately small: one dataclass, one class, no inheritance hierarchy."""
from __future__ import annotations

from dataclasses import dataclass

from .providers import EXTERNAL_PROVIDERS, SearchProviderPort, _POOL


@dataclass(frozen=True)
class ProviderRegistration:
    provider: SearchProviderPort
    enabled: bool = True
    priority: int = 0   # lower runs/lists first; ordering is deterministic, not insertion-order-fragile


class ProviderRegistry:
    def __init__(self) -> None:
        self._registrations: list[ProviderRegistration] = []

    def register(self, provider: SearchProviderPort, *, enabled: bool = True, priority: int = 0) -> None:
        self._registrations.append(ProviderRegistration(provider, enabled, priority))

    def all(self) -> list[SearchProviderPort]:
        return [r.provider for r in sorted(self._registrations, key=lambda r: r.priority) if r.enabled]

    def for_vertical(self, vertical: str) -> list[SearchProviderPort]:
        return [p for p in self.all() if not p.verticals or vertical in p.verticals]

    def capability_matrix(self) -> list[dict]:
        out = []
        for p in self.all():
            status = p.status()
            regions = getattr(p, "regions", ("*",))
            out.append({
                "provider": p.key,
                "verticals": list(p.verticals) if p.verticals else ["*"],
                "regions": list(regions) if regions else ["*"],
                "priority": next((r.priority for r in self._registrations if r.provider is p), None),
                "timeout_seconds": getattr(p, "timeout_seconds", None),
                "connected": p.connected,
                "status": status.get("status"),
                "capabilities": status.get("capabilities", {"search": p.connected}),
            })
        return out


REGISTRY = ProviderRegistry()
# priority 0: the wired internal supplier offer pool -- the only real inventory
# source today. priority 10: declared-but-disabled external carriers, kept
# registered (not hidden) so their truthful not_connected state is always
# visible in diagnostics and provider_fanout, never silently omitted.
REGISTRY.register(_POOL, priority=0)
for _ext in EXTERNAL_PROVIDERS:
    REGISTRY.register(_ext, priority=10)
