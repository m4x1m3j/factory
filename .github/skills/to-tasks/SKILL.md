---
name: to-tasks
description: Turn the current conversation context into independently-grabbable tasks using tracer-bullet vertical slices. Use when user wants to break down the context into ready to implement tasks.
---

# To Tasks

This skill takes the current conversation context and codebase understanding and turn it into independently-grabbable tasks using vertical slices (tracer bullets).
The tasks will be written in a task-<topic>.md file ; that will be used as input by agentic or human developers to be implemented. So, all important information contained in the current context must be written down in this file.

## Process

### 1. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Tasks titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

### 2. High level conception

Sketch out the major modules you will need to build or modify to complete the implementation. Actively look for opportunities to extract deep modules that can be tested in isolation.

A deep module (as opposed to a shallow module) is one which encapsulates a lot of functionality in a simple, testable interface which rarely changes.

Check with the user that these modules match their expectations. Check with the user which modules they want tests written for.

### 3. Write tasks as vertical slices

Break the context into **tracer bullet** tasks. Each task is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

Slices may be 'HITL' or 'AFK'. HITL slices require human interaction, such as an architectural decision or a design review. AFK slices can be implemented and merged without human interaction. Prefer AFK over HITL where possible.

<vertical-slice-rules>
- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones
</vertical-slice-rules>

Create a file task-<topic>.md.

In this file, write the tasks list, with the following template:

- **Task#ID**: identifier of the task, starting from 0 and iterating
- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Blocked by**: which other slices (if any) must complete first
- **Status**: "to_be_implemented" by default
- **Description**: A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation. Avoid specific file paths or code snippets — they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it here and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.
- **Tests to be made**: a list of test that will prove that the task is correctly implemented, including edge cases ; one line per test.

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?
- Are the correct slices marked as HITL and AFK?

Iterate until the user approves the breakdown.
