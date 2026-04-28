"""
scripts/first-run-onboard.py — installer-friendly entrypoint.

Wraps onboard/designer.py with a guaranteed-seeded picker so installers
can never accidentally bake a hardcoded expression list into a fresh
agent. Always calls designer.py with --random, which forces the
hash-seeded, personality-driven expression picker.

Usage (from installer or shell):
  python scripts/first-run-onboard.py                 # auto-derive name+slug from cwd
  python scripts/first-run-onboard.py --name Foo      # explicit name, slug derived
  python scripts/first-run-onboard.py --name Foo --slug foo

Idempotency:
  If config/face.json already exists with onboarded:true, this script
  prints a one-line note and exits 0 — re-running is safe and won't
  overwrite an agent's chosen identity. Pass --force to overwrite.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGNER = ROOT / "onboard" / "designer.py"
CONFIG = ROOT / "config" / "face.json"


def derive_slug(name):
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", name.strip().lower()).strip("-")
    return s or "agent"


def already_onboarded():
    if not CONFIG.exists():
        return False
    try:
        return bool(json.loads(CONFIG.read_text(encoding="utf-8")).get("onboarded"))
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="Seeded first-run onboarding for AXIOM-Body.")
    ap.add_argument("--name", help="Agent display name (default: cwd basename)")
    ap.add_argument("--slug", help="Agent slug (default: derived from --name)")
    ap.add_argument("--force", action="store_true", help="Overwrite existing config/face.json")
    args = ap.parse_args()

    if not args.force and already_onboarded():
        print("[first-run-onboard] config/face.json already onboarded -- skipping. "
              "Pass --force to re-onboard.", file=sys.stderr)
        return 0

    name = args.name or Path.cwd().name or "Agent"
    slug = args.slug or derive_slug(name)

    cmd = [
        sys.executable, str(DESIGNER),
        "--name", name,
        "--slug", slug,
        "--random",
    ]
    print(f"[first-run-onboard] running: {' '.join(cmd)}", file=sys.stderr)
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    sys.exit(main())
