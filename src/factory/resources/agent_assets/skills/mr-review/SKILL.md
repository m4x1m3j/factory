---
name: mr-review
description: Review pull requests, publish one inline GitHub thread per finding, and verify publication.
---

Review changed behavior first. Commit each obvious review fix separately. Draft
responses for ambiguous findings and never push without user approval.
For completed reviews, publish each finding directly on the pull request as one
inline thread. Use the GitHub review-comment API through `gh` when no dedicated
GitHub review tool is available. Use the pull request head commit and a changed
line for every comment. Do not substitute a chat summary for publication.

After publishing, query the pull request comments and verify that the number of
new threads matches the number of findings. Return the published comment URLs.
If GitHub publication or verification cannot be performed, report the blocker
and leave the review incomplete.
