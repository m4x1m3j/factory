# Glossary

## Core Concepts

### Factory Core
Python package and CLI engine implementing the workflow orchestrator, agent adapter protocols, signal detection, validation harnesses, and release gates.

### Factory CLI
Command-line user interface providing explicit commands for bootstrapping target projects, managing the signal queue, directly executing agent adapters, orchestrating multi-stage pipelines, and monitoring sandboxes.

### Factory Workspace
Repository hosting the Factory Core engine source code, tooling, specifications, and test harnesses.

### Self-Hosting (Bootstrapping)
Operating Factory on itself: using Factory's own agent adapters, verification hooks, and sandbox manager to implement, test, and release Factory Core features.

### Target Project
Any external software repository that consumes Factory Core to automate its engineering lifecycle, initialized and operated through Factory commands.

### Project Archetype
Pre-packaged template and configuration blueprint (e.g. Python MLOps, TypeScript API, CLI tool) providing base directory layout, toolchain configuration, sandbox specification, and CI pipelines upon project initialization.

### Project Bootstrapper
Subsystem within Factory Core responsible for scaffolding a Target Project from a chosen Project Archetype, setting up dependency managers, sandbox environments, and CI integrations.

### Signal
Normalized data structure representing an actionable event, issue, telemetry alert, pull request status, or human prompt entering the Factory.

### Signal Queue
Persistent backlog holding ingested signals awaiting triage, scoring, or dispatch to active workflows.

### Triage Agent
Autonomous agent evaluating, deduplicating, scoring priority, and routing signals from the Signal Queue into execution pipelines.

### Workflow Orchestrator
Event-driven engine that sequences pipeline stages (monitoring, signal detection, code generation, validation, release), tracking global state and triggering steps automatically.

### Release Gate
Evaluation checkpoint between Validation and Release Management enforcing risk policy; allows autonomous delivery for low-risk changes while holding higher-risk changes for human sign-off.

### Risk Policy
Project-level configuration defining risk tiers, test coverage criteria, and blast-radius thresholds that determine whether a validated change qualifies for autonomous release.

### Agent Adapter
Pluggable execution bridge allowing a specific stage or standalone task to run either through an autonomous LLM runner or via external agent CLIs/harnesses (e.g. Claude Code, Copilot workspace agent, OpenHands).

### Shared Agent Assets
Common, version-controlled definitions (AGENTS.md, MCP servers, skills, prompts, and subagents) distributed by Factory Core across target projects.

### Asset Synchronizer
Subsystem within Factory Core responsible for compiling vendor-neutral Shared Agent Assets into harness-specific configuration structures (e.g. `.github/`, `.opencode/`) and synchronizing updates across target projects.

### Agent Persona
Declarative specification of an agent profile (identity, system instructions, tool whitelist, associated skills, and model preferences) defined within Shared Agent Assets, compiled to interactive harnesses (e.g. GitHub Copilot, OpenCode) and autonomous pipeline stages.

### Model Capability Tier
Abstract classification of model capabilities (e.g. reasoning, code_generation, fast_triage) defined on Agent Personas and mapped to harness-specific models via project configuration.

### Context & Harness Engine
Subsystem packaging codebase knowledge, token-budgeted memory, project instructions, and execution boundaries injected into an agent before and during execution.

### Harness Hook
Event-driven interceptor executing before or after an agent tool call within an interactive harness (e.g. PreToolUse command rewriting, PostToolUse immediate code quality checks).

### Verification Hooks
Automated deterministic checks (linters, static analysis, type checking, mutation testing) executed inside sandboxes to evaluate agent output.

### Backpressure Loop
Feedback mechanism intercepting agent output with Verification Hook failures, halting runaway edits or forcing the agent into self-correction cycles before changes proceed.

### Long-Term Development Loop
Iterative workflow engine managing multi-turn, multi-session tasks across checkpoints, maintaining progress, rollback states, and persistent goals over extended timelines.

### Execution Sandbox
Containerized, isolated runtime environment (e.g. Docker container) allocated per agent run; confines file access, command execution, and dependencies to prevent host contamination and enable parallel execution.

### Sandbox Specification
Project-defined environment configuration (such as a Dockerfile or devcontainer definition) detailing system libraries, Python runtimes, and dependencies required by agents working in that project.

### Sandbox Manager
Subsystem within Factory Core controlling the lifecycle, concurrency throttles, resource limits, and cleanup of ephemeral Execution Sandboxes on the host machine.
