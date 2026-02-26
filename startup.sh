#!/bin/bash
gunicorn --bind 0.0.0.0:${PORT:-8000} -w 2 -k uvicorn.workers.UvicornWorker src.api.main:app --timeout 120
