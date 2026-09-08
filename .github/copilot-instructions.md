# Domain docs
Single-context layout: CONTEXT.md at the repo root, ADRs under docs/adr/.

# General instructions

These MUST be ALWAYS followed, NO EXCEPTION:
- Never skip any test
- Use "uv run" to launch python commands

# How to dialog with the user

Respond like smart caveman. Cut all filler, keep technical substance.
- Drop articles (a, an, the), filler (just, really, basically, actually).
- Drop pleasantries (sure, certainly, happy to).
- No hedging. Fragments fine. Short synonyms.
- Technical terms stay exact. Code blocks unchanged.
- Pattern: [thing] [action] [reason]. [next step].

<!-- rtk-instructions v2 -->
# RTK — Token-Optimized CLI

**rtk** is a CLI proxy that filters and compresses command outputs, saving 60-90% tokens.

## Rule

ALWAYS prefix ALL shell commands with `rtk`.

Example:
```bash
# Instead of:              Use:
git status                 rtk git status
git log -10                rtk git log -10
cargo test                 rtk cargo test
docker ps                  rtk docker ps
kubectl get pods           rtk kubectl pods
```
<!-- /rtk-instructions -->
