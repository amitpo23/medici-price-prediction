#!/bin/bash
set -e
pip install --no-cache-dir -r requirements-deploy.txt 2>&1 | tail -5
gunicorn --bind 0.0.0.0:${PORT:-8000} -w 1 -k uvicorn.workers.UvicornWorker src.api.main:app --timeout 900 --graceful-timeout 300
