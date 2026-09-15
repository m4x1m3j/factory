#!/usr/bin/env bash
# build-copilot-template.sh
# Builds and loads a custom Docker Agent Sandbox template for GitHub Copilot.
# Includes `just` and `rtk` (required by .github/hooks).

set -euo pipefail

IMAGE_NAME="custom-copilot:v1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/docker/copilot"
TAR_PATH="/tmp/custom-copilot-template.tar"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -t, --tag <tag>     Template image tag (default: $IMAGE_NAME)
  -h, --help          Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--tag)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

echo "=== Building custom Copilot template image ($IMAGE_NAME) ==="

# Check prerequisite tools
if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker command not found." >&2
    exit 1
fi

if ! command -v sbx >/dev/null 2>&1; then
    echo "Error: sbx command not found." >&2
    exit 1
fi

# Locate rtk binary to copy into the template
RTK_BIN="$(command -v rtk || true)"
if [ -z "$RTK_BIN" ] && [ -x "$HOME/.local/bin/rtk" ]; then
    RTK_BIN="$HOME/.local/bin/rtk"
fi

mkdir -p "$DOCKER_DIR"

# Cleanup temporary files on exit
trap 'rm -f "$DOCKER_DIR/rtk" "$TAR_PATH"' EXIT

if [ -n "$RTK_BIN" ] && [ -f "$RTK_BIN" ]; then
    echo "✓ Found host rtk binary at $RTK_BIN"
    cp "$RTK_BIN" "$DOCKER_DIR/rtk"
else
    echo "Warning: rtk binary not found on host. Downloading latest Linux release..."
    curl -fsSL https://github.com/rtk-ai/rtk/releases/latest/download/rtk-x86_64-unknown-linux-gnu.tar.gz -o /tmp/rtk.tar.gz
    tar -xzf /tmp/rtk.tar.gz -C "$DOCKER_DIR" rtk
    rm -f /tmp/rtk.tar.gz
fi

# Ensure Dockerfile exists
if [ ! -f "$DOCKER_DIR/Dockerfile" ]; then
    cat <<'EOF' > "$DOCKER_DIR/Dockerfile"
FROM docker/sandbox-templates:copilot-docker

USER root

# Install system dependencies including just and openssh-client
RUN apt-get update && \
    apt-get install -y --no-install-recommends just openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Pre-populate known hosts for github.com system-wide
RUN ssh-keyscan -t ed25519,rsa github.com >> /etc/ssh/ssh_known_hosts && \
    chmod 644 /etc/ssh/ssh_known_hosts

# Copy rtk CLI into system path
COPY --chmod=755 rtk /usr/local/bin/rtk

USER agent
EOF
fi

# Build Docker image
echo "Building docker image..."
docker build -t "$IMAGE_NAME" "$DOCKER_DIR"

# Save image and load into Docker Sandboxes template cache
echo "Saving image and loading into sbx template storage..."
docker image save "$IMAGE_NAME" -o "$TAR_PATH"
sbx template load "$TAR_PATH"

echo "✓ Template '$IMAGE_NAME' successfully built and loaded into sbx!"
sbx template ls
