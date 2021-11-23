#!/usr/bin/env bash

set -eux -o pipefail

VENV_DIR="${TMPDIR}/haskell-sublime-syntax-venv"
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install PyYAML flake8 mypy
    "${VENV_DIR}/bin/mypy" --install-types --non-interactive .
fi

# run linting, but don't fail on failures
"${VENV_DIR}/bin/flake8" . \
    --ignore=E201,E202,E266,E302,E305,E306,E501 \
    || true

# run typechecking, but don't fail on failures
"${VENV_DIR}/bin/mypy" . || true

"${VENV_DIR}/bin/python" generate.py
