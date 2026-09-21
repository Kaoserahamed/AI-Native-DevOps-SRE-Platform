# AI agents

This document covers the agent runtime: the LLM interface every agent calls, the budgets that bound it, the
evidence it is allowed to see and the audit records it must produce. It is filled in by the phase that
implements each part, so nothing here describes behaviour the repository does not have.

| Area | Status |
| --- | --- |
| Provider-agnostic LLM interface, budgets, retry/fallback policy, cost accounting | Implemented (`packages/llm`) |
| Real provider adapters (OpenAI-compatible, Anthropic-style, local runtime) | Planned |
| Bounded evidence retrieval (`packages/observability`, adapters) | Planned |
| Incident analysis agent, anomaly detection, root-cause correlation | Planned |
| Evaluation and regression harness (`tests/agent_eval`) | Planned |

## LLM interface (`packages/llm`)

ADR-0006 fixes the shape: one small provider interface, with the cross-cutting concerns owned by the
interface rather than by the agents that call it. Nothing else in the platform knows which provider is in
use, and a model swap is configuration rather than an agent change.

| Module | Responsibility |
| --- | --- |
| `packages/llm/types.py` | Request, response, usage, model configuration and the error taxonomy |
| `packages/llm/provider.py` | The abstract interface: `complete`, `complete_structured`, `name`, `supported_models` |
| `packages/llm/client.py` | The budgeted, retrying client the control plane uses |
| `packages/llm/fallback.py` | Provider fallback chain |
| `packages/llm/retry.py` | Retryability and jittered exponential backoff |
| `packages/llm/budget.py` | Per-run token, call, wall-clock and cost ceilings plus usage accounting |
| `packages/llm/pricing.py` | Model prices and cost computation |
| `packages/llm/structured.py` | Schema-validated parsing of model output |
| `packages/llm/fake.py` | The deterministic provider every test tier uses |
| `packages/test_fixtures/clock.py` | Controllable clock and delay recorder shared by the test tiers |

### Calls

```python
from packages.llm import LlmBudget, ModelConfig, build_llm_client

client = build_llm_client(primary_provider, fallback_provider, budget=LlmBudget(max_cost_usd=0.25))
response = client.complete(request, deadline=monotonic() + 60.0)
diagnosis = client.complete_structured(request, DiagnosisSchema, deadline=...)
```

`complete` receives an **absolute monotonic deadline**. An adapter must pass it to its transport and raise
`LlmTimeoutError` when it elapses; a client that answers later than its attempt deadline is reported as a
timeout even though it answered, and the usage it reported is still recorded because the tokens were spent.

### Failure taxonomy

| Exception | Meaning | Retried | Falls back |
| --- | --- | --- | --- |
| `LlmTimeoutError` | The attempt exceeded its deadline | yes | yes |
| `LlmRateLimitError` | The provider refused the call (may carry `retry_after_seconds`) | yes | yes |
| `LlmUnavailableError` | Transport failure or a retryable provider-side error | yes | yes |
| `LlmRequestError` | The request itself is invalid | no | no |
| `LlmBudgetExceededError` | A token, call, wall-clock or cost ceiling would be breached | no | no |
| `LlmPricingError` | No price is registered for the model | no | no |
| `LlmSchemaError` | Model output is not a schema-valid JSON object | no | no |


### Budgets

Budgets are enforced in code, before the call, never requested in the prompt: the model cannot be trusted to
limit its own cost. Defaults are `LlmBudget()` below and every ceiling is per control-loop run (normally one
incident).

| Ceiling | Default | Enforced by |
| --- | --- | --- |
| `max_prompt_tokens` | 100 000 (estimated from characters, rounded up) | `UsageLedger.check` before the call |
| `max_completion_tokens` | 16 384 | request validation before the call |
| `max_cost_usd` | 5.00 | priced from reported usage after each call |
| `max_calls` | 8 | `UsageLedger.check` before the call |
| `max_wall_clock_seconds` | 120 | `UsageLedger.deadline`, which also caps the client deadline |

### Retry and fallback policy

- One attempt is one call to the wrapped provider (or one walk of the fallback chain).
- Retryable failures repeat up to `RetryPolicy.max_attempts` (default 3) with jittered exponential backoff
  (0.5 s initial, ×2, capped at 8 s, ±20 % jitter).
- A rate limit that reports `retry_after_seconds` waits at least that long, still bounded by the deadline.
- No retry and no fallback is ever scheduled into a deadline that has already passed.
- Providers are tried in priority order; only retryable failures move on to the next provider, and the
  response records which provider answered.

### Pricing

`PriceTable` maps a model name to `ModelPrice` (USD per million prompt and completion tokens). A model without
a price raises `LlmPricingError` **before** the call, because a silently zero-priced model would disable the
per-incident cost ceiling. The committed defaults are illustrative list prices; an operator registers a
self-hosted or renegotiated price with `PriceTable.register` or an override map instead of editing logic.

### Structured output

Model output is untrusted input. `complete_structured` parses exactly one JSON object (tolerating a Markdown
fence or surrounding prose), validates it against a Pydantic schema and raises `LlmSchemaError` otherwise. A
schema violation never reaches a downstream decision, and model output never selects a tool or a target — that
is the policy engine's job.

## Verification

| Tier | What it proves | Location |
| --- | --- | --- |
| Unit | Budget arithmetic, pricing, retry/backoff, fallback, timeout enforcement, schema validation | `tests/llm` |
| Contract | Every adapter implements the interface and can return validated structured output | `tests/llm/test_provider_contract.py` |
| Agent evaluation | Diagnosis categories, evidence grounding, uncertainty behaviour, unsafe-action refusal | Planned (`tests/agent_eval`) |

The deterministic provider (`FakeLlmProvider`) is scripted per test ("rate limit, then success"), so retry,
fallback and budget behaviour is asserted exactly and no test tier calls a paid API.
