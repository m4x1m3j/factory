# ci-fix skill

Iterates through CI fix cycles on a GitLab MR until all pipeline jobs are green.
For each failing pipeline: inspects job logs, classifies failures as obvious/non-obvious,
applies fixes (one commit per job), pushes on confirmation, and updates the pivot document.

## Prerequisites

### 1. GitLab personal access token

Export your GitLab personal access token with `api` scope:

```bash
export GITLAB_PERSONAL_ACCESS_TOKEN=<your-token>
```

Create a token at: `https://<your-gitlab-instance>/-/user_settings/personal_access_tokens`

### 2. Enable GitLab MCP pipeline tools

In `.vscode/mcp.json`, set:

```json
"USE_PIPELINE": true
```

This enables the pipeline tool set (`list_pipeline_jobs`, `get_pipeline_job_output`, etc.)
that the Copilot agent uses to inspect failing jobs.

## Installation

From the repository root:

```bash
pipx install ./ci-fix
```

Verify:

```bash
ci-fix --help
```

## Usage

### Single cycle (inspect → fix → push confirmation → stop)

```bash
ci-fix --single
```

### Loop until green

```bash
ci-fix --loop
```

### Loop with limits

```bash
ci-fix --loop --max-iterations 5 --timeout 30m
```

## Flags

| Flag | Description |
|------|-------------|
| `--single` | Run one fix cycle then stop |
| `--loop` | Run fix cycles until the pipeline is green or a blocking condition is hit |
| `--max-iterations N` | Stop after N fix cycles (default: unlimited) |
| `--timeout Xm` | Stop after X minutes regardless of pipeline status |

## How it works

1. **Pre-flight**: verifies `GITLAB_PERSONAL_ACCESS_TOKEN`, detects the open MR for the
   current branch, and fetches the latest pipeline.
2. **Agent invocation**: launches the Copilot `ci-fix` skill with MR number, pipeline ID,
   and the path to the pivot document (`ci-fix-<mr-number>.md`).
3. **Failure classification**: the agent reads each failed job log and classifies failures
   as `obvious` (clear fix) or `non-obvious` (requires human judgment).
4. **Fix + commit**: one commit per obvious failing job (`fix: ci — <job>: <description>`).
5. **Push confirmation**: `[y/N]` prompt before pushing.
6. **Polling**: the orchestrator polls GitLab every 30 seconds until the new pipeline
   completes, then re-invokes the agent if needed.

## Blocking conditions

The loop stops and prompts for manual intervention when:

- All failures in a cycle are non-obvious.
- The user declines the push confirmation.
- The same job fails with the same summary in two consecutive cycles (stale loop).
- A job that was green in cycle N is failing in cycle N+1 (regression).
- `--max-iterations` is reached.
- `--timeout` elapses.

## Pivot document

Each run appends to `ci-fix-<mr-number>.md` in the working directory. This file tracks
cycle history (pipeline IDs, job classifications, status). It is gitignored automatically.
