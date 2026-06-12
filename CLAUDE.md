# Curb — agent operating brief

## What this is
An AI accessibility auditor that proposes verified WCAG fixes, scored by an eval harness.
Read `docs/ARCHITECTURE.md` before touching the worker pipeline or the eval harness.

## Workflow (READ THIS)
- Commit directly to `main`. No feature branches, no pull requests.
- One coherent step per commit, conventional-commit format. Keep commits small and self-contained.
- Run the pre-push checks before every commit; never commit red. CI on `main` is a safety net, not a gate.
- Pace the work across sessions; the commit history is meant to read as real, paced development.
- Never backdate, amend-history, or force-push to fake a cadence.

## Golden rules
- Detection is deterministic. axe-core is the source of truth for whether a violation exists. The
  model never decides that.
- A remediation may be marked `verified` ONLY after the validate tool applies it and axe confirms the
  violation is gone with no new violations. No exceptions.
- Ground every fix in retrieved WCAG / ARIA guidance; cite the criterion.
- The model is chosen only in the gateway. Never hardcode a provider elsewhere. BYOK keys are
  per-request and never persisted or logged.
- Curb's own UI must meet the accessibility bar it audits for. a11y is part of done.

## Conventions
- Python managed with `uv`; lint/format with `ruff`; types with `mypy` (strict). No bare except, no
  `Any` without a justifying comment.
- TypeScript strict in `apps/web`; Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`).
- UK English in user-facing copy. No em dashes.
- Styling: design tokens (CSS custom properties) + CSS Modules. (Tailwind v4 only if the owner flips it.)

## Commands
- `just dev`           &mdash; web + api + worker (docker compose)
- `just test`          &mdash; pytest + svelte-check
- `just eval`          &mdash; full eval harness
- `just eval-smoke`    &mdash; fast subset (pre-push)
- `just lint`          &mdash; ruff
- `just typecheck`     &mdash; mypy

## Guardrails
- PUBLIC repo. Assume everything committed is world-readable. Never commit secrets or keys. Secrets
  live in `.env` (gitignored) and GitHub Actions secrets; the owner provisions real values.
- Do not weaken the verified-only rule or the eval thresholds to make something pass.
- Do not swap free/local models for a paid default. Cost-free operation is a design goal.

## Definition of done (per commit)
1. Pre-push checks pass (ruff, mypy, pytest fast, svelte-check, eval smoke).
2. New worker logic has a test; new remediation logic respects verified-only.
3. New interactive UI is keyboard-operable and passes axe.
4. `docs/ARCHITECTURE.md` updated if the pipeline or contracts changed.
