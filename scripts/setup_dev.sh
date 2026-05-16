#!/bin/bash
# Setup script for libp2p specs local development (markdown preview + lint)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Setting up libp2p specs development environment...${NC}"

find_compatible_python() {
    if PYTHON_BIN="$(python "${SCRIPT_DIR}/dev_setup.py" 2>/dev/null)"; then
        echo "${PYTHON_BIN}"
        return 0
    fi
    return 1
}

activate_venv() {
    if [[ -f ".venv/bin/activate" ]]; then
        # shellcheck source=/dev/null
        source ".venv/bin/activate"
    elif [[ -f ".venv/Scripts/activate" ]]; then
        # shellcheck source=/dev/null
        source ".venv/Scripts/activate"
    else
        echo -e "${RED}Virtual environment is missing an activate script.${NC}"
        exit 1
    fi
}

ensure_venv() {
    if [[ -n "${VIRTUAL_ENV}" ]]; then
        return 0
    fi

    PYTHON_BIN="$(find_compatible_python)" || {
        echo -e "${RED}Python 3.10+ is required for Grip and local tooling.${NC}"
        exit 1
    }

    echo -e "${YELLOW}Creating virtual environment with ${PYTHON_BIN}...${NC}"
    "${PYTHON_BIN}" -m venv .venv
    activate_venv
}

verify_venv_python() {
    python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
        echo -e "${RED}Active Python is older than 3.10. Remove .venv and re-run setup.${NC}"
        exit 1
    }
}

ensure_venv
verify_venv_python

echo -e "${GREEN}Installing Python tools (grip)...${NC}"
python -m pip install --upgrade pip
python -m pip install grip

if command -v npm &> /dev/null; then
    echo -e "${GREEN}Installing Node dev dependencies...${NC}"
    npm install
else
    echo -e "${YELLOW}npm not found; skip markdownlint-cli2 install. Install Node.js to run npm run lint.${NC}"
fi

echo -e "${GREEN}Setup complete! Run: npm run dev${NC}"
