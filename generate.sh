#!/usr/bin/env bash

set -eux -o pipefail

VENV_DIR=/tmp/venv
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install PyYAML flake8
fi

# run linting, but don't fail on failures
"${VENV_DIR}/bin/flake8" . \
    --ignore=E501,E302,E306,E266,E305,E201,E202 \
    || true

"${VENV_DIR}/bin/python" generate.py
