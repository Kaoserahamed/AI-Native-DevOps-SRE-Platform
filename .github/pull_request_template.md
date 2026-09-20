# Pull Request

## Summary

<!-- What changed, and why? One or two paragraphs. Keep it reviewable. -->

## Linked work

- Issue: <!-- Refs: #123 -->
- ADR / runbook: <!-- ADR-0007, docs/20-runbooks/... -->
- Incident: <!-- incident ID if this change fixes or follows one -->

## Type of change

- [ ] `feat` — new capability
- [ ] `fix` — bug fix
- [ ] `security` — security control or hardening
- [ ] `refactor` / `perf` — no behaviour change intended
- [ ] `test` — tests only
- [ ] `docs` — documentation only
- [ ] `build` / `ci` / `cd` — toolchain or pipeline
- [ ] `chore` / `release` — maintenance or versioning

## What was verified

<!-- The exact commands you ran. Paste evidence such as lint/type-check/test summaries when useful. -->

```text
uv run lint
uv run typecheck
uv run test
```

- [ ] Unit tests added/updated (or explained why not)
- [ ] Contract/integration/e2e tests added where applicable
- [ ] CI green, including the security jobs
- [ ] Documentation updated (README, `docs/`, ADR, runbook, configuration reference)
- [ ] `CHANGELOG.md` updated under `Unreleased` for user-visible changes

## Security and safety review

- [ ] No secrets, credentials, tokens, kubeconfigs, `.env` files or Terraform state committed
- [ ] New external input is validated and treated as untrusted (logs, GitHub content, telemetry)
- [ ] Agent capabilities remain read-only unless an approved, policy-checked action requires more
- [ ] Production mutation still requires explicit human approval; approvals bind to an action hash
- [ ] New permissions/credentials follow least privilege and are documented
- [ ] Threat model updated if a trust boundary changed

## Observability

- [ ] Metrics, logs and traces added/updated for new critical paths
- [ ] Correlation IDs propagate through new boundaries
- [ ] Dashboards/alerts updated when a new signal is introduced

## Deployment and rollback

- [ ] Migration impact described (schema, data, state) and reversible where practical
- [ ] Rollback path documented or confirmed unchanged
- [ ] Configuration/env vars documented in `.env.example` and `docs/04-configuration.md`

## Reviewer notes

<!-- Anything reviewers should focus on, known limitations, follow-up work. -->
