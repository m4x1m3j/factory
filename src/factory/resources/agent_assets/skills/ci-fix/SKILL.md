---
name: ci-fix
description: Diagnose and fix obvious CI failures one job at a time.
---

Inspect failing job logs. Classify failures as obvious or non-obvious. Apply
minimal fixes for obvious failures, create one commit per job, and stop for
human input when the cause is unclear. Never push without approval.