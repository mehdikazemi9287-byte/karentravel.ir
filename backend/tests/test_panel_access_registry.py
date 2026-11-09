"""The frontend panel registry (lib/panel-access.ts) reads role permissions from lib/role-permissions.json.
That file must stay an exact copy of the backend RBAC table, or the menus and the route guard drift from the API."""
import json
from pathlib import Path

from app.security import ROLE_PERMISSIONS


def test_frontend_role_permissions_match_backend():
    path = Path(__file__).resolve().parents[2] / "lib" / "role-permissions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()}
