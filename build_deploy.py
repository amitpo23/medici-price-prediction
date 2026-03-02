"""Build deploy.zip for Azure App Service deployment.

Usage:
    python build_deploy.py          # build zip only
    python build_deploy.py --deploy # build + deploy to Azure

Exclusion rules:
- Top-level dirs: .git, .venv, data, docs (data/ = JSON/CSV files, NOT src/data/)
- Any dir named __pycache__ anywhere
- Any *.egg-info dir anywhere
- Files: .env, deploy.zip
- Extensions: .pyc, .pyo
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent

# Only top-level directories to exclude
TOP_LEVEL_EXCLUDE = {".git", ".venv", "data", "docs"}
# Directories excluded anywhere in the tree
DEEP_EXCLUDE_NAMES = {"__pycache__"}
DEEP_EXCLUDE_SUFFIXES = {".egg-info"}
EXCLUDE_FILES = {".env", "deploy.zip", "build_deploy.py"}
EXCLUDE_EXT = {".pyc", ".pyo"}

AZURE_APP = "medici-prediction-api"
AZURE_RG = "medici-prediction-rg"
OUT_ZIP = ROOT / "deploy.zip"


def build_zip() -> int:
    included = []
    for p in ROOT.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(ROOT)
        parts = rel.parts

        # Skip top-level excluded dirs (parts[0] check — does NOT affect src/data/)
        if parts[0] in TOP_LEVEL_EXCLUDE:
            continue

        # Skip __pycache__ and .egg-info anywhere in path
        if any(part in DEEP_EXCLUDE_NAMES for part in parts):
            continue
        if any(part.endswith(tuple(DEEP_EXCLUDE_SUFFIXES)) for part in parts):
            continue

        if rel.name in EXCLUDE_FILES:
            continue
        if rel.suffix in EXCLUDE_EXT:
            continue

        included.append((p, rel))

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, rel in included:
            zf.write(p, rel)

    # Verify critical paths
    with zipfile.ZipFile(OUT_ZIP) as zf:
        names = set(zf.namelist())

    checks = {
        "src/data/trading_db.py": True,
        "src/data/yoy_db.py": True,
        "src/analytics/booking_benchmarks.py": True,
        "data/booking_benchmarks.json": False,  # must NOT be present
    }
    all_ok = True
    for path, should_exist in checks.items():
        exists = any(n == path or n.startswith(path) for n in names)
        status = "OK" if exists == should_exist else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] {path} {'present' if exists else 'absent'} (expected {'present' if should_exist else 'absent'})")

    print(f"\nBuilt {OUT_ZIP.name}: {len(included)} files")
    return 0 if all_ok else 1


def deploy() -> int:
    print(f"Deploying {OUT_ZIP} to {AZURE_APP}...")
    result = subprocess.run([
        "az", "webapp", "deploy",
        "--name", AZURE_APP,
        "--resource-group", AZURE_RG,
        "--src-path", str(OUT_ZIP),
        "--type", "zip",
    ])
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy", action="store_true", help="Deploy after building")
    args = parser.parse_args()

    rc = build_zip()
    if rc != 0:
        print("\nERROR: zip validation failed — not deploying")
        raise SystemExit(rc)

    if args.deploy:
        raise SystemExit(deploy())
