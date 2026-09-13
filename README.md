# Factory

Factory is an AI software factory.
It is in two parts:

- A software factory template, that can be instanciated for any new software projet
- A mlops example project, that instanciate the template, and is used as a proof of concept of the factory.

## Main specifications of the factory

The factory is an ensemble of agents that will:

- Signal detection and triage. Figuring out what needs to be built or fixed. Reading GitHub issues, errors, user feedback, and stale PRs, then deciding what is worth doing and in what order. A chat / CLI interface is also available.+
- Code generation. Taking a well-understood problem and producing a correct solution. Reading the codebase, matching its patterns, writing the change and its tests.
- Validation. Verifying the solution is correct, secure, performant, and maintainable. Review, test runs, security scans.
- Release management. Getting a validated change into production. Version bumps, changelogs, deploy, health checks, rollback when needed.
- Documentation. Keeping written artifacts in sync with what the code actually does. API references, runbooks, architecture notes, inline comments.
- Production monitoring. Watching for problems. Detecting anomalies, opening incidents, and routing what they find back into the development loop.

The factory will be agnostic of model, agents, or IDE.

The factory template can be modified, and the modifications will need to be made in every factory-based project.

Our base tech stack will be Python, github.

## Shared Agent Assets

Factory packages vendor-neutral agent instructions, personas, skills, hooks, and
MCP templates. Project initialization synchronizes them automatically. Existing
projects can refresh generated files with:

```console
factory project sync-assets
factory project sync-assets --directory PATH
```

Copilot files are written under `.github/`, OpenCode files under `.opencode/`,
GitHub MCP configuration under `.vscode/mcp.json` and `opencode.json`. The
GitHub token is read from `GITHUB_TOKEN`; no token is written into generated
files.


## Copilot Agent Sandboxes

Run GitHub Copilot inside isolated microVM sandboxes via Docker Sandboxes (`sbx`) using an in-container Git clone:

```console
# 1. Build and load the custom Copilot template
./build-copilot-template.sh

# 2. Setup the sandbox in clone mode with custom .github mounted and GitHub token configured
./setup-copilot-sandbox.sh

# 3. Run interactive Copilot session or execute non-interactive prompts
./run-copilot-sandbox.sh
./run-copilot-sandbox.sh -p "Check git status and summarize recent commits"
```

### Key Components

- [build-copilot-template.sh](build-copilot-template.sh): Extends `docker/sandbox-templates:copilot-docker` using [docker/copilot/Dockerfile](docker/copilot/Dockerfile) with `just`, `rtk`, and GitHub SSH host keys pre-configured, then loads the image into `sbx template`.
- [setup-copilot-sandbox.sh](setup-copilot-sandbox.sh): Creates an isolated clone-mode sandbox (`--clone`), mounts the custom `.github` folder into the sandbox, synchronizes GitHub credentials into `sbx secret`, and configures sandbox network policy to allow SSH Git pushes (`github.com:22`).
- [run-copilot-sandbox.sh](run-copilot-sandbox.sh): Starts interactive or non-interactive Copilot sessions, command execution (`-e`), and OAuth device-code login (`--login`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code quality standards (Ruff, mypy, pre-commit), and testing guidelines.
