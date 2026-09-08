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

## Execution Sandboxes

Agent commands can be run in an ephemeral Docker container without mounting the
current checkout:

```console
factory sandbox run issue-7 -- python -m pytest
```

The manager creates a self-contained temporary Git clone, mounts only that clone
at `/workspace`, disables networking, drops Linux capabilities, applies CPU,
memory, and process limits, and removes the clone after execution. Changes are
committed only inside the temporary clone and returned as a diff; no branch is
created in the caller's repository. This makes the command suitable for
verification and experimentation without accumulating local branches. Use
`--json` for structured output and `--repository PATH` to target a repository
other than the current directory.

When the repository contains `pyproject.toml`, Factory prepares a temporary
Python image with `uv` and installs the project's declared dependencies and dev
dependencies. The mounted clone is the image's `/workspace` source tree, while
the environment is kept outside the mounted workspace at
`/opt/factory-venv`, so installation does not add files to the Git diff. Image
builds may require network access even when the command container itself uses
`--network none`. Runtime commands set `UV_NO_SYNC=1`, so they use the
environment prepared during the image build and do not attempt network
dependency resolution in the network-isolated container. The runtime `uv` cache
is placed at `/tmp/uv-cache`, which is writable by the non-root sandbox user and
discarded with the container.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code quality standards (Ruff, mypy, pre-commit), and testing guidelines.
