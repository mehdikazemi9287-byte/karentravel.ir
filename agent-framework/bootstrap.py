"""Render agent instructions to stdout only; never modify a target project."""
import argparse
import json
from pathlib import Path
import re
import sys

KEYS = {"PROJECT_NAME", "PROJECT_ROOT", "SERVER", "PRODUCTION_PATH", "SERVICES",
        "PROTECTED_AREAS", "PROJECT_SPECIFIC_RULES"}
SUPPORTED = {"Karen Travel", "60Online", "Estehkam", "ShadShahr", "Padvira", "CheckLine"}


def render(values):
    if not isinstance(values, dict) or set(values) != KEYS:
        raise ValueError("Provide exactly the seven documented project variables")
    if any(not isinstance(v, str) or not v.strip() for v in values.values()):
        raise ValueError("Each project variable must be a non-empty string")
    if values["PROJECT_NAME"] not in SUPPORTED:
        raise ValueError("Unsupported project; explicit user instruction is required to extend support")
    if not Path(values["PROJECT_ROOT"]).is_absolute():
        raise ValueError("PROJECT_ROOT must be an absolute path")
    base = Path(__file__).resolve().parent
    substitutions = dict(values, MASTER_RULES=(base / "MASTER_RULES.md").read_text())
    template = (base / "AGENTS.template.md").read_text()
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: substitutions[m[1]], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variables", type=Path, help="JSON file containing seven non-secret project values")
    args = parser.parse_args()
    try:
        result = render(json.loads(args.variables.read_text()))
    except (OSError, ValueError, KeyError) as exc:
        print(f"Bootstrap blocked: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
