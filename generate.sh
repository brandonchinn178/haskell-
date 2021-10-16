#!/usr/bin/env bash

set -eux -o pipefail

VENV_DIR=/tmp/venv
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install PyYAML
fi

"${VENV_DIR}/bin/python" generate.py
