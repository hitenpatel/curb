# Curb task runner

default:
    @just --list

# Boot the full stack locally via docker compose
dev:
    docker compose -f infra/docker-compose.yml up --build

# Stop and remove the stack
down:
    docker compose -f infra/docker-compose.yml down

# Python + frontend tests
test:
    uv run pytest -q
    pnpm --dir apps/web run check

# Build (or rebuild) the WCAG + ARIA guidance corpus
corpus *args:
    uv run python -m corpus.ingest {{args}}

# Full eval harness (runs in CI as the deploy gate)
eval:
    uv run deepeval test run evals/golden

# Fast eval subset, used by the pre-push hook
eval-smoke:
    uv run deepeval test run evals/smoke

# Lint + format check
lint:
    uv run ruff check .
    uv run ruff format --check .

# Type check
typecheck:
    uv run mypy services packages

# Apply all auto-fixes
fix:
    uv run ruff check --fix .
    uv run ruff format .
