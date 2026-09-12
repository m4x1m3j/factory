#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This bootstrap script supports Linux only." >&2
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install development tools." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    curl --fail --location --silent --show-error \
        https://astral.sh/uv/install.sh | sh
fi

export PATH="$HOME/.local/bin:$PATH"

uv tool install --reinstall rust-just

if ! command -v rtk >/dev/null 2>&1; then
    curl --fail --location --silent --show-error \
        https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
fi

uv sync --dev
uv run pre-commit install
