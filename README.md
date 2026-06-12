# Curb

> An AI accessibility auditor that does not just detect WCAG 2.2 issues — it proposes verified code
> fixes, scored by an eval harness whose primary metric is deterministic (re-run axe-core on the
> patched DOM). Runs on free and local models.

**Status: Phase 0 — scaffold and live shell.** Live at `https://a11y.hiten.dev` (coming soon).

## Highlights
- **Verified-by-axe remediations.** The agent's `validate` tool applies each proposed patch to the
  live page and re-runs axe-core. Nothing is marked `verified` until axe confirms the violation is
  gone with no new violations.
- **Eval harness as a CI gate.** Primary metric: deterministic re-run-axe pass rate against a golden
  dataset. Secondary: an LLM-judge for idiomaticity and explanation correctness. A regression blocks
  deploy.
- **Free by design.** Local embeddings (MiniLM / BGE), free-tier generation (Gemini / Groq / GitHub
  Models / Ollama) selected in a provider-agnostic gateway, BYOK overrides for live runs.
- **Eats its own dog food.** Curb's own UI meets the WCAG bar it enforces.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the Mermaid diagram and a tour of the
pipeline. Colour key: green is free / local / deterministic; amber is the pluggable model layer;
purple is the agentic core (the standout part).

## Repository layout

```
apps/web/           SvelteKit 2 + Svelte 5 runes
services/api/       FastAPI (audit lifecycle + SSE)
services/worker/    Playwright + axe, retrieval, agent, scoring
packages/shared/    Pydantic models shared by api + worker
corpus/             WCAG 2.2 + ARIA APG sources + ingestion script
evals/golden/       curated issue -> ideal-fix cases
evals/smoke/        fast subset for the pre-push hook
infra/              docker compose + Dockerfiles
```

## Local development

```bash
just dev           # web + api + worker via docker compose
just test          # pytest + svelte-check
just eval          # full eval harness
just eval-smoke    # fast subset, same as the pre-push hook
```

## Deployment

Docker / Traefik on a self-hosted box behind `a11y.hiten.dev`. GitHub Actions runs lint, type check,
tests, and the eval harness on every push to `main`; a failing eval blocks the deploy step.
