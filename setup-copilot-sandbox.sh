#!/usr/bin/env bash
# setup-copilot-sandbox.sh
# Sets up a Docker Agent Sandbox running GitHub Copilot in clone mode
# with a custom .github directory mounted and authenticated.

set -euo pipefail

SANDBOX_NAME="copilot-sandbox"
REPO_DIR="$(pwd)"
CUSTOM_GITHUB_DIR=""
TEMPLATE=""
TOKEN=""
FORCE=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -n, --name <name>         Name of the sandbox (default: $SANDBOX_NAME)
  -r, --repo <path>         Path to host Git repository to clone (default: current directory)
  -g, --github-dir <path>   Path to custom .github directory to mount (default: <repo>/.github)
  -t, --template <image>    Custom template image to use (default: custom-copilot:v1 if loaded, else copilot-docker)
  -k, --token <token>       GitHub token with Copilot access (or via GITHUB_TOKEN/COPILOT_TOKEN)
  -f, --force               Remove existing sandbox with the same name before setup
  -h, --help                Show this help message
EOF
}

# Parse command line options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--name)
            SANDBOX_NAME="$2"
            shift 2
            ;;
        -r|--repo)
            REPO_DIR="$2"
            shift 2
            ;;
        -g|--github-dir)
            CUSTOM_GITHUB_DIR="$2"
            shift 2
            ;;
        -t|--template)
            TEMPLATE="$2"
            shift 2
            ;;
        -k|--token)
            TOKEN="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=1
            shift
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

echo "=== Setting up Copilot Docker Agent Sandbox ==="

# 1. Verify sbx CLI is installed
if ! command -v sbx >/dev/null 2>&1; then
    echo "Error: 'sbx' CLI not found. Please install Docker Sandboxes (https://docs.docker.com/ai/sandboxes/install/)" >&2
    exit 1
fi

# 2. Verify repository path
REPO_DIR="$(cd "$REPO_DIR" && pwd)"
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Error: '$REPO_DIR' is not a Git repository." >&2
    exit 1
fi
echo "✓ Git repository: $REPO_DIR"

# 3. Determine and verify custom .github directory
if [ -z "$CUSTOM_GITHUB_DIR" ]; then
    CUSTOM_GITHUB_DIR="$REPO_DIR/.github"
fi
CUSTOM_GITHUB_DIR="$(cd "$CUSTOM_GITHUB_DIR" 2>/dev/null && pwd || true)"

if [ -z "$CUSTOM_GITHUB_DIR" ] || [ ! -d "$CUSTOM_GITHUB_DIR" ]; then
    echo "Warning: Custom .github directory '$CUSTOM_GITHUB_DIR' does not exist."
    echo "Creating empty directory at $CUSTOM_GITHUB_DIR..."
    mkdir -p "$CUSTOM_GITHUB_DIR"
fi
echo "✓ Custom .github directory: $CUSTOM_GITHUB_DIR"

# 4. Handle authentication
# Resolve token from args or env if available
if [ -z "$TOKEN" ]; then
    if [ -n "${COPILOT_GITHUB_TOKEN:-}" ]; then
        TOKEN="$COPILOT_GITHUB_TOKEN"
    elif [ -n "${COPILOT_TOKEN:-}" ]; then
        TOKEN="$COPILOT_TOKEN"
    elif [ -n "${GH_TOKEN:-}" ]; then
        TOKEN="$GH_TOKEN"
    elif [ -n "${GITHUB_TOKEN:-}" ]; then
        TOKEN="$GITHUB_TOKEN"
    fi
fi

if [ -n "$TOKEN" ]; then
    echo "✓ Configuring GitHub/Copilot token in sbx secrets..."
    sbx secret set github --token "$TOKEN" -f >/dev/null 2>&1
    sbx secret set copilot --token "$TOKEN" -f >/dev/null 2>&1
    echo "✓ Stored token into sbx secrets"
elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "✓ Using host GitHub CLI ('gh') authentication for sbx secrets..."
    sbx secret set github --command 'gh auth token' >/dev/null 2>&1
    sbx secret set copilot --command 'gh auth token' >/dev/null 2>&1
elif sbx secret ls 2>/dev/null | grep -qE "github|copilot"; then
    echo "✓ Found existing stored GitHub/Copilot secrets in sbx"
else
    echo "Notice: No GitHub/Copilot token found in environment or sbx secrets."
    echo "You can set one via --token, GITHUB_TOKEN, or run 'copilot login' inside the sandbox."
fi

