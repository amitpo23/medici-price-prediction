"""Build deploy.zip for Azure deployment."""
import zipfile
import os
import shutil

shutil.copy2("requirements-deploy.txt", "requirements.txt")

EXCLUDE_TOP = {".venv", ".git", ".claude", "__pycache__", "data", "docs", ".mypy_cache", ".pytest_cache"}
EXCLUDE_FILES = {".env", "deploy.zip", "requirements-deploy.txt", "query_salesoffice_orders.py"}
INCLUDE_DATA = {"miami_hotels_tbo.csv", "booking_benchmarks.json"}

with zipfile.ZipFile("deploy.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk("."):
        rel_root = os.path.relpath(root, ".")
        parts = rel_root.split(os.sep) if rel_root != "." else []
        if parts and parts[0] in EXCLUDE_TOP:
            continue
        if "__pycache__" in parts:
            continue
        for f in files:
            rel_path = os.path.join(rel_root, f) if rel_root != "." else f
            if f in EXCLUDE_FILES or f.endswith(".pyc"):
                continue
            if parts and parts[0] == "data" and f not in INCLUDE_DATA:
                continue
            zf.write(rel_path)
    print(f"Built {len(zf.namelist())} files -> deploy.zip")

os.remove("requirements.txt")
