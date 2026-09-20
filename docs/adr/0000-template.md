# ADR-NNNN: <decision title>

- **Status:** Proposed | Accepted | Superseded by ADR-NNNN
- **Date:** YYYY-MM-DD
- **Deciders:** <roles or people>
- **Related:** <issues, pull requests, docs>

## Context

Describe the forces at play: the requirement, the constraints (cost, operational maturity, team size,
existing platform choices), and any incident or measurement that motivates the decision. State what
would happen if nothing changed.

## Decision

State the decision in the active voice: "We will ...". Be specific enough that a reviewer can tell
whether the implementation matches it.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| <option> | <reason> |

## Consequences

- **Positive:** what becomes easier, cheaper or safer.
- **Negative:** what becomes harder, more expensive or riskier.
- **Neutral / follow-up:** migrations, deprecations, new runbooks, new tests.

## Security, privacy and agent impact

Which trust boundaries move (see `docs/01-architecture.md` section 4)? Does this change credentials,
permissions, egress, data retention, agent tools, prompt handling or the approval model? What must the
threat model gain?

## Validation

How will we know the decision worked: which tests, CI gates, dashboards, alerts or SLOs prove it, and how
would we detect that it was the wrong decision?
