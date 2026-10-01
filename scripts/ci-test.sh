#!/usr/bin/env sh
set -eu

python3 scripts/prepare_runtime.py
python3 -m compileall -q app tests alembic scripts main.py setup.py
python3 -m pip check
python3 -m unittest discover -s tests -v
