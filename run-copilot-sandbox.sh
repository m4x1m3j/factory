#!/usr/bin/env bash
# run-copilot-sandbox.sh
# Runs GitHub Copilot inside the Docker Agent Sandbox.

set -euo pipefail

SANDBOX_NAME="copilot-sandbox"
PROMPT=""
DO_LOGIN=0
EXEC_CMD=""
EXTRA_ARGS=()

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] [-- COPILOT_ARGS...]

Options:
  -n, --name <name>       Name of the sandbox (default: $SANDBOX_NAME)
  -p, --prompt <prompt>   Run Copilot non-interactively with a prompt
  -e, --exec <command>    Execute a shell command inside the sandbox
  --login                 Run interactive Copilot device-code login inside the sandbox
  -h, --help              Show this help message

Examples:
  # Start interactive Copilot session
  ./$(basename "$0")

  # Start with a specific sandbox name
  ./$(basename "$0") -n my-copilot-sandbox

  # Run non-interactive prompt
  ./$(basename "$0") -p "Review recent changes and summarize"

  # Authenticate via OAuth device code inside the sandbox
  ./$(basename "$0") --login

  # Pass custom flags directly to Copilot
  ./$(basename "$0") -- --model gpt-5.4
EOF
}

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--name)
            SANDBOX_NAME="$2"
            shift 2
            ;;
        -p|--prompt)
            PROMPT="$2"
            shift 2
            ;;
        -e|--exec)
            EXEC_CMD="$2"
            shift 2
            ;;
        --login)
            DO_LOGIN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS=("$@")
            break
            ;;
        *)
            # Collect other arguments to pass to copilot
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# 1. Verify sandbox exists
STATUS=$(sbx ls 2>/dev/null | awk -v name="$SANDBOX_NAME" '$1 == name {print $3}')
if [ -z "$STATUS" ]; then
    echo "Error: Sandbox '$SANDBOX_NAME' does not exist." >&2
    echo "Run './setup-copilot-sandbox.sh -n $SANDBOX_NAME' first to create it." >&2
    exit 1
fi

# 2. Execute command inside sandbox if requested
if [ -n "$EXEC_CMD" ]; then
    echo "Executing command in sandbox '$SANDBOX_NAME'..."
    exec sbx exec -it "$SANDBOX_NAME" sh -lc "$EXEC_CMD"
fi

# 3. Handle login flow if requested
if [ "$DO_LOGIN" -eq 1 ]; then
    echo "Initiating Copilot login inside sandbox '$SANDBOX_NAME'..."
    exec sbx exec -it "$SANDBOX_NAME" copilot login --device-code
fi

# 4. Run prompt mode or interactive mode
if [ -n "$PROMPT" ]; then
    echo "Running Copilot prompt in sandbox '$SANDBOX_NAME'..."
    if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
        exec sbx run --name "$SANDBOX_NAME" -- -p "$PROMPT" --allow-all-tools "${EXTRA_ARGS[@]}"
    else
        exec sbx run --name "$SANDBOX_NAME" -- -p "$PROMPT" --allow-all-tools
    fi
else
    echo "Attaching to Copilot in sandbox '$SANDBOX_NAME'..."
    if [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
        exec sbx run --name "$SANDBOX_NAME" -- "${EXTRA_ARGS[@]}"
    else
        exec sbx run --name "$SANDBOX_NAME"
    fi
fi
