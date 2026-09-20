# Contributing

Thanks for improving the AI-Native DevOps & SRE Platform. This document describes how changes are
proposed, reviewed and validated. It is intentionally strict: CI enforces what is written here.

## Ways to contribute

- Bug reports and security reports (see [SECURITY.md](SECURITY.md) — do not open a public issue for a vulnerability).
- Feature and architecture proposals via the issue templates in `.github/ISSUE_TEMPLATE/`.
- Pull requests that implement an approved proposal (small documentation fixes may go straight to a PR).

## Ground rules

1. **One logical change per commit.** A commit is one feature, refactor, test improvement, documentation
   change or security improvement — not a bundle of unrelated work.
2. **Every production-code change ships tests** unless the change is genuinely not testable; in that case
   the PR explains why.
3. **Tests must not be weakened to make a build pass.** Fix the code, or document the defect.
4. **Never commit secrets or generated infrastructure state**: no credentials, tokens, `.env` files,
   Terraform state/plan files, kubeconfigs, private keys or production data. CI runs a secret scan.
5. **Do not manufacture history.** Commits must represent real work performed; no backdating and no
   artificially fragmented commits.
6. **Public behaviour changes require documentation**: API changes update the OpenAPI document and
   `docs/05-api.md`; configuration changes update `docs/04-configuration.md` and `.env.example`.
7. **Agents never mutate production directly.** All production-changing actions require policy approval
   plus an explicit human approval, and must be auditable.

## Development workflow

```bash
# 1. Install the documented toolchain (see `docs/03-local-development.md`)
python -m pip install uv
uv sync --frozen --all-extras
uv run pre-commit install

# 2. Create a topic branch
git switch -c feat/short-description

# 3. Make the change, then run the repository verification entry point
uv run pre-commit run --all-files
uv run lint
uv run typecheck
uv run test
```

Windows users can run the same logical steps through the commands documented in
`docs/03-local-development.md`; the repository `Makefile` documents the canonical CI invocation.

## Commit and branch conventions

- Branches: `feat/…`, `fix/…`, `chore/…`, `docs/…`, `security/…`, `ci/…`, `test/…`, `refactor/…`.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`
  in the imperative mood, for example `feat(api): add incident lifecycle endpoints`.
- Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`,
  `security`, `release`, `cd`.
- Reference the GitHub issue and the incident or ADR when applicable (`Refs: #123`, `ADR-0007`).

## Pull request requirements

A PR is ready for review only when all of the following hold:

- The description explains **what changed, why, and how it was verified**.
- Tests were added or updated and pass locally.
- Documentation is updated (README, `docs/`, ADR, runbook, or changelog).
- Security implications were reviewed: new external input, new credentials, new egress, new permissions.
- Observability was considered for new critical paths (logs, metrics, traces, correlation IDs).
- Migration and rollback impact is described when persisted data or deployed infrastructure changes.
- `CHANGELOG.md` is updated under `Unreleased` for user-visible changes.
- CI is green, including the security jobs (security jobs are required checks).

Reviewers use the checklist in `.github/pull_request_template.md` and may request an ADR for changes to
architecture, trust boundaries, or the agent safety model.

## Testing tiers

| Tier | Runs | Location | Rules |
| --- | --- | --- | --- |
| Unit | Always, fast, no network | `*/tests/unit`, `packages/*/tests` | Deterministic fixtures only |
| Contract | Always, fast | `tests/contract` | Validates schemas/adapters against fakes |
| Integration | Dedicated CI job | `tests/integration` | Real ephemeral PostgreSQL/Redis/OTel |
| End-to-end | Dedicated CI job | `tests/e2e` | Ephemeral Kubernetes cluster |
| Agent evaluation | Dedicated CI job | `tests/agent_eval` | Fixed incident fixtures, safety assertions |

Unit and contract tests must never require a live service: use the fakes in `packages/test_fixtures`.

## Architecture decisions

Significant technical decisions are recorded as ADRs in `docs/adr/` using the template
`docs/adr/0000-template.md`. ADRs are immutable once accepted; a superseding decision is a new ADR that
references the old one.

## Code of conduct and licensing

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Contributions are accepted
under the [Apache License 2.0](LICENSE); do not submit code you cannot license this way.
