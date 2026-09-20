# ADR-0007: Human approval bound to an action hash for every production change

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/09-incident-lifecycle.md`, `packages/policy/`, phase 9 of the implementation backlog

## Context

The platform can diagnose incidents and generate remediation proposals. Applying those proposals
unattended would make an LLM a production operator, with consequences that cannot be reviewed before
impact. At the same time, an approval mechanism that is slow, ambiguous or trivially bypassed degrades
into a rubber stamp. The mechanism must therefore be precise (what exactly is approved), bound in time,
single-use, and auditable — and it must be impossible for an agent to approve its own proposal.

## Decision

Every production-changing action requires an approval record that is:

1. **Bound to a canonical action hash** — a digest over the target (environment, namespace, workload),
   the operation and its parameters, and the image digest or manifest revision. If any element changes,
   the hash changes and the existing approval no longer applies.
2. **Identity-attributed** — the approver is an authenticated human principal, recorded with the decision,
   comment and timestamp; an agent or automation principal can never approve.
3. **Expiring and single-use** — approvals carry a short validity window and are consumed by exactly one
   execution; reuse is rejected.
4. **Execution-verified** — the executor re-computes the action hash and refuses to act when it does not
   match the approved hash, when the approval has expired, or when the policy result differs.
5. **Re-approval required on material change** — new evidence that changes the proposal category,
   blast radius, target revision or risk level invalidates the previous approval.

High-risk categories (production rollback, destructive configuration changes, actions outside the default
namespace) additionally require an explicit confirmation and the strictest policy result. No production
category has an auto-approval path.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Unattended auto-remediation with post-hoc review | The platform's whole value proposition is governance; a wrong automatic change is not recoverable by review |
| Silent approval ("no objection within N minutes") | Turns inactivity into consent and produces no accountable approver |
| Long-lived approvals for a class of actions | Replay risk and drift between what was reviewed and what executes |
| Approvals not bound to an action hash | The classic confused-deputy flaw: approve a benign action, execute a different one |
| Approval inside the agent's own runtime | An agent must not be able to grant itself authority |

## Consequences

- **Positive:** every production change has a traceable human decision, replay and substitution attacks
  fail closed, and approvals are a measurable SLO (approval latency) rather than an implicit process.
- **Negative:** incidents wait for a human; the approval UI/endpoint and expiry handling add surface area,
  and stale approvals create support questions that must be answered by observability (approval audit).
- **Neutral:** the incident lifecycle gains explicit `proposed → awaiting_approval → approved/rejected`
  transitions with tests for every invalid transition.

## Security, privacy and agent impact

This ADR defines TB-5's enforcement: agents hold read-only Kubernetes credentials and can only *propose*.
The action hash also serves as the idempotency key, so a replayed approval cannot cause a duplicate
mutation. Approver identity and the action hash are recorded in the append-only audit trail, and any
change to this model requires a threat-model update.

## Validation

- State-machine tests assert every invalid transition is rejected, including execution with a mismatched
  or expired approval and approval replay.
- Policy tests assert deny-by-default behaviour for unknown action categories and blocked targets.
- The agent evaluation fixtures include a case where the model proposes an unsafe action, and assert that
  the refusal happens before an approval can even be requested.
