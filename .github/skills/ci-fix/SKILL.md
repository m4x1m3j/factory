---
name: ci-fix
description: >
  Iterates through CI fix cycles on a GitLab MR until all pipeline jobs are
  green. For each failing pipeline: inspects job logs, classifies failures as
  obvious/non-obvious, applies fixes (one commit per job), pushes on
  confirmation, and updates the pivot document for the orchestrator.
---

<!--
## GitLab MCP Pipeline Tools (requires USE_PIPELINE: true in .vscode/mcp.json)

Server name in mcp.json: "gitlabvsct"
All tool calls must be prefixed with "mcp_gitlabvsct_".

### List pipelines for a project
Tool: mcp_gitlabvsct_list_pipelines
Params:
  - project_id: string  (e.g. "group/repo")
  - ref: string         (branch name, optional — filter by branch)
  - status: string      (optional — "running", "failed", "success", etc.)
Returns: array of pipeline objects with fields: id, status, ref, sha, web_url

### List pipelines for a specific MR
Tool: mcp_gitlabvsct_list_merge_request_pipelines
Params:
  - project_id:        string  (e.g. "group/repo")
  - merge_request_iid: number  (the MR IID, not the global ID)
Returns: array of pipeline objects with fields: id, status, ref, sha, web_url

### Get a specific pipeline
Tool: mcp_gitlabvsct_get_pipeline
Params:
  - project_id:  string  (e.g. "group/repo")
  - pipeline_id: number
Returns: pipeline object with fields: id, status, ref, sha, created_at, web_url

### List jobs in a pipeline
Tool: mcp_gitlabvsct_list_pipeline_jobs
Params:
  - project_id:  string  (e.g. "group/repo")
  - pipeline_id: number
  - scope: string        (optional — "failed", "success", "running", etc.)
Returns: array of job objects with fields: id, name, status, stage, web_url,
         artifacts_file, runner, created_at, started_at, finished_at

### Get a specific pipeline job
Tool: mcp_gitlabvsct_get_pipeline_job
Params:
  - project_id: string  (e.g. "group/repo")
  - job_id:     number
Returns: job object (same fields as list_pipeline_jobs entries)

### Fetch raw log text for a job
Tool: mcp_gitlabvsct_get_pipeline_job_output
Params:
  - project_id: string  (e.g. "group/repo")
  - job_id:     number
  - limit:      number  (optional — max bytes to return)
  - offset:     number  (optional — byte offset to start from)
Returns: raw log text as a string
-->

<what-to-do>

## Startup — read arguments and validate branch

You receive the following arguments when invoked by the orchestrator:

| Argument | Description |
|----------|-------------|
| `MR_NUMBER` | The GitLab MR ID to fix |
| `PIPELINE_ID` | The current failing pipeline ID |
| `PIPELINE_STATUS` | The pipeline status (`failed` or `canceled`) |
| `PIVOT_PATH` | Absolute path to the pivot document (e.g. `ci-fix-42.md`) |

**Step 1 — Validate the current branch.**

Run `git rev-parse --abbrev-ref HEAD` to get the current branch name.

Use the GitLab MCP tool `mcp_gitlabvsct_get_merge_request` to fetch the MR
and read its `source_branch` field.

If the current branch does **not** match `source_branch`, abort immediately:

```
ERROR: current branch '<current>' does not match MR !<MR_NUMBER> source branch '<expected>'.
       Switch to '<expected>' before running ci-fix.
```

**Step 2 — Initialise or append to the pivot document.**

Check whether `PIVOT_PATH` exists.

- **First run** (file does not exist): call `python -c "from ci_fix import pivot; pivot.create('$PIVOT_PATH', $MR_NUMBER)"` to create it.
  The file will contain:
  ```
  MR_NUMBER: <MR_NUMBER>
  STATUS: in-progress
  ```

- **Subsequent runs** (file exists): append a new cycle header block:
  ```python
  from ci_fix import pivot
  pivot.append_cycle(PIVOT_PATH, {"PIPELINE_ID": PIPELINE_ID, "STATUS": "in-progress"})
  ```

After writing, confirm the pivot document exists and contains the correct `MR_NUMBER` and `STATUS: in-progress` fields before proceeding.

## Step 3 — Inspect the failing pipeline and classify failures

**Step 3.1 — List failed jobs.**

Call `mcp_gitlabvsct_list_pipeline_jobs` with:
- `project_id`: the GitLab project path (e.g. `group/repo`)
- `pipeline_id`: the value of `PIPELINE_ID` you received as argument
- `scope`: `"failed"`

