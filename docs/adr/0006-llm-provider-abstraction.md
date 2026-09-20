# ADR-0006: Provider-agnostic LLM interface with budgets and structured output

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/08-ai-agents.md`, `packages/llm/`, `packages/policy/`, phase 8 of the implementation backlog

## Context

Diagnosis and remediation proposals depend on an LLM, which is the least reliable, least predictable and
most expensive dependency in the platform. Providers differ in APIs, rate limits, structured-output
support and pricing, and they change frequently. A model or prompt change must not be able to silently
reduce safety. The platform must also be demonstrable in CI without calling a paid API.

## Decision

We will define a small provider interface in `packages/llm/` (`complete`, `complete_structured`) with
adapters for OpenAI-compatible APIs, Anthropic-style APIs and a local OpenAI-compatible runtime (for
example Ollama/vLLM), plus a deterministic fake adapter for tests. The interface owns timeouts, retry with
jittered exponential backoff, rate-limit handling, token and cost accounting, structured-output parsing
and schema validation, and a documented provider fallback policy. Prompts are versioned files in the
repository; every invocation records agent version, prompt version, model/provider and the evidence IDs
that were sent. Budgets (tokens, iterations, wall-clock timeout, evidence payload size, cost per incident)
are enforced in code by the caller, not requested in the prompt.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Call provider SDKs directly from agents | Scatters retry, timeout, cost and validation logic; makes model swaps invasive |
| A large agent framework | Adds a heavy abstraction with its own prompt/state model; the platform needs a narrow, auditable interface |
| Self-hosted models only | Removes provider risk but makes the local/CI story and quality claims impractical for a reference implementation |
| Single provider with no fallback | A provider incident would stop the whole control loop |
| Let the model call tools freely | Unacceptable: tool authorization must be explicit and independent of model output |

## Consequences

- **Positive:** provider swaps are configuration, tests are deterministic through the fake adapter, cost and
  token usage are measurable per incident, and structured output is validated against `packages/contracts`
  schemas before anything downstream sees it.
- **Negative:** the lowest-common-denominator interface hides provider-specific capabilities, and every
  adapter needs contract tests to keep behaviour aligned.
- **Neutral:** model and prompt versions become part of the audit record, so regressions can be attributed.

## Security, privacy and agent impact

TB-4 (LLM provider ↔ control plane) is the relevant boundary. Prompts contain bounded, sanitized evidence
and never credentials, tokens, customer data or internal endpoints. Model output is untrusted: it is
schema-validated, it cannot select tools, and it never bypasses the policy engine or the approval
requirement. Provider error surfaces must not leak API keys into logs or API responses.

## Validation

- Contract tests run every adapter, including the fake, against the same behavioural suite (timeouts,
  retries, rate limits, malformed output, refusal).
- The agent evaluation suite asserts diagnosis categories, evidence grounding, uncertainty behaviour and
  refusal of unsafe actions for fixed fixtures.
- Cost and token accounting is asserted in unit tests, and per-incident cost appears on the agent
  operations dashboard.
