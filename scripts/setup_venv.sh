#!/usr/bin/env bash
# Bootstrap a venv when the OS Python has no ensurepip.
# Recreates .venv in the repository root. Run it from anywhere:
#   bash scripts/setup_venv.sh
set -eu
cd "$(dirname "$0")/.."
rm -rf .venv
python3 -m venv --without-pip .venv
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip-podoba.py
.venv/bin/python /tmp/get-pip-podoba.py
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -c 'import langgraph, fastapi, streamlit, rank_bm25, pytest; print("imports-ok")'