Collect all jobs whose `status` is `failed` or `canceled`.

**Step 3.2 — Fetch logs and classify each failed job.**

For each failed job, call `mcp_gitlabvsct_get_pipeline_job_output` with:
- `project_id`: the GitLab project path
- `job_id`: the job's `id`
- `limit`: `50000` (fetch up to 50 KB of log)

Classify the failure as one of:

| Classification | Criteria |
|----------------|----------|
| `obvious` | The log contains a clear, actionable error message: lint rule violation with file and line number, compilation error with explicit symbol or syntax message, test assertion failure with expected vs actual values. |
| `non-obvious` | The log contains infrastructure errors (image pull failure, network timeout, runner eviction), intermittent failures with no code change correlation, or any error where the root cause cannot be determined from the log alone. |

**Step 3.3 — Write one classification block per job to the pivot document.**

For each job, call:
```python
from ci_fix import pivot
pivot.append_cycle(PIVOT_PATH, {
    "JOB": "<job-name>",
    "CLASSIFICATION": "<obvious|non-obvious>",
    "FAILURE_SUMMARY": "<one-line summary of the root cause>",
})
```

**Step 3.4 — Check if all failures are non-obvious.**

Count the number of jobs classified as `obvious` vs `non-obvious`.

If **all** failed jobs are `non-obvious`:
1. Write a blocked status block with a human-readable reason:
   ```python
   pivot.append_cycle(PIVOT_PATH, {
       "STATUS": "blocked",
       "REASON": "All failures are non-obvious — manual inspection required",
   })
   ```
2. Print the following message and stop:
   ```
   BLOCKED: all failing jobs have non-obvious failures.
   See <PIVOT_PATH> for details.
   Manual intervention is required.
   ```

If **at least one** job is `obvious`, proceed to Step 4 (fix application).

## Step 4 — Apply fixes and create commits

For each `obvious` failing job (in the order they appear in the pipeline job list):

**Step 4.1 — Apply the minimal fix.**

Read the `FAILURE_SUMMARY` written in Step 3.3 and the full job log. Apply the smallest code change that resolves the failure. Do **not** refactor unrelated code.

**Step 4.2 — Stage and commit.**

Stage only the files changed to fix this specific job:

```bash
git add <changed files>
```

Create one commit using the following message format exactly:

```
fix: ci — <job-name>: <one-line description of the fix>
```

Where `<one-line description>` is a concise imperative sentence (e.g. "remove unused import in utils.py").

```bash
git commit -m "fix: ci — <job-name>: <one-line description>"
```

> **Commit message format rule:** the message must match `^fix: ci — .+: .+$`.
> One commit per job — never squash or cross-contaminate fixes.

Repeat Steps 4.1–4.2 for every obvious failing job before proceeding.

## Step 5 — Display summary and push

**Step 5.1 — Display commit summary.**

Run `git log --oneline -<N>` (where N is the number of commits just created) and display the output so the user can review each commit.

**Step 5.2 — Prompt for push confirmation.**

Print the following prompt (exactly one line, no trailing text):

```
Push <N> commit(s) to trigger a new pipeline? [y/N]
```

Read the user's response.

**Step 5.3a — User answers Y (push).**

Run:
```bash
git push 2>&1
```

Capture the full stdout+stderr output.

Parse the pipeline ID using:
```python
from ci_fix.gitlab_client import parse_pipeline_id
pipeline_id = parse_pipeline_id(push_output)
```

If `pipeline_id` is `None` (not found in push output), fall back to the MCP tool:
```
mcp_gitlabvsct_list_merge_request_pipelines(project_id=<project_path>, merge_request_iid=<MR_NUMBER>)
```
Take the pipeline with the highest `id` from the returned list as the new `pipeline_id`.

Append to the pivot document:
```python
pivot.append_cycle(PIVOT_PATH, {
    "PIPELINE_ID": str(pipeline_id),
    "STATUS": "in-progress",
})
```

Print:
```
Pushed. New pipeline: <pipeline_id>
```

**Step 5.3b — User answers N or provides no input (do not push).**

Do **not** run `git push`. Leave all commits in place (they remain in `git log`).

Append to the pivot document:
```python
pivot.append_cycle(PIVOT_PATH, {
    "STATUS": "blocked",
    "REASON": "push declined by user",
})
```

Print:
```
BLOCKED: push declined by user.
Commits are staged in git log. Re-run ci-fix when ready to push.
```

</what-to-do>