# 5. Handle existing sandbox
EXISTING_STATUS=$(sbx ls 2>/dev/null | awk -v name="$SANDBOX_NAME" '$1 == name {print $3}')
if [ -n "$EXISTING_STATUS" ]; then
    if [ "$FORCE" -eq 1 ]; then
        echo "Removing existing sandbox '$SANDBOX_NAME' (--force)..."
        sbx rm "$SANDBOX_NAME" -f >/dev/null 2>&1 || true
    else
        echo "Sandbox '$SANDBOX_NAME' already exists (status: $EXISTING_STATUS)."
        echo "Use -f / --force to recreate it, or run ./run-copilot-sandbox.sh -n $SANDBOX_NAME to start it."
        exit 0
    fi
fi

# 6. Resolve template
# If no template was specified, check if custom-copilot:v1 exists, otherwise build it or prompt
TEMPLATE_ARGS=()
if [ -n "$TEMPLATE" ]; then
    TEMPLATE_ARGS=("-t" "$TEMPLATE")
elif sbx template ls 2>/dev/null | grep -q "custom-copilot"; then
    echo "✓ Found loaded custom template: custom-copilot:v1"
    TEMPLATE_ARGS=("-t" "custom-copilot:v1")
elif [ -f "./build-copilot-template.sh" ]; then
    echo "Custom template 'custom-copilot:v1' not found in sbx. Building it now..."
    ./build-copilot-template.sh
    TEMPLATE_ARGS=("-t" "custom-copilot:v1")
fi

# 7. Create sandbox in clone mode with custom .github mounted
echo "Creating clone-mode sandbox '$SANDBOX_NAME'..."

IS_INSIDE_REPO=0
case "$CUSTOM_GITHUB_DIR" in
    "$REPO_DIR"/*|"$REPO_DIR")
        IS_INSIDE_REPO=1
        ;;
esac

if [ "$IS_INSIDE_REPO" -eq 1 ]; then
    # In clone mode, sbx automatically mounts $REPO_DIR at /run/sandbox/source (ro).
    # If .github is inside the repo, mounting it as a second workspace argument to sbx create
    # causes virtiofs to collide with the clone destination directory before git-clone.
    # So we create the clone, and then wire the live mount from /run/sandbox/source/.github.
    sbx create "${TEMPLATE_ARGS[@]}" --name "$SANDBOX_NAME" --clone copilot "$REPO_DIR"
    MOUNTED_TARGET="/run/sandbox/source/.github"
else
    # External custom .github directory: mount it directly as an additional read-only workspace
    sbx create "${TEMPLATE_ARGS[@]}" --name "$SANDBOX_NAME" --clone copilot "$REPO_DIR" "$CUSTOM_GITHUB_DIR:ro"
    MOUNTED_TARGET="$CUSTOM_GITHUB_DIR"
fi

echo "✓ Created sandbox '$SANDBOX_NAME'"

# 8. Configure network policy for Git push (SSH port 22)
echo "Configuring network policy for Git operations..."
sbx policy allow network --sandbox "$SANDBOX_NAME" "github.com:22" >/dev/null 2>&1 || true

# 9. Wire custom .github into the cloned workspace and configure SSH
echo "Mounting custom .github directory into sandbox workspace..."
sbx exec "$SANDBOX_NAME" sh -lc "
    mkdir -p '$MOUNTED_TARGET'
    rm -rf '$REPO_DIR/.github'
    ln -sfn '$MOUNTED_TARGET' '$REPO_DIR/.github'
    mkdir -p ~/.ssh && chmod 700 ~/.ssh
    if [ ! -f /etc/ssh/ssh_known_hosts ]; then
        ssh-keyscan -t ed25519,rsa github.com >> ~/.ssh/known_hosts 2>/dev/null || true
    fi
"

# 10. Verify sandbox setup
echo "Verifying sandbox..."
sbx exec "$SANDBOX_NAME" sh -lc "
    echo 'Workspace: '\$(pwd)
    echo 'Git branch: '\$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'not a git repo')
    echo 'Git remote: '\$(git remote get-url origin 2>/dev/null || echo 'none')
    echo 'Custom .github mounted at: '\$(readlink -f .github)
    echo 'Hook tools: rtk='\$(which rtk || echo 'missing')', just='\$(which just || echo 'missing')
    echo 'Copilot version: '\$(copilot --version 2>/dev/null || echo 'copilot ready')
"

echo ""
echo "=== Setup complete! ==="
echo "To run Copilot in this sandbox, use:"
echo "  ./run-copilot-sandbox.sh -n $SANDBOX_NAME"
