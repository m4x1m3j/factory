---
name: mr-review
description: >
  Given a GitLab MR number, fetches all open review threads and either commits
  a fix per thread (if the resolution is obvious) or drafts a proposed response
  in a local result file. Produces target/result-{mr-number}.md as a
  pivot file for user review and iteration. NEVER pushes. 1 commit per thread.
---

<what-to-do>

You are acting as an automated MR review responder. Follow these steps exactly.

## Step 1 — Resolve the GitLab project

Run the following terminal command to get the remote URL:

```
git remote get-url origin
```

Parse the project namespace from the URL. Both SSH (`git@gitlab.com:group/repo.git`)
and HTTPS (`https://gitlab.com/group/repo.git`) formats must be handled.
Strip the `.git` suffix. The result is the `project_path` (e.g., `group/repo`).

## Step 2 — Fetch MR metadata

Using the GitLab MCP, call `mcp_gitlabvsct_get_merge_request` with the resolved
`project_path` and the MR number provided by the user.

Extract:
- `source_branch`: the branch the MR is open from
- `title`: for context

## Step 3 — Branch guard

Run:

```
git branch --show-current
```

If the current branch does NOT match `source_branch`, abort immediately with:

> Error: You are on branch `<current>`, but MR !<number> targets `<source_branch>`.
> Switch to `<source_branch>` first, then re-run this skill.

Do not proceed further.

## Step 4 — Rotate the previous result file

If `target/result-{mr-number}.md` already exists at the repo root:

1. Find the highest existing `.old.N` suffix for that file (start at 0).
2. Rename the current file to `target/result-{mr-number}.md.old.<N+1>`.

## Step 5 — Fetch open threads

Using the GitLab MCP, call `mcp_gitlabvsct_mr_discussions` (or equivalent) to
list all discussions on the MR. Filter to keep only threads that are:
- Not resolved
- Have at least one note (exclude system notes)

For each thread, collect:
- `thread_id`
- `file_path` and `line` (if it is an inline comment; null if general)
- The full text of the first/root note (the reviewer's comment)

If there are no open threads, write a result file with a single line:
`No open threads found on MR !{mr-number}.` and stop.

## Step 6 — Load relevant context

For each thread, read the diff of the MR to understand what changed:
- Use `mcp_gitlabvsct_get_merge_request_diffs` to fetch the MR diff.
- If the thread is inline, also read the local file at the referenced path.

## Step 7 — Process each thread (one at a time)

For each open thread, perform an **obviousness judgment**:

> Read the reviewer's comment, the diff, and the relevant file content.
> Decide: is the resolution unambiguous enough to commit immediately?
>
> Obvious if: the change is clear, bounded, and safe — e.g., fix a specific bug,
> rename a symbol, remove dead code, correct a typo, add a null check.
>
> Non-obvious if: the request is a question, a design discussion, is ambiguous,
> requires architectural input, or the model is not confident about the correct
> change.

### If obvious → commit

1. Apply the change to the relevant local file(s).
2. Stage only the changed files:
   ```
   git add <file1> [<file2> ...]
   ```
3. Commit with the message:
   ```
   fix: address review thread #<thread-id>

   <One-line description of what was changed>
   ```
   Run: `git commit -m "fix: thread #<thread-id>" -m "<description>"`
4. Capture the resulting commit SHA1:
   ```
   git rev-parse HEAD
   ```
5. Record status: `committed — <sha1>`

**NEVER run `git push`.**

### If non-obvious → propose

1. Draft a clear, actionable proposed response or change description.
   - If it is a question: draft a direct answer.
   - If it requires a code change: describe exactly what should be changed and why.
2. Record status: `proposed — <draft response>`

## Step 9 — Write the result file

Write `target/result-{mr-number}.md` at the repo root.

If a previous `.old.*` file exists, read it before writing. Do not re-propose
a response that is identical to a previous proposal — if the proposed text would
be the same, note `(same proposal as previous run)` instead.

Use this format strictly:

```markdown
# MR !{mr-number} Review — {title}

Generated: {ISO date}
Branch: `{source_branch}`
Open threads processed: {N}

---

## Thread #{thread-id-1}

**File:** `path/to/file.kt` line 42
*(omit this line if not an inline comment)*

**Comment:**
> {original reviewer comment verbatim}

**Status:** committed — `{sha1}`

---

## Thread #{thread-id-2}

**Comment:**
> {original reviewer comment verbatim}

**Status:** proposed — {AI-drafted response or change description}

---
```

## Step 10 — Summary

After writing the result file, print a concise summary to the user:

- How many threads were processed
- How many commits were made (list each SHA1 and its thread)
- How many proposals are waiting in the result file
- Remind the user: **you must push manually** when ready

</what-to-do>
