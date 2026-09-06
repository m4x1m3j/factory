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